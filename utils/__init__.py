import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    COOKIE_NAME,
)
from utils.dependencies import (
    get_db,
    get_current_user,
    require_auth,
    require_role,
    require_admin,
    require_organizer,
    require_attendee,
)