import os
import json
import datetime

# Resolve DATA_DIR cleanly for local, container, or package execution
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.getenv("DATA_DIR", os.path.join(_CURRENT_DIR, "data"))

MEMBERS_FILE = os.path.join(DATA_DIR, "team_members.json")
BOOKINGS_FILE = os.path.join(DATA_DIR, "booked_meetings.json")


def ensure_bookings_file() -> None:
    """Ensures that the booked_meetings.json file and its parent directory exist on the fly."""
    os.makedirs(os.path.dirname(BOOKINGS_FILE), exist_ok=True)
    if not os.path.exists(BOOKINGS_FILE):
        try:
            with open(BOOKINGS_FILE, "w") as f:
                json.dump([], f, indent=2)
        except Exception as e:
            print(f"[Scheduling Agent] Error initializing {BOOKINGS_FILE}: {e}")


def get_team_members() -> list[dict]:
    """Loads and returns the team members' profiles, schedules, and preferences.

    This lists each member's timezone, weekly availability slots, dietary restrictions,
    and preferred cuisines.
    """
    print("[Scheduling Agent] Fetching team members profiles...")
    try:
        if os.path.exists(MEMBERS_FILE):
            with open(MEMBERS_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"[Scheduling Agent] Error reading {MEMBERS_FILE}: {e}")
        return []


def book_meeting(time_slot: str, restaurant: str, reason: str = "") -> str:
    """Appends a new meeting booking to the central system to finalize a slot and catering choice.

    Args:
        time_slot: The day and time range of the confirmed meeting, e.g., "Monday 10:00-11:00".
        restaurant: The name of the selected restaurant for catering, e.g., "Fiesta Tacos".
        reason: Optional brief reason/summary for selecting this choice.
    """
    print(f"[Scheduling Agent] Finalizing booking: {time_slot} with catering from {restaurant}...")
    try:
        ensure_bookings_file()
        bookings = []
        if os.path.exists(BOOKINGS_FILE):
            with open(BOOKINGS_FILE, "r") as f:
                try:
                    bookings = json.load(f)
                except json.JSONDecodeError:
                    bookings = []

        new_booking = {
            "booking_id": f"bk_{int(datetime.datetime.now().timestamp())}",
            "time_slot": time_slot,
            "catering_restaurant": restaurant,
            "reason": reason,
            "booked_at": datetime.datetime.now().isoformat()
        }
        bookings.append(new_booking)

        with open(BOOKINGS_FILE, "w") as f:
            json.dump(bookings, f, indent=2)

        return f"Successfully booked! Meeting scheduled for {time_slot} with catering from {restaurant}. Booking ID: {new_booking['booking_id']}."
    except Exception as e:
        return f"Failed to book meeting: {str(e)}"


def update_team_member_preferences(
    name: str, 
    preferred_time_of_day: str | None = None, 
    dietary_restrictions: list[str] | None = None, 
    cuisine_preferences: list[str] | None = None
) -> str:
    """Updates a team member's preferred meeting times and food preferences in the central registry.
    
    This acts as the agent's central long-term memory, ensuring the updated preferences 
    persist and are automatically applied to all future meeting scheduling requests.

    Args:
        name: Name of the team member to update (e.g. "Alice", "Bob").
        preferred_time_of_day: New preferred meeting time window (e.g., "morning", "afternoon").
        dietary_restrictions: Updated list of dietary restrictions (e.g., ["Vegan", "Gluten-Free"]).
        cuisine_preferences: Updated list of preferred cuisines (e.g., ["Mexican", "Asian"]).
    """
    print(f"[Scheduling Agent] Updating long-term preferences database for team member: {name}...")
    try:
        members = get_team_members()
        updated = False
        for member in members:
            if member["name"].strip().lower() == name.strip().lower():
                if preferred_time_of_day is not None:
                    member["preferred_time_of_day"] = preferred_time_of_day
                if dietary_restrictions is not None:
                    member["dietary_restrictions"] = dietary_restrictions
                if cuisine_preferences is not None:
                    member["cuisine_preferences"] = cuisine_preferences
                updated = True
                break

        if not updated:
            return f"Team member '{name}' not found in the database. No updates made."

        os.makedirs(os.path.dirname(MEMBERS_FILE), exist_ok=True)
        with open(MEMBERS_FILE, "w") as f:
            json.dump(members, f, indent=2)

        return f"Successfully updated central database preferences for {name}. These preferences are now saved permanently in long-term memory."
    except Exception as e:
        return f"Failed to update team member preferences: {str(e)}"
