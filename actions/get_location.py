"""
JARVIS Action: Get or pinpoint real-time geographical location and coordinates of the workstation.
"""
from core.location import get_cached_or_fresh_location, pinpoint_location

TOOL_DECLARATION = {
    "name": "get_current_location",
    "description": (
        "Get or pinpoint the user's real geographical location, city, state, country, "
        "and precise latitude and longitude GPS coordinates. "
        "If the user specifies a location (e.g. 'I am in Assagao', 'set my location to Mapusa', "
        "'locate me at AITD'), pass it in 'set_location' to pinpoint coordinates and update the tactical map."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "set_location": {
                "type": "STRING",
                "description": "Optional location name, village, landmark, or city to pinpoint and update on the tactical map."
            }
        },
    },
}

def get_current_location(parameters: dict = None, player=None, session_memory=None) -> str:
    params = parameters or {}
    query = (params.get("set_location") or params.get("query") or "").strip()
    
    if query:
        loc = pinpoint_location(query)
        city = loc.get("city", query)
        region = loc.get("region", "Goa")
        lat = loc.get("lat", 15.5981)
        lon = loc.get("lon", 73.7722)
        if player:
            player.write_log(f"[GPS] Location pinpointed: {city.upper()}, {region.upper()} ({lat:.4f} N, {lon:.4f} E)")
        return (
            f"Location updated and pinpointed to: {city}, {region}, India\n"
            f"Exact GPS Coordinates: {lat:.4f}° N, {lon:.4f}° E\n"
            f"Tactical street map refreshed."
        )

    loc = get_cached_or_fresh_location()
    city = loc.get("city", "Assagao")
    region = loc.get("region", "Goa")
    country = loc.get("country", "India")
    lat = loc.get("lat", 15.5981)
    lon = loc.get("lon", 73.7722)
    coords_str = loc.get("coords_str", f"{lat:.4f}° N, {lon:.4f}° E")
    
    return (
        f"Location: {city}, {region}, {country}\n"
        f"Coordinates: {coords_str}\n"
        f"Map URL: {loc.get('map_url', '')}"
    )
