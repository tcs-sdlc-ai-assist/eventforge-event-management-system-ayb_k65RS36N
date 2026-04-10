import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database import Base
from models.user import User
from models.event import Event
from models.event_category import EventCategory
from models.ticket import Ticket, TicketType
from models.rsvp import RSVP
from utils.security import hash_password, create_access_token, COOKIE_NAME


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client with the test database override."""
    from main import app
    from utils.dependencies import get_db

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create and return an admin user."""
    user = User(
        username="testadmin",
        email="testadmin@eventforge.com",
        display_name="Test Admin",
        hashed_password=hash_password("adminpass123"),
        role="Super Admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def organizer_user(db_session: AsyncSession) -> User:
    """Create and return an organizer (Project Manager) user."""
    user = User(
        username="testorganizer",
        email="testorganizer@eventforge.com",
        display_name="Test Organizer",
        hashed_password=hash_password("organizerpass123"),
        role="Project Manager",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def attendee_user(db_session: AsyncSession) -> User:
    """Create and return an attendee (Viewer) user."""
    user = User(
        username="testattendee",
        email="testattendee@eventforge.com",
        display_name="Test Attendee",
        hashed_password=hash_password("attendeepass123"),
        role="Viewer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(admin_user: User) -> str:
    """Return a valid JWT token for the admin user."""
    token = create_access_token(data={"sub": admin_user.id})
    return token


@pytest_asyncio.fixture
async def organizer_token(organizer_user: User) -> str:
    """Return a valid JWT token for the organizer user."""
    token = create_access_token(data={"sub": organizer_user.id})
    return token


@pytest_asyncio.fixture
async def attendee_token(attendee_user: User) -> str:
    """Return a valid JWT token for the attendee user."""
    token = create_access_token(data={"sub": attendee_user.id})
    return token


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_token: str) -> AsyncClient:
    """Provide an authenticated client for the admin user."""
    client.cookies.set(COOKIE_NAME, admin_token)
    return client


@pytest_asyncio.fixture
async def organizer_client(client: AsyncClient, organizer_token: str) -> AsyncClient:
    """Provide an authenticated client for the organizer user."""
    client.cookies.set(COOKIE_NAME, organizer_token)
    return client


@pytest_asyncio.fixture
async def attendee_client(client: AsyncClient, attendee_token: str) -> AsyncClient:
    """Provide an authenticated client for the attendee user."""
    client.cookies.set(COOKIE_NAME, attendee_token)
    return client


@pytest_asyncio.fixture
async def sample_category(db_session: AsyncSession) -> EventCategory:
    """Create and return a sample event category."""
    category = EventCategory(
        name="Technology",
        color="#6366f1",
        icon="💻",
    )
    db_session.add(category)
    await db_session.flush()
    await db_session.refresh(category)
    return category


@pytest_asyncio.fixture
async def sample_event(
    db_session: AsyncSession,
    organizer_user: User,
    sample_category: EventCategory,
) -> Event:
    """Create and return a sample published event with ticket types."""
    now = datetime.now(timezone.utc)
    event = Event(
        title="Test Conference 2024",
        description="A test conference for unit testing.",
        category_id=sample_category.id,
        organizer_id=organizer_user.id,
        venue_name="Test Venue",
        address_line="123 Test Street",
        city="Test City",
        state="Test State",
        country="Test Country",
        start_datetime=now + timedelta(days=30),
        end_datetime=now + timedelta(days=30, hours=8),
        total_capacity=500,
        status="published",
    )
    db_session.add(event)
    await db_session.flush()
    await db_session.refresh(event)

    general_ticket = TicketType(
        event_id=event.id,
        name="General Admission",
        price=49.99,
        quantity=300,
        sold=0,
        description="Standard entry ticket",
    )
    db_session.add(general_ticket)

    vip_ticket = TicketType(
        event_id=event.id,
        name="VIP",
        price=149.99,
        quantity=100,
        sold=0,
        description="VIP access with perks",
    )
    db_session.add(vip_ticket)

    await db_session.flush()
    await db_session.refresh(event)

    return event


@pytest_asyncio.fixture
async def draft_event(
    db_session: AsyncSession,
    organizer_user: User,
    sample_category: EventCategory,
) -> Event:
    """Create and return a sample draft event."""
    now = datetime.now(timezone.utc)
    event = Event(
        title="Draft Event 2024",
        description="A draft event for testing.",
        category_id=sample_category.id,
        organizer_id=organizer_user.id,
        venue_name="Draft Venue",
        address_line="456 Draft Avenue",
        city="Draft City",
        state="Draft State",
        country="Draft Country",
        start_datetime=now + timedelta(days=60),
        end_datetime=now + timedelta(days=60, hours=4),
        total_capacity=200,
        status="draft",
    )
    db_session.add(event)
    await db_session.flush()
    await db_session.refresh(event)
    return event