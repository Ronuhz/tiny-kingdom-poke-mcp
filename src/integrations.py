from typing import Optional, Tuple

import httpx
from urllib.parse import urlencode

from config import GIPHY_API_KEY


async def fetch_weather_summary(city: str) -> Optional[str]:
    """Use Open-Meteo geocoding + forecast to get a compact weather summary for today.
    Returns a short natural-language summary or None on failure.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        # geocode city lat/lon
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
        )
        if geo.status_code != 200:
            return None
        g = geo.json()
        results = (g or {}).get("results") or []
        if not results:
            return None
        r0 = results[0]
        lat, lon = r0.get("latitude"), r0.get("longitude")
        if lat is None or lon is None:
            return None

        # fetch current weather
        wx = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
        )
        if wx.status_code != 200:
            return None
        w = wx.json()
        cw = (w or {}).get("current_weather") or {}
        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        code = cw.get("weathercode")

        # code-to-text mapping
        code_text = {
            0: "clear",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "foggy",
            48: "rime fog",
            51: "light drizzle",
            61: "light rain",
            63: "rain",
            65: "heavy rain",
            71: "light snow",
            73: "snow",
            75: "heavy snow",
            95: "thunderstorms",
        }.get(int(code) if code is not None else -1, "unknown weather")

        parts = []
        if temp is not None:
            parts.append(f"{temp}°C")
        parts.append(code_text)
        if wind is not None:
            parts.append(f"wind {wind} km/h")
        return ", ".join(parts)


async def fetch_weather_by_coords(lat: float, lon: float) -> Optional[str]:
    async with httpx.AsyncClient(timeout=10) as client:
        wx = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
        )
        if wx.status_code != 200:
            return None
        w = wx.json()
        cw = (w or {}).get("current_weather") or {}
        temp = cw.get("temperature")
        wind = cw.get("windspeed")
        code = cw.get("weathercode")
        code_text = {
            0: "clear",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "foggy",
            48: "rime fog",
            51: "light drizzle",
            61: "light rain",
            63: "rain",
            65: "heavy rain",
            71: "light snow",
            73: "snow",
            75: "heavy snow",
            95: "thunderstorms",
        }.get(int(code) if code is not None else -1, "unknown weather")
        parts = []
        if temp is not None:
            parts.append(f"{temp}°C")
        parts.append(code_text)
        if wind is not None:
            parts.append(f"wind {wind} km/h")
        return ", ".join(parts)


async def fetch_trending_news_summary() -> Optional[str]:
    """Fetch a very short general headline summary via Wikipedia's trending changes.
    It's free and avoids API keys; content is generic but works as a novelty context.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(
            "https://en.wikipedia.org/api/rest_v1/feed/featured/2025/09/13"
        )
        if res.status_code != 200:
            return None
        data = res.json() or {}
        tfa = (data.get("tfa") or {}).get("title")
        onthisday = data.get("onthisday") or []
        blurb = None
        if tfa:
            blurb = f"Today's featured article: {tfa}"
        elif onthisday:
            e = onthisday[0]
            year = e.get("year")
            text = e.get("text")
            if year and text:
                blurb = f"On this day in {year}: {text}"
        return blurb


async def fetch_media_url(query: str) -> Optional[str]:
    """Return a URL to a GIF or image suitable for lightweight linking.
    Tries Giphy (if key available), then Wikimedia Commons as a fallback.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        # try Giphy first if key is present
        if GIPHY_API_KEY:
            params = {"api_key": GIPHY_API_KEY, "q": query, "limit": 1, "rating": "g", "lang": "en"}
            res = await client.get("https://api.giphy.com/v1/gifs/search", params=params)
            if res.status_code == 200:
                data = res.json() or {}
                items = data.get("data") or []
                if items:
                    gif = items[0]
                    # prefer downsized or original URL
                    images = gif.get("images") or {}
                    for key in ["downsized_medium", "downsized", "original"]:
                        url = (images.get(key) or {}).get("url")
                        if url:
                            return url

        # next try Openverse 
        ov = await client.get(
            "https://api.openverse.engineering/v1/images/",
            params={"q": query, "page_size": 1, "format": "json"},
            headers={"User-Agent": "tiny-kingdom-mcp/1.0"},
        )
        if ov.status_code == 200:
            o = ov.json() or {}
            results = o.get("results") or []
            if results:
                item = results[0]
                # prefer direct image URL; fallback to thumbnail
                for key in ["url", "thumbnail"]:
                    val = item.get(key)
                    if isinstance(val, str) and val.startswith("http"):
                        return val

        # fallback: Wikimedia Commons search
        # use MediaWiki Opensearch-like endpoint via Commons API
        res = await client.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": 6,  # file namespace
                "gsrlimit": 1,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 800,
            },
        )
        if res.status_code == 200:
            j = res.json() or {}
            pages = (j.get("query") or {}).get("pages") or {}
            for _, page in pages.items():
                info = (page.get("imageinfo") or [])
                if info:
                    return info[0].get("thumburl") or info[0].get("url")

    return None


