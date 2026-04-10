import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.auth_service import (
    register_user,
    authenticate_user,
    get_user_by_id,
    get_user_by_username,
    get_user_by_email,
)
from services.event_service import (
    create_event,
    edit_event,
    delete_event,
    get_event,
    search_events,
    get_events_by_organizer,
    update_event_status,
    get_event_attendees,
    get_event_stats,
    get_all_categories,
)
from services.rsvp_service import (
    set_rsvp,
    get_rsvp_counts,
    get_user_rsvp,
    delete_rsvp,
    get_event_rsvps,
)
from services.ticket_service import (
    claim_ticket,
    get_ticket_availability,
    get_user_tickets,
    cancel_ticket,
    get_ticket_by_id,
    get_event_tickets,
    get_total_tickets_sold,
    get_total_revenue,
    toggle_checkin,
)