"""
JARVIS Action: Get or pinpoint real-time geographical location and coordinates of the workstation.
"""
from core.location import get_location, pinpoint_location

def get_current_location(parameters: dict = None, player=None, session_memory=None) -> str:
    params = parameters or {}
    query = (params.get("set_location") or params.get("query") or "").strip()
    refresh = bool(params.get("refresh", False) or params.get("force_live", False))
    
    if query:
        loc = pinpoint_location(query)
        city = loc.get("city", query)
        region = loc.get("region", "Goa")
        lat = loc.get("lat", 15.4957)
        lon = loc.get("lon", 73.8262)
        if player:
            player.write_log(f"[GPS] Location pinpointed: {city.upper()}, {region.upper()} ({lat:.4f}° N, {lon:.4f}° E)")
        return (
            f"Workstation location updated and pinpointed to: {city}, {region}, India\n"
            f"GPS Coordinates: {lat:.4f}° N, {lon:.4f}° E\n"
            f"Tactical map updated."
        )

    # Fetch live workstation network IP geolocation
    loc = get_location(refresh=refresh or True, force_live=refresh)
    city = loc.get("city", "Panjim")
    region = loc.get("region", "Goa")
    country = loc.get("country", "India")
    lat = loc.get("lat", 15.5016)
    lon = loc.get("lon", 73.8234)
    coords_str = loc.get("coords_str", f"{abs(lat):.4f}° {'N' if lat>=0 else 'S'}, {abs(lon):.4f}° {'E' if lon>=0 else 'W'}")
    isp = loc.get("isp", "")
    isp_info = f"\nNetwork / ISP: {isp}" if isp else ""
    
    if player:
        player.write_log(f"[GPS] Workstation Location: {city.upper()}, {region.upper()} ({coords_str})")
        
    return (
        f"Workstation Location: {city}, {region}, {country}\n"
        f"GPS Coordinates: {coords_str}{isp_info}\n"
        f"Map URL: {loc.get('map_url', '')}"
    )

TOOL = {
    "name": "get_current_location",
    "description": (
        "Get or refresh the user's real live geographical location, city, state, country, "
        "ISP network, and precise GPS latitude and longitude coordinates of this workstation. "
        "Call this whenever the user asks where they are, what their location is, or to detect/update location. "
        "If the user specifies a place to set (e.g. 'I am in Assagao', 'set my location to Mapusa', 'locate me at AITD'), "
        "pass it in 'set_location' to pinpoint coordinates and update the tactical map."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "set_location": {
                "type": "STRING",
                "description": "Optional location name, village, landmark, or city to pinpoint and update on the tactical map."
            },
            "refresh": {
                "type": "BOOLEAN",
                "description": "True to force a live network IP geolocation check from the workstation."
            }
        },
    },
    "handler": get_current_location,
}
