import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base, SessionLocal, engine
from models.user import User
from models.event import Event
from models.event_category import EventCategory
from models.ticket import TicketType
from utils.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DEFAULT_CATEGORIES = [
    {"name": "Music", "color": "#ec4899", "icon": "🎵"},
    {"name": "Technology", "color": "#6366f1", "icon": "💻"},
    {"name": "Sports", "color": "#22c55e", "icon": "⚽"},
    {"name": "Food & Drink", "color": "#f97316", "icon": "🍔"},
    {"name": "Business", "color": "#3b82f6", "icon": "💼"},
    {"name": "Arts", "color": "#a855f7", "icon": "🎨"},
    {"name": "Education", "color": "#14b8a6", "icon": "📚"},
    {"name": "Charity", "color": "#ef4444", "icon": "❤️"},
]

SAMPLE_EVENTS = [
    {
        "category": "Music",
        "title": "Summer Music Festival 2024",
        "description": "A weekend of live music performances featuring local and international artists across multiple stages.",
        "venue_name": "Central Park Amphitheater",
        "address_line": "123 Park Avenue",
        "city": "New York",
        "state": "New York",
        "country": "United States",
        "total_capacity": 5000,
        "ticket_types": [
            {"name": "General Admission", "price": 49.99, "quantity": 3000},
            {"name": "VIP", "price": 149.99, "quantity": 500},
            {"name": "Backstage Pass", "price": 299.99, "quantity": 100},
        ],
    },
    {
        "category": "Technology",
        "title": "DevCon 2024 — Developer Conference",
        "description": "Annual developer conference with talks on AI, cloud computing, web development, and emerging technologies.",
        "venue_name": "Moscone Center",
        "address_line": "747 Howard Street",
        "city": "San Francisco",
        "state": "California",
        "country": "United States",
        "total_capacity": 2000,
        "ticket_types": [
            {"name": "Standard", "price": 199.00, "quantity": 1500},
            {"name": "Premium", "price": 399.00, "quantity": 400},
            {"name": "Workshop Pass", "price": 599.00, "quantity": 100},
        ],
    },
    {
        "category": "Sports",
        "title": "City Marathon 2024",
        "description": "Annual city marathon open to runners of all levels. Includes 5K, 10K, half marathon, and full marathon categories.",
        "venue_name": "Downtown Starting Line",
        "address_line": "1 Main Street",
        "city": "Chicago",
        "state": "Illinois",
        "country": "United States",
        "total_capacity": 10000,
        "ticket_types": [
            {"name": "5K Entry", "price": 25.00, "quantity": 3000},
            {"name": "10K Entry", "price": 35.00, "quantity": 3000},
            {"name": "Half Marathon", "price": 55.00, "quantity": 2000},
            {"name": "Full Marathon", "price": 75.00, "quantity": 2000},
        ],
    },
    {
        "category": "Food & Drink",
        "title": "International Food Festival",
        "description": "Taste cuisines from around the world with over 50 food vendors, cooking demonstrations, and live entertainment.",
        "venue_name": "Waterfront Plaza",
        "address_line": "500 Harbor Drive",
        "city": "San Diego",
        "state": "California",
        "country": "United States",
        "total_capacity": 3000,
        "ticket_types": [
            {"name": "Day Pass", "price": 15.00, "quantity": 2000},
            {"name": "Weekend Pass", "price": 25.00, "quantity": 800},
            {"name": "VIP Tasting", "price": 75.00, "quantity": 200},
        ],
    },
    {
        "category": "Business",
        "title": "Startup Summit 2024",
        "description": "Connect with investors, mentors, and fellow entrepreneurs. Pitch competitions, networking sessions, and keynote speakers.",
        "venue_name": "Convention Center Hall A",
        "address_line": "200 Congress Avenue",
        "city": "Austin",
        "state": "Texas",
        "country": "United States",
        "total_capacity": 1500,
        "ticket_types": [
            {"name": "Attendee", "price": 99.00, "quantity": 1000},
            {"name": "Startup Exhibitor", "price": 299.00, "quantity": 200},
            {"name": "Investor Circle", "price": 499.00, "quantity": 100},
        ],
    },
    {
        "category": "Arts",
        "title": "Contemporary Art Exhibition",
        "description": "Showcasing works from emerging and established contemporary artists. Includes gallery tours and artist meet-and-greets.",
        "venue_name": "Metropolitan Gallery",
        "address_line": "88 Art Boulevard",
        "city": "Los Angeles",
        "state": "California",
        "country": "United States",
        "total_capacity": 800,
        "ticket_types": [
            {"name": "General Entry", "price": 20.00, "quantity": 600},
            {"name": "Guided Tour", "price": 45.00, "quantity": 150},
            {"name": "Opening Night Gala", "price": 120.00, "quantity": 50},
        ],
    },
    {
        "category": "Education",
        "title": "Future of Learning Conference",
        "description": "Exploring innovative approaches to education including EdTech, project-based learning, and AI in the classroom.",
        "venue_name": "University Conference Center",
        "address_line": "1000 University Drive",
        "city": "Boston",
        "state": "Massachusetts",
        "country": "United States",
        "total_capacity": 1000,
        "ticket_types": [
            {"name": "Educator Pass", "price": 0.00, "quantity": 500},
            {"name": "Professional", "price": 149.00, "quantity": 400},
            {"name": "Student", "price": 0.00, "quantity": 100},
        ],
    },
    {
        "category": "Charity",
        "title": "Annual Charity Gala — Hope for Tomorrow",
        "description": "An evening of fine dining, live auction, and entertainment to raise funds for children's education programs.",
        "venue_name": "Grand Ballroom Hotel",
        "address_line": "450 Luxury Lane",
        "city": "Miami",
        "state": "Florida",
        "country": "United States",
        "total_capacity": 500,
        "ticket_types": [
            {"name": "Individual Seat", "price": 150.00, "quantity": 300},
            {"name": "Table of 8", "price": 1000.00, "quantity": 25},
        ],
    },
]


