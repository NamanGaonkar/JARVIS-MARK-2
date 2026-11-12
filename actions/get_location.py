"""
JARVIS Action: Get real-time geographical location and coordinates of the workstation.
"""
from core.location import get_cached_or_fresh_location

TOOL_DECLARATION = {
    "name": "get_current_location",
    "description": (
        "Get the user's real geographical location, city, state, country, "
        "and precise latitude and longitude GPS coordinates."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {},
    },
}

def get_current_location(parameters: dict = None, player=None, session_memory=None) -> str:
    loc = get_cached_or_fresh_location()
    city = loc.get("city", "Unknown City")
    region = loc.get("region", "Unknown Region")
    country = loc.get("country", "Unknown Country")
    lat = loc.get("lat", 0.0)
    lon = loc.get("lon", 0.0)
    tz = loc.get("timezone", "UTC")
    
    return (
        f"Location: {city}, {region}, {country}\n"
        f"Coordinates: {lat}° N, {lon}° E\n"
        f"Timezone: {tz}"
    )
