"""
weather_report.py — MJ Live Weather

Fetches real weather data from wttr.in (free, no API key) and formats a brief
spoken + on-screen report. Falls back to opening a Google search page only if
the API call fails.
"""
from __future__ import annotations

import json
import urllib.parse


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(message)
        except Exception:
            pass


def _fetch_wttr(city: str) -> dict | None:
    """Fetch current + 3-day weather from wttr.in as JSON."""
    import urllib.request

    query = urllib.parse.quote(city)
    url = f"https://wttr.in/{query}?format=j1&lang=en"
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Weather] ⚠️ wttr.in failed: {e}")
        return None


def _fmt_conditions(desc: dict) -> str:
    text = (desc.get("weatherDesc") or [{}])
    if isinstance(text, list) and text and isinstance(text[0], dict):
        return str(text[0].get("value", "")).strip()
    return ""


def _build_report(city: str, data: dict) -> str:
    try:
        current = data["current_condition"][0]
        temp_c  = current.get("temp_C", "?")
        feels   = current.get("FeelsLikeC", temp_c)
        cond    = _fmt_conditions(current) or "unknown conditions"
        humidity = current.get("humidity", "?")
        wind_k   = current.get("windspeedKmph", "?")
        wind_dir = current.get("winddir16Point", "")

        forecast = data.get("weather", [])[:3]

        lines = [
            f"Weather in {city.title()} right now:",
            f"  {cond}, {temp_c}°C (feels like {feels}°C)",
            f"  Humidity {humidity}% · Wind {wind_k} km/h {wind_dir}",
        ]
        if forecast:
            lines.append("  Forecast:")
            for day in forecast:
                date = day.get("date", "")
                max_c = day.get("maxtempC", "?")
                min_c = day.get("mintempC", "?")
                day_cond = ""
                try:
                    day_cond = _fmt_conditions(day["hour"][0]) or ""
                except (KeyError, IndexError, TypeError):
                    pass
                lines.append(f"    {date}: {min_c}–{max_c}°C {day_cond}".rstrip())
        return "\n".join(lines)
    except (KeyError, IndexError, TypeError) as e:
        print(f"[Weather] ⚠️ Parse error: {e}")
        return None


def _open_browser_search(city: str, when: str) -> str:
    import webbrowser

    query = f"weather in {city} {when}"
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
    try:
        if webbrowser.open(url):
            return f"Opened the weather page for {city} in your browser."
    except Exception as e:
        return f"Could not open browser for weather: {e}"
    return f"Could not open browser for weather in {city}."


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    city = parameters.get("city") if isinstance(parameters, dict) else None
    when = parameters.get("time", "today")

    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()
    when = (when or "today").strip()

    if player:
        player.write_log(f"[Weather] Fetching live weather for {city}…")

    data = _fetch_wttr(city)
    report = _build_report(city, data) if data else None

    if report:
        _log(f"{city}: live weather delivered", player)
        if session_memory:
            try:
                session_memory.set_last_search(
                    query=f"weather in {city} {when}", response=report
                )
            except Exception:
                pass
        return report

    # Fallback — keep old behaviour only when the API is unreachable
    return _open_browser_search(city, when)