async def seed_admin_user(db: AsyncSession) -> User:
    result = await db.execute(
        select(User).where(User.username == "admin")
    )
    admin = result.scalars().first()

    if admin is not None:
        logger.info("Admin user already exists (id=%s), skipping.", admin.id)
        return admin

    admin = User(
        username="admin",
        email="admin@eventforge.com",
        display_name="Admin User",
        hashed_password=hash_password("admin123"),
        role="Super Admin",
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    await db.refresh(admin)
    logger.info("Created admin user: id=%s username=%s", admin.id, admin.username)
    return admin


async def seed_categories(db: AsyncSession) -> dict[str, EventCategory]:
    category_map: dict[str, EventCategory] = {}

    for cat_data in DEFAULT_CATEGORIES:
        result = await db.execute(
            select(EventCategory).where(EventCategory.name == cat_data["name"])
        )
        existing = result.scalars().first()

        if existing is not None:
            logger.info("Category '%s' already exists (id=%s), skipping.", existing.name, existing.id)
            category_map[existing.name] = existing
            continue

        category = EventCategory(
            name=cat_data["name"],
            color=cat_data["color"],
            icon=cat_data["icon"],
        )
        db.add(category)
        await db.flush()
        await db.refresh(category)
        logger.info("Created category: id=%s name=%s", category.id, category.name)
        category_map[category.name] = category

    return category_map


async def seed_events(
    db: AsyncSession,
    organizer: User,
    category_map: dict[str, EventCategory],
) -> None:
    now = datetime.now(timezone.utc)

    for idx, event_data in enumerate(SAMPLE_EVENTS):
        category_name = event_data["category"]
        category = category_map.get(category_name)
        if category is None:
            logger.warning("Category '%s' not found, skipping event '%s'.", category_name, event_data["title"])
            continue

        result = await db.execute(
            select(Event).where(
                Event.title == event_data["title"],
                Event.organizer_id == organizer.id,
            )
        )
        existing_event = result.scalars().first()

        if existing_event is not None:
            logger.info("Event '%s' already exists (id=%s), skipping.", existing_event.title, existing_event.id)
            continue

        start_offset = timedelta(days=30 + (idx * 14))
        start_dt = now + start_offset
        end_dt = start_dt + timedelta(hours=8)

        event = Event(
            title=event_data["title"],
            description=event_data["description"],
            category_id=category.id,
            organizer_id=organizer.id,
            venue_name=event_data["venue_name"],
            address_line=event_data["address_line"],
            city=event_data["city"],
            state=event_data["state"],
            country=event_data["country"],
            start_datetime=start_dt,
            end_datetime=end_dt,
            total_capacity=event_data["total_capacity"],
            status="published",
        )
        db.add(event)
        await db.flush()

        for tt_data in event_data.get("ticket_types", []):
            ticket_type = TicketType(
                event_id=event.id,
                name=tt_data["name"],
                price=float(tt_data["price"]),
                quantity=int(tt_data["quantity"]),
                sold=0,
                description=None,
            )
            db.add(ticket_type)

        await db.flush()
        await db.refresh(event)
        logger.info(
            "Created event: id=%s title='%s' category='%s' tickets=%d",
            event.id,
            event.title,
            category_name,
            len(event_data.get("ticket_types", [])),
        )


async def run_seed() -> None:
    logger.info("Starting database seed...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")

    async with SessionLocal() as db:
        try:
            admin = await seed_admin_user(db)
            category_map = await seed_categories(db)
            await seed_events(db, admin, category_map)
            await db.commit()
            logger.info("Database seed completed successfully.")
        except Exception:
            await db.rollback()
            logger.exception("Database seed failed, rolling back.")
            raise


if __name__ == "__main__":
    asyncio.run(run_seed())