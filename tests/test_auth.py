import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from utils.security import COOKIE_NAME, hash_password, create_access_token


class TestRegistration:
    """Tests for user registration flow."""

    @pytest.mark.asyncio
    async def test_register_page_returns_200(self, client: AsyncClient):
        """GET /auth/register returns the registration form."""
        response = await client.get("/auth/register")
        assert response.status_code == 200
        assert "Create your account" in response.text

    @pytest.mark.asyncio
    async def test_register_creates_new_user(self, client: AsyncClient):
        """POST /auth/register with valid data creates a user and redirects."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "display_name": "New User",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "role": "Viewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")
        # Verify JWT cookie is set
        cookies = response.cookies
        assert COOKIE_NAME in cookies

    @pytest.mark.asyncio
    async def test_register_with_organizer_role(self, client: AsyncClient):
        """POST /auth/register with Project Manager role succeeds."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "organizer1",
                "email": "organizer1@example.com",
                "display_name": "Organizer One",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "role": "Project Manager",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert COOKIE_NAME in response.cookies

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient, db_session: AsyncSession):
        """POST /auth/register with an existing username returns error."""
        existing_user = User(
            username="existinguser",
            email="existing@example.com",
            display_name="Existing User",
            hashed_password=hash_password("password123"),
            role="Viewer",
            is_active=True,
        )
        db_session.add(existing_user)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/auth/register",
            data={
                "username": "existinguser",
                "email": "different@example.com",
                "display_name": "Another User",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "role": "Viewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already taken" in response.text

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient, db_session: AsyncSession):
        """POST /auth/register with an existing email returns error."""
        existing_user = User(
            username="emailowner",
            email="taken@example.com",
            display_name="Email Owner",
            hashed_password=hash_password("password123"),
            role="Viewer",
            is_active=True,
        )
        db_session.add(existing_user)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/auth/register",
            data={
                "username": "differentuser",
                "email": "taken@example.com",
                "display_name": "Different User",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "role": "Viewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert "already registered" in response.text

    @pytest.mark.asyncio
    async def test_register_password_mismatch(self, client: AsyncClient):
        """POST /auth/register with mismatched passwords returns 422."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "mismatchuser",
                "email": "mismatch@example.com",
                "display_name": "Mismatch User",
                "password": "securepass123",
                "confirm_password": "differentpass456",
                "role": "Viewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "Passwords do not match" in response.text

    @pytest.mark.asyncio
    async def test_register_short_password(self, client: AsyncClient):
        """POST /auth/register with password < 8 chars returns 422."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "shortpwuser",
                "email": "shortpw@example.com",
                "display_name": "Short PW User",
                "password": "short",
                "confirm_password": "short",
                "role": "Viewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "at least 8 characters" in response.text

    @pytest.mark.asyncio
    async def test_register_short_username(self, client: AsyncClient):
        """POST /auth/register with username < 3 chars returns 422."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "ab",
                "email": "shortname@example.com",
                "display_name": "Short Name",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "role": "Viewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "at least 3 characters" in response.text

    @pytest.mark.asyncio
    async def test_register_invalid_role(self, client: AsyncClient):
        """POST /auth/register with invalid role returns 422."""
        response = await client.post(
            "/auth/register",
            data={
                "username": "badroleuser",
                "email": "badrole@example.com",
                "display_name": "Bad Role User",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "role": "InvalidRole",
            },
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "Role must be one of" in response.text

    @pytest.mark.asyncio
    async def test_register_redirects_when_authenticated(
        self, organizer_client: AsyncClient
    ):
        """GET /auth/register redirects to /dashboard when already logged in."""
        response = await organizer_client.get(
            "/auth/register",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_register_post_redirects_when_authenticated(
        self, organizer_client: AsyncClient
    ):
        """POST /auth/register redirects to /dashboard when already logged in."""
        response = await organizer_client.post(
            "/auth/register",
            data={
                "username": "shouldnotcreate",
                "email": "shouldnot@example.com",
                "display_name": "Should Not",
                "password": "securepass123",
                "confirm_password": "securepass123",
                "role": "Viewer",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")


class TestLogin:
    """Tests for user login flow."""

    @pytest.mark.asyncio
    async def test_login_page_returns_200(self, client: AsyncClient):
        """GET /auth/login returns the login form."""
        response = await client.get("/auth/login")
        assert response.status_code == 200
        assert "Sign in to EventForge" in response.text

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /auth/login with correct credentials sets JWT cookie and redirects."""
        user = User(
            username="loginuser",
            email="loginuser@example.com",
            display_name="Login User",
            hashed_password=hash_password("correctpass123"),
            role="Viewer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/auth/login",
            data={
                "username": "loginuser",
                "password": "correctpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")
        assert COOKIE_NAME in response.cookies

    @pytest.mark.asyncio
    async def test_login_with_wrong_password(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /auth/login with wrong password returns 401."""
        user = User(
            username="wrongpwuser",
            email="wrongpw@example.com",
            display_name="Wrong PW User",
            hashed_password=hash_password("correctpass123"),
            role="Viewer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/auth/login",
            data={
                "username": "wrongpwuser",
                "password": "wrongpassword",
            },
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_with_nonexistent_user(self, client: AsyncClient):
        """POST /auth/login with nonexistent username returns 401."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "nosuchuser",
                "password": "anypassword123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_with_empty_username(self, client: AsyncClient):
        """POST /auth/login with empty username returns 422."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "   ",
                "password": "somepassword",
            },
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "Username cannot be empty" in response.text

    @pytest.mark.asyncio
    async def test_login_with_empty_password(self, client: AsyncClient):
        """POST /auth/login with empty password returns 422."""
        response = await client.post(
            "/auth/login",
            data={
                "username": "someuser",
                "password": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 422
        assert "Password cannot be empty" in response.text

    @pytest.mark.asyncio
    async def test_login_with_inactive_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """POST /auth/login with inactive user returns 401."""
        user = User(
            username="inactiveuser",
            email="inactive@example.com",
            display_name="Inactive User",
            hashed_password=hash_password("correctpass123"),
            role="Viewer",
            is_active=False,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/auth/login",
            data={
                "username": "inactiveuser",
                "password": "correctpass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert "Invalid username or password" in response.text

    @pytest.mark.asyncio
    async def test_login_redirects_when_authenticated(
        self, organizer_client: AsyncClient
    ):
        """GET /auth/login redirects to /dashboard when already logged in."""
        response = await organizer_client.get(
            "/auth/login",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_login_post_redirects_when_authenticated(
        self, organizer_client: AsyncClient
    ):
        """POST /auth/login redirects to /dashboard when already logged in."""
        response = await organizer_client.post(
            "/auth/login",
            data={
                "username": "anyuser",
                "password": "anypassword",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/dashboard" in response.headers.get("location", "")


class TestLogout:
    """Tests for user logout flow."""

    @pytest.mark.asyncio
    async def test_logout_get_clears_cookie_and_redirects(
        self, organizer_client: AsyncClient
    ):
        """GET /auth/logout clears the JWT cookie and redirects to login."""
        response = await organizer_client.get(
            "/auth/logout",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("location", "")
        # Check that the cookie is being deleted (set-cookie with max-age=0 or expires in past)
        set_cookie_header = response.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie_header

    @pytest.mark.asyncio
    async def test_logout_post_clears_cookie_and_redirects(
        self, organizer_client: AsyncClient
    ):
        """POST /auth/logout clears the JWT cookie and redirects to login."""
        response = await organizer_client.post(
            "/auth/logout",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("location", "")
        set_cookie_header = response.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie_header

    @pytest.mark.asyncio
    async def test_logout_without_auth_still_redirects(self, client: AsyncClient):
        """GET /auth/logout without being logged in still redirects to login."""
        response = await client.get(
            "/auth/logout",
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("location", "")


class TestJWTCookie:
    """Tests for JWT cookie behavior."""

    @pytest.mark.asyncio
    async def test_jwt_cookie_is_httponly(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """JWT cookie should be set with httponly flag."""
        user = User(
            username="cookieuser",
            email="cookie@example.com",
            display_name="Cookie User",
            hashed_password=hash_password("securepass123"),
            role="Viewer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.commit()

        response = await client.post(
            "/auth/login",
            data={
                "username": "cookieuser",
                "password": "securepass123",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        set_cookie_header = response.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie_header

    @pytest.mark.asyncio
    async def test_invalid_jwt_cookie_does_not_authenticate(
        self, client: AsyncClient
    ):
        """A request with an invalid JWT cookie should not be authenticated."""
        client.cookies.set(COOKIE_NAME, "invalid.jwt.token")
        response = await client.get("/auth/login", follow_redirects=False)
        # Should show login page (not redirect to dashboard)
        assert response.status_code == 200
        assert "Sign in to EventForge" in response.text

    @pytest.mark.asyncio
    async def test_expired_token_does_not_authenticate(self, client: AsyncClient):
        """A request with an expired JWT should not be authenticated."""
        from datetime import timedelta

        token = create_access_token(
            data={"sub": "nonexistent-user-id"},
            expires_delta=timedelta(seconds=-10),
        )
        client.cookies.set(COOKIE_NAME, token)
        response = await client.get("/auth/login", follow_redirects=False)
        # Should show login page (not redirect to dashboard)
        assert response.status_code == 200
        assert "Sign in to EventForge" in response.text


class TestRoleBasedRedirects:
    """Tests for role-based access and redirects."""

    @pytest.mark.asyncio
    async def test_admin_can_access_admin_dashboard(
        self, admin_client: AsyncClient
    ):
        """Admin user can access /admin dashboard."""
        response = await admin_client.get("/admin", follow_redirects=False)
        assert response.status_code == 200
        assert "Admin Dashboard" in response.text

    @pytest.mark.asyncio
    async def test_organizer_cannot_access_admin_dashboard(
        self, organizer_client: AsyncClient
    ):
        """Organizer (Project Manager) cannot access /admin — gets 401/403."""
        response = await organizer_client.get("/admin", follow_redirects=False)
        # require_admin raises HTTPException with 403
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_attendee_cannot_access_admin_dashboard(
        self, attendee_client: AsyncClient
    ):
        """Attendee (Viewer) cannot access /admin — gets 401/403."""
        response = await attendee_client.get("/admin", follow_redirects=False)
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access_admin_dashboard(
        self, client: AsyncClient
    ):
        """Unauthenticated user cannot access /admin — gets 401."""
        response = await client.get("/admin", follow_redirects=False)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_organizer_can_access_organizer_dashboard(
        self, organizer_client: AsyncClient
    ):
        """Organizer (Project Manager) can access /dashboard."""
        response = await organizer_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Organizer Dashboard" in response.text

    @pytest.mark.asyncio
    async def test_admin_can_access_organizer_dashboard(
        self, admin_client: AsyncClient
    ):
        """Admin user can access /dashboard."""
        response = await admin_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 200
        assert "Organizer Dashboard" in response.text

    @pytest.mark.asyncio
    async def test_attendee_redirected_from_organizer_dashboard(
        self, attendee_client: AsyncClient
    ):
        """Attendee (Viewer) accessing /dashboard gets redirected to /events."""
        response = await attendee_client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/events" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_unauthenticated_redirected_from_dashboard(
        self, client: AsyncClient
    ):
        """Unauthenticated user accessing /dashboard gets redirected to login."""
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/auth/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_create_event(self, client: AsyncClient):
        """Unauthenticated user cannot access /events/create — gets 401."""
        response = await client.get("/events/create", follow_redirects=False)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticated_user_can_access_create_event(
        self, organizer_client: AsyncClient
    ):
        """Authenticated user can access /events/create."""
        response = await organizer_client.get("/events/create", follow_redirects=False)
        assert response.status_code == 200
        assert "Create Event" in response.text