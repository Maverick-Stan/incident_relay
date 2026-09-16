DEMO_PROFILE_COLORS = {
    "alex.morgan@calendar.com": {"profile": "#1a73e8", "work": "#0b8043", "Birthdays": "#c5221f"},
    "jordan.smith@calendar.com": {"profile": "#b85c00", "work": "#3f51b5"},
    "taylor.johnson@calendar.com": {"profile": "#c2185b", "work": "#00796b"},
    "riley.parker@calendar.com": {"profile": "#00796b", "work": "#795548"},
    "casey.bennett@calendar.com": {"profile": "#7b1fa2", "work": "#b85c00"},
}

FALLBACK_COLOR = "#5f6368"


def demo_color_for(email, calendar="profile"):
    palette = DEMO_PROFILE_COLORS.get(email, {})

    return palette.get(calendar) or palette.get("profile") or FALLBACK_COLOR
