"""core/location.py — Real location detection, map generation, and local news coordination.

Automatically resolves user location via IP geolocation, fetches real map tile
and coordinates, and provides real map links and Indian local state news context.
"""
from __future__ import annotations

import io
import json
import math
import os
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
LOC_FILE = CONFIG_DIR / "location.json"
MAP_FILE = CONFIG_DIR / "tactical_map.png"

_cached_loc: dict | None = None
_loc_lock = threading.Lock()


def fetch_tactical_tiles(lat: float, lon: float, zoom: int = 14) -> bool:
    """Download 2x2 grid of CartoDB Dark Matter tiles centered on coords and save to tactical_map.png."""
    try:
        from PIL import Image
    except ImportError:
        return False

    try:
        n = 2.0 ** zoom
        xc = (lon + 180.0) / 360.0 * n
        yc = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
        x0, y0 = int(xc), int(yc)

        canvas = Image.new("RGB", (512, 512), (18, 10, 2))
        for dx in range(2):
            for dy in range(2):
                tx = x0 + dx
                ty = y0 + dy
                url = f"https://a.basemaps.cartocdn.com/dark_all/{zoom}/{tx}/{ty}.png"
                req = urllib.request.Request(url, headers={"User-Agent": "JarvisMark2/2.0"})
                with urllib.request.urlopen(req, timeout=3.5) as resp:
                    tile = Image.open(io.BytesIO(resp.read()))
                    canvas.paste(tile, (dx * 256, dy * 256))

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        canvas.save(str(MAP_FILE))
        print(f"[location] Tactical map tile updated for ({lat:.4f}, {lon:.4f}) -> {MAP_FILE}")
        return True
    except Exception as e:
        print(f"[location] could not fetch tactical tiles: {e}")
        return False


def pinpoint_location(query: str, save: bool = True) -> dict:
    """Geocode query via OpenStreetMap Nominatim, download tactical map, and update location."""
    global _cached_loc
    clean_q = query.strip()
    # Add Goa, India context if query is a local village or town
    full_q = clean_q
    if "goa" not in clean_q.lower() and "india" not in clean_q.lower():
        full_q = f"{clean_q}, Goa, India"

    encoded = urllib.parse.quote(full_q)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "JarvisMark2/2.0"})
    
    loc = None
    try:
        with urllib.request.urlopen(req, timeout=4.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, list):
                top = data[0]
                lat = float(top["lat"])
                lon = float(top["lon"])
                disp = top.get("display_name", "")
                parts = [p.strip() for p in disp.split(",")]
                city = parts[0] if parts else clean_q
                region = "Goa" if "Goa" in disp else (parts[1] if len(parts) > 1 else "India")
                
                loc = {
                    "city": city,
                    "region": region,
                    "country": "India",
                    "lat": lat,
                    "lon": lon,
                    "display_name": disp,
                    "pinned": True,
                }
    except Exception as e:
        print(f"[location] Nominatim geocode error: {e}")

    if not loc:
        loc = {
            "city": clean_q,
            "region": "Goa",
            "country": "India",
            "lat": 15.4957,
            "lon": 73.8262,
            "display_name": f"{clean_q}, Goa, India",
            "pinned": True,
        }

    lat, lon = loc["lat"], loc["lon"]
    loc["map_url"] = f"https://www.google.com/maps/@{lat:.5f},{lon:.5f},15z"
    loc["label"] = f"{loc['city'].upper()}, {loc['region'].upper()}"
    loc["coords_str"] = f"{abs(lat):.4f}° {'N' if lat>=0 else 'S'}, {abs(lon):.4f}° {'E' if lon>=0 else 'W'}"

    # Asynchronously or synchronously update tactical map tile
    fetch_tactical_tiles(lat, lon, zoom=14)

    if save:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            LOC_FILE.write_text(json.dumps(loc, indent=2), encoding="utf-8")
        except Exception:
            pass

    with _loc_lock:
        _cached_loc = loc

    return loc


def get_location(refresh: bool = False) -> dict:
    """Return dict with city, region, country, lat, lon, and map_url.

    Defaults to user's real detected location, with graceful offline fallback.
    """
    global _cached_loc
    with _loc_lock:
        if _cached_loc and not refresh:
            return _cached_loc

        # Try reading saved cache
        if LOC_FILE.exists():
            try:
                saved = json.loads(LOC_FILE.read_text(encoding="utf-8"))
                if saved.get("pinned") or not refresh:
                    _cached_loc = saved
                    return _cached_loc
            except Exception:
                pass

        # Default to user's real base location (Panjim, Goa)
        loc = {
            "city": "Panjim",
            "region": "Goa",
            "country": "India",
            "lat": 15.4957,
            "lon": 73.8262,
            "isp": "",
            "pinned": False,
        }

        try:
            req = urllib.request.Request(
                "http://ip-api.com/json/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Jarvis/2.0"},
            )
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "success":
                    loc["city"] = data.get("city") or loc["city"]
                    loc["region"] = data.get("regionName") or loc["region"]
                    loc["country"] = data.get("country") or loc["country"]
                    loc["lat"] = float(data.get("lat", loc["lat"]))
                    loc["lon"] = float(data.get("lon", loc["lon"]))
                    loc["isp"] = data.get("isp") or ""
        except Exception:
            try:
                req2 = urllib.request.Request(
                    "https://ipinfo.io/json",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                with urllib.request.urlopen(req2, timeout=3.5) as resp2:
                    d2 = json.loads(resp2.read().decode("utf-8"))
                    loc["city"] = d2.get("city") or loc["city"]
                    loc["region"] = d2.get("region") or loc["region"]
                    if d2.get("loc"):
                        plat, plon = map(float, d2["loc"].split(","))
                        loc["lat"], loc["lon"] = plat, plon
                    loc["isp"] = d2.get("org") or ""
            except Exception:
                pass

        lat, lon = loc["lat"], loc["lon"]
        loc["map_url"] = f"https://www.google.com/maps/@{lat:.4f},{lon:.4f},14z"
        loc["label"] = f"{loc['city'].upper()}, {loc['region'].upper()}"
        loc["coords_str"] = f"{abs(lat):.4f}° {'N' if lat>=0 else 'S'}, {abs(lon):.4f}° {'E' if lon>=0 else 'W'}"

        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            LOC_FILE.write_text(json.dumps(loc, indent=2), encoding="utf-8")
        except Exception:
            pass

        # If tactical map tile doesn't exist, generate it
        if not MAP_FILE.exists():
            fetch_tactical_tiles(lat, lon, zoom=14)

        _cached_loc = loc
        return loc


def open_live_map(lat: float | None = None, lon: float | None = None) -> None:
    """Open interactive map centered at detected or panned coordinates in user's browser."""
    loc = get_location()
    cur_lat = lat if lat is not None else loc.get("lat", 15.5016)
    cur_lon = lon if lon is not None else loc.get("lon", 73.8234)
    url = f"https://www.google.com/maps/@{cur_lat:.5f},{cur_lon:.5f},15z"
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[location] could not open map: {e}")


def get_news_query_for_location() -> str:
    """Return tailored news query for user's Indian state and location."""
    loc = get_location()
    region = loc.get("region", "India")
    city = loc.get("city", "")
    return f"{city} {region} latest news India"


get_cached_or_fresh_location = get_location
