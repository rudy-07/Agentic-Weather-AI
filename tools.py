import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
try:
    import pdfplumber
except ImportError:
    pdfplumber = None
from bs4 import BeautifulSoup
import io
import json
import csv
import os
from pathlib import Path

# --- Module-level location cache so master.csv is only read once ---
_LOCATION_CACHE: list = []
_LOCATION_CACHE_LOADED: bool = False

def _get_retry_session(retries: int = 3, backoff: float = 0.5) -> requests.Session:
    """Return a requests Session with automatic retry+backoff on transient errors."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

_HTTP = _get_retry_session()
try:
    from langchain.tools import tool
except ImportError:
    class _SimpleTool:
        def __init__(self, func):
            self.func = func
            self.__name__ = getattr(func, "__name__", self.__class__.__name__)

        def __call__(self, *args, **kwargs):
            return self.func(*args, **kwargs)

        def invoke(self, value):
            if isinstance(value, dict):
                return self.func(**value)
            return self.func(value)

    def tool(func):
        return _SimpleTool(func)
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

IMD_PRESS_URL = "https://internal.imd.gov.in/pages/press_release_mausam.php"
LOCATION_FILE = Path(__file__).with_name("master.csv")
MAUSAMGRAM_ENDPOINTS = {
    "1hr": "https://mausamgram.imd.gov.in/nwp/api/GetHourlyData",
    "3hr": "https://mausamgram.imd.gov.in/nwp/api/GetHourlyData",
    "6hr": "https://mausamgram.imd.gov.in/nwp/api/GetHourlyData",
    "daily": "https://mausamgram.imd.gov.in/nwpapi/get-daily",
}
MAUSAMGRAM_HOURLY_STEPS = {"1hr": 1, "3hr": 3, "6hr": 6}

# A set of Indian states and UTs for precise state name identification.
INDIAN_STATES_UT = {
    "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM", "BIHAR", "CHHATTISGARH", "GOA",
    "GUJARAT REGION", "SAURASHTRA & KUTCH", "HARYANA", "HIMACHAL PRADESH", "JHARKHAND", "KARNATAKA",
    "KERALA", "MADHYA PRADESH", "MAHARASHTRA", "MANIPUR", "MEGHALAYA", "MIZORAM",
    "NAGALAND", "ODISHA", "PUNJAB", "RAJASTHAN", "SIKKIM", "TAMIL NADU",
    "TELANGANA", "TRIPURA", "UTTAR PRADESH", "UTTARAKHAND", "WEST BENGAL",
    "ANDAMAN & NICOBAR ISLANDS", "CHANDIGARH", "DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
    "DELHI", "JAMMU & KASHMIR", "LADAKH", "LAKSHADWEEP", "PUDUCHERRY",
    "KONKAN & GOA", "MADHYA MAHARASHTRA", "MARATHAWADA", "VIDARBHA",
    "COASTAL ANDHRA PRADESH & YANAM", "RAYALASEEMA", "COASTAL KARNATAKA",
    "NORTH INTERIOR KARNATAKA", "SOUTH INTERIOR KARNATAKA", "GANGETIC WEST BENGAL",
    "SUB-HIMALAYAN WEST BENGAL & SIKKIM", "EAST RAJASTHAN", "WEST RAJASTHAN",
    "EAST UTTAR PRADESH", "WEST UTTAR PRADESH", "EAST MADHYA PRADESH", "WEST MADHYA PRADESH",
    "NAGALAND, MANIPUR, MIZORAM & TRIPURA", "TAMIL NADU, PUDUCHERRY & KARAIKAL",
    "ASSAM & MEGHALAYA"
}

# --- Helper function to parse the messy rainfall data string ---
def _parse_rainfall_data_string(text: str) -> List[Dict]:
    """Parses strings like 'State: Location (dist District) 22; ...' into structured data."""
    data_points = []
    pattern = re.compile(r"([\w\s.-]+?)\s+\(dist\s+([\w\s.-]+?)\)\s+([0-9]+)")
    lines = text.split('\n')
    current_state = "Unknown"

    for line in lines:
        cleaned_line = line.strip()
        potential_state_match = re.match(r'^\s*([^:]+):', line)
        if potential_state_match:
            potential_state = potential_state_match.group(1).strip().upper()
            if potential_state in INDIAN_STATES_UT:
                current_state = potential_state.title()

        entries = line.split(';')
        for entry in entries:
            match = pattern.search(entry)
            if match:
                data_points.append({
                    "state": current_state,
                    "location": match.group(1).strip(),
                    "district": match.group(2).strip(),
                    "rainfall_cm": int(match.group(3))
                })
    return data_points

# --- Helper function to parse a standard forecast bulletin ---
def _parse_forecast_bulletin(text: str, url: str) -> Dict:
    data = {"source_url": url, "document_type": "Daily Forecast Bulletin"}
    headers = {"Forecast", "Weather Forecast", "Rainfall Warnings", "Warning", "Action Suggested", "Impact Expected"}
    lines = text.split('\n')
    current_section = None
    for line in lines:
        stripped_line = line.strip()
        if stripped_line in headers and len(stripped_line) < 30:
            current_section = stripped_line.lower().replace(' ', '_')
            data.setdefault(current_section, "")
        elif current_section:
            data[current_section] += stripped_line + " "
    data["rainfall_data_points"] = _parse_rainfall_data_string(text)
    return data

# --- Helper function to parse a weekly summary report ---
def _parse_weekly_summary(tables: list, url: str) -> Dict:
    data = {"source_url": url, "document_type": "Weekly Rainfall Summary", "summary_data": []}
    for table in tables:
        if table and 'THE COUNTRY AS A WHOLE' in str(table):
            headers = ["region", "actual_mm_week", "normal_mm_week", "departure_percent_week", "actual_mm_season", "normal_mm_season", "departure_percent_season"]
            for row in table[2:]:
                row_data = [item.replace('\n', ' ') if item else '' for item in row]
                if len(row_data) == len(headers):
                    data["summary_data"].append(dict(zip(headers, row_data)))
            break
    return data

# --- Helper function for the simple rainfall data log ---
def _parse_rainfall_log(tables: list, url: str) -> Dict:
    data = {"source_url": url, "document_type": "Rainfall Observation Log", "rainfall_log": []}
    if tables:
        for table in tables:
            if table and len(table[0]) == 3 and 'Time (IST)' in table[0][1]:
                for row in table[1:]:
                    if len(row) == 3:
                        try:
                            rainfall = float(row[2]) if row[2] else 0.0
                            data["rainfall_log"].append({"date": row[0], "time_ist": row[1], "rainfall_mm": rainfall})
                        except (ValueError, TypeError):
                            continue
    return data

@tool
def scrape_imd_press_release_urls(query: str = "") -> str:
    """
    Finds and returns a JSON list of URLs for all English IMD press release
    PDFs published within the last 7 days, using a precise language filter.

    The optional query argument is intentionally ignored. It keeps this tool
    compatible with ReAct agents that cannot safely call zero-argument tools.
    """
    try:
        response = requests.get(IMD_PRESS_URL, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_urls = []
        english_keywords = ['press release', 'weather', 'low pressure', 'rainfall', 'cyclone']
        hindi_keyword = "\u092a\u094d\u0930\u0947\u0938 \u0935\u093f\u091c\u094d\u091e\u092a\u094d\u0924\u093f"
        for tr in soup.find_all('tr'):
            cells = tr.find_all('td')
            if len(cells) >= 5:
                date_str = cells[2].get_text().strip()
                subject_str = cells[3].get_text().strip()
                link_cell = cells[4]
                subject_lower = subject_str.lower()
                is_english = any(keyword in subject_lower for keyword in english_keywords)
                is_hindi = hindi_keyword in subject_str
                if is_english and not is_hindi:
                    try:
                        press_release_date = datetime.strptime(date_str, '%d %b %Y')
                        if press_release_date >= seven_days_ago:
                            pdf_link = link_cell.find('a', href=lambda href: href and href.lower().endswith('.pdf'))
                            if pdf_link:
                                full_url = requests.compat.urljoin(IMD_PRESS_URL, pdf_link['href'])
                                recent_urls.append(full_url)
                    except ValueError:
                        continue
        deduped_urls = []
        seen_urls = set()
        for url in recent_urls:
            if url not in seen_urls:
                deduped_urls.append(url)
                seen_urls.add(url)

        if not deduped_urls:
            return "No English press releases found for the last 7 days."
        return json.dumps(deduped_urls)
    except Exception as e:
        return f"An unexpected error occurred during scraping: {e}"

def _coerce_url_list(urls: Any) -> List[str]:
    """Accept agent/tool input as a list, JSON string, or {"urls": [...]}."""
    if isinstance(urls, str):
        stripped = urls.strip()
        if not stripped:
            return []
        try:
            urls = json.loads(stripped)
        except json.JSONDecodeError:
            return [stripped] if stripped.startswith(("http://", "https://")) else []

    if isinstance(urls, dict):
        urls = urls.get("urls", [])

    if isinstance(urls, list):
        return [str(url).strip() for url in urls if str(url).strip()]

    return []

def _normalize_location_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

def _load_locations(location_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    global _LOCATION_CACHE, _LOCATION_CACHE_LOADED
    # Use module-level cache for default file; always reload when a custom file is given
    if location_file is None and _LOCATION_CACHE_LOADED:
        return _LOCATION_CACHE

    path = location_file or LOCATION_FILE
    if not path.exists():
        return []

    locations = []
    if path.suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data = data.get("locations", [])
        locations = data if isinstance(data, list) else []
    else:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("cityname") and row.get("lat") and row.get("lon"):
                    try:
                        locations.append({
                            "name": row["cityname"].strip(),
                            "state": "",
                            "lat": float(row["lat"]),
                            "lon": float(row["lon"]),
                            "source": path.name
                        })
                    except ValueError:
                        continue

    if location_file is None:
        _LOCATION_CACHE = locations
        _LOCATION_CACHE_LOADED = True
    return locations

def list_known_locations(location_file: Optional[Path] = None) -> List[str]:
    locations = _load_locations(location_file)
    return sorted(str(item.get("name", "")).strip() for item in locations if item.get("name"))

def resolve_location(
    place: Optional[str] = None,
    lat: Optional[Any] = None,
    lon: Optional[Any] = None,
    location_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Resolve either direct lat/lon or a known place name from locations.json.
    Direct coordinates are preferred because the Mausamgram API is grid based.
    """
    if lat is not None and lon is not None and str(lat).strip() and str(lon).strip():
        try:
            latitude = float(lat)
            longitude = float(lon)
        except (TypeError, ValueError) as exc:
            raise ValueError("Latitude and longitude must be numeric.") from exc
        if not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90.")
        if not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180.")
        return {
            "name": place or f"{latitude:.4f},{longitude:.4f}",
            "lat": latitude,
            "lon": longitude,
            "source": "coordinates",
        }

    if not place or not str(place).strip():
        raise ValueError("Provide either a place name or latitude and longitude.")

    wanted = _normalize_location_key(str(place))
    for item in _load_locations(location_file):
        names = [item.get("name", ""), item.get("state", "")]
        names.extend(item.get("aliases", []) or [])
        if wanted in {_normalize_location_key(str(name)) for name in names if name}:
            return {
                "name": item.get("name"),
                "state": item.get("state"),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "source": item.get("source", "locations.json"),
            }

    # Fallback to OpenStreetMap Nominatim API for dynamic geocoding of unknown places
    try:
        geocode_url = "https://nominatim.openstreetmap.org/search"
        params = {"q": f"{place}, India", "format": "json", "limit": 1}
        headers = {"User-Agent": "AgenticWeatherBot/1.0"}
        resp = _HTTP.get(geocode_url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                return {
                    "name": place.title(),
                    "state": "",
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "source": "nominatim_geocoding",
                }
    except Exception:
        pass  # Silently fall through to the ValueError below if geocoding fails

    known = ", ".join(list_known_locations(location_file)[:20])
    suffix = f" Known locations include: {known}." if known else ""
    raise ValueError(f"Unknown place '{place}'. Please enter latitude and longitude.{suffix}")

def _normalize_forecast_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower().replace("_", "").replace("-", "")
    aliases = {
        "1": "1hr",
        "1h": "1hr",
        "1hr": "1hr",
        "hourly": "1hr",
        "3": "3hr",
        "3h": "3hr",
        "3hr": "3hr",
        "6": "6hr",
        "6h": "6hr",
        "6hr": "6hr",
        "day": "daily",
        "daily": "daily",
    }
    if normalized not in aliases:
        raise ValueError("Forecast mode must be one of: 1hr, 3hr, 6hr, daily.")
    return aliases[normalized]

def _get_mausamgram_credentials() -> Dict[str, str]:
    user = os.getenv("MAUSAMGRAM_USER", "").strip()
    key = os.getenv("MAUSAMGRAM_KEY", "").strip()
    if not user or not key:
        raise ValueError("Set MAUSAMGRAM_USER and MAUSAMGRAM_KEY in the environment or .env file.")
    return {"user": user, "key": key}

def _build_mausamgram_hourly_payload(lat: float, lon: float, mode: str) -> Dict[str, Any]:
    payload = {
        os.getenv("MAUSAMGRAM_LAT_FIELD", "lat"): lat,
        os.getenv("MAUSAMGRAM_LON_FIELD", "lon"): lon,
        os.getenv("MAUSAMGRAM_HOURLY_FIELD", "hourly"): MAUSAMGRAM_HOURLY_STEPS[mode],
    }
    optional_date = os.getenv("MAUSAMGRAM_DATE", "").strip()
    if optional_date:
        payload[os.getenv("MAUSAMGRAM_DATE_FIELD", "date")] = optional_date
    return payload

def _coerce_forecast_records(parsed: Any) -> List[Any]:
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("data", "forecast", "forecasts", "records", "result", "results"):
            value = parsed.get(key)
            if isinstance(value, list):
                return value
        return [parsed]
    return []

def _summarise_daily_records(raw_parsed: Any, place_name: str) -> str:
    """
    Convert the raw Mausamgram daily JSON into a compact, human-readable text
    summary that fits comfortably within the LLM context window.
    """
    lines = [f"5-day forecast for {place_name}:"]
    if not isinstance(raw_parsed, dict):
        return "No forecast data available."
    for key in ("fcstday1", "fcstday2", "fcstday3", "fcstday4", "fcstday5"):
        day = raw_parsed.get(key)
        if not isinstance(day, dict):
            continue
        date = day.get("date", key)
        rain = day.get("rain", 0.0)
        tmin = day.get("tmin", "?")
        tmax = day.get("tmax", "?")
        cloud = day.get("cloud", "?")
        wind_dir = day.get("wind", ["", ""])
        wind_dir_str = wind_dir[1] if isinstance(wind_dir, list) and len(wind_dir) > 1 else str(wind_dir)
        wspd = day.get("wspd", "?")
        warning = day.get("weather_warning", "")
        rain_label = day.get("rain_message", f"{rain}mm")
        lines.append(
            f"  {date}: {rain_label} ({rain}mm), Temp {tmin}-{tmax}°C, "
            f"Cloud {cloud}%, Wind {wind_dir_str} {wspd}m/s. {warning}"
        )
    return "\n".join(lines)


def _summarise_hourly_records(records: List[Any], place_name: str, mode: str) -> str:
    """Compact summary for sub-daily forecast records."""
    if not records:
        return "No hourly forecast records returned."
    lines = [f"{mode} forecast for {place_name} ({len(records)} time-steps):"]
    for rec in records[:12]:  # cap at 12 entries to save context
        if not isinstance(rec, dict):
            continue
        ts = rec.get("time") or rec.get("datetime") or rec.get("valid_time", "")
        rain = rec.get("rain") or rec.get("rainfall", 0)
        temp = rec.get("temp") or rec.get("temperature", "?")
        lines.append(f"  {ts}: rain={rain}mm, temp={temp}°C")
    if len(records) > 12:
        lines.append(f"  ... {len(records) - 12} more time-steps omitted.")
    return "\n".join(lines)


def fetch_mausamgram_forecast(
    lat: Any,
    lon: Any,
    forecast_mode: str,
    place_name: str = "",
    session: Any = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    """
    Fetch a point forecast from Mausamgram.
    Returns a compact result dict; the heavy `parsed` blob is intentionally
    excluded to keep the LLM context small.
    """
    http = session or _HTTP
    location = resolve_location(lat=lat, lon=lon)
    display_name = place_name or location.get("name", f"{lat},{lon}")
    mode = _normalize_forecast_mode(forecast_mode)
    endpoint = MAUSAMGRAM_ENDPOINTS[mode]
    requested_at = datetime.now(timezone.utc).isoformat()
    try:
        credentials = _get_mausamgram_credentials()
    except ValueError as exc:
        return {
            "endpoint": endpoint,
            "forecast_mode": mode,
            "requested_at": requested_at,
            "status": "error",
            "error": str(exc),
            "records": [],
            "summary": str(exc),
        }

    try:
        if mode == "daily":
            response = http.get(
                endpoint,
                params={"lat": location["lat"], "lon": location["lon"]},
                auth=(credentials["user"], credentials["key"]),
                timeout=timeout,
            )
            request_method = "GET"
        else:
            response = http.post(
                endpoint,
                json=_build_mausamgram_hourly_payload(location["lat"], location["lon"], mode),
                headers={
                    "user": credentials["user"],
                    "key": credentials["key"],
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
            request_method = "POST"
        response.raise_for_status()
    except requests.RequestException as exc:
        return {
            "endpoint": endpoint,
            "forecast_mode": mode,
            "request_method": "GET" if mode == "daily" else "POST",
            "requested_at": requested_at,
            "status": "error",
            "error": f"Mausamgram request failed: {exc}",
            "records": [],
            "summary": f"Failed to fetch forecast: {exc}",
        }

    result: Dict[str, Any] = {
        "endpoint": endpoint,
        "forecast_mode": mode,
        "request_method": request_method,
        "requested_at": requested_at,
        "status": "ok",
        "http_status": response.status_code,
        "records": [],
        "summary": "",
    }
    try:
        raw = response.json()
        records = _coerce_forecast_records(raw)
        result["records"] = records
        # Build compact summary — this is what the LLM agent should use
        if mode == "daily":
            result["summary"] = _summarise_daily_records(
                raw[0] if isinstance(raw, list) and raw else raw, display_name
            )
        else:
            result["summary"] = _summarise_hourly_records(records, display_name, mode)
    except ValueError:
        result["status"] = "parser_warning"
        result["summary"] = "Mausamgram response was not valid JSON."
        result["raw_response"] = response.text[:500]
    return result

@tool
def lookup_location(place_name: str) -> str:
    """
    Resolve an Indian city/place name to latitude and longitude.
    Use this BEFORE fetch_mausamgram_forecast_tool when you only know the place name.
    Returns a JSON string like: {"name": "Allahabad", "lat": 25.41, "lon": 81.85}
    """
    try:
        loc = resolve_location(place=place_name)
        return json.dumps({"name": loc["name"], "lat": loc["lat"], "lon": loc["lon"]})
    except ValueError as e:
        return f"Error: {e}"


@tool
def fetch_mausamgram_forecast_tool(input_data: str) -> str:
    """
    Fetch a weather forecast from the Mausamgram API.
    Input MUST be a JSON string with ONE of these two patterns:
      Pattern A (place name): {"place": "Allahabad", "forecast_mode": "daily"}
      Pattern B (coordinates): {"lat": 25.41, "lon": 81.85, "forecast_mode": "daily"}
    forecast_mode can be: daily, 1hr, 3hr, 6hr
    Returns a compact human-readable text summary of the forecast.
    """
    try:
        data = json.loads(input_data)
        mode = data.get("forecast_mode", "daily")
        place = data.get("place", "")
        lat = data.get("lat")
        lon = data.get("lon")

        # Resolve place name if no coordinates provided
        if place and (lat is None or lon is None):
            try:
                loc = resolve_location(place=place)
                lat, lon = loc["lat"], loc["lon"]
                place = loc.get("name", place)
            except ValueError as e:
                return f"Error resolving place '{place}': {e}"

        if lat is None or lon is None:
            return "Error: Provide either 'place' name or both 'lat' and 'lon' in JSON input."

        result = fetch_mausamgram_forecast(lat, lon, mode, place_name=place)
        if result["status"] == "error":
            return f"Forecast fetch failed: {result.get('error', 'Unknown error')}"
        # Return the compact summary — NOT the raw JSON blob
        return result.get("summary") or json.dumps({k: v for k, v in result.items() if k not in ("records",)}, indent=2)
    except Exception as e:
        return f"Error parsing tool input: {e}. Ensure you pass a valid JSON string."

@tool
def parse_imd_bulletins(urls: Any) -> str:
    """
    Parses a list of IMD press release PDF URLs and returns key forecast sections.
    Returns only the most important fields: forecast, warning, rainfall_warnings,
    and action_suggested — NOT the full raw document.
    Input: a JSON list of PDF URLs, e.g. ["https://...", "https://..."]
    """
    urls = _coerce_url_list(urls)
    if not urls:
        return json.dumps({"error": "No valid PDF URLs were provided."})

    _IMPORTANT_KEYS = (
        "document_type", "source_url",
        "forecast", "weather_forecast",
        "warning", "rainfall_warnings",
        "impact_expected", "action_suggested",
    )
    MAX_CHARS = 3000  # Keep the total output compact for the LLM

    all_bulletins_data = []
    for url in urls:
        try:
            if pdfplumber is None:
                raise ImportError("pdfplumber is required to parse IMD PDF bulletins.")
            response = _HTTP.get(url, stream=True, timeout=20)
            response.raise_for_status()
            pdf_data = io.BytesIO(response.content)
            full_text = ""
            all_tables = []
            with pdfplumber.open(pdf_data) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text(x_tolerance=2) or ""
                    tables = page.extract_tables()
                    if tables:
                        all_tables.extend(tables)

            table_str = str(all_tables).lower()
            if "country as a whole" in table_str and "departure (%)" in table_str:
                parsed_data = _parse_weekly_summary(all_tables, url)
            elif "time (ist)" in table_str and "rainfall" in table_str and len(all_tables) > 0 and len(all_tables[0]) > 0 and len(all_tables[0][0]) == 3:
                parsed_data = _parse_rainfall_log(all_tables, url)
            else:
                parsed_data = _parse_forecast_bulletin(full_text, url)

            # Keep only important keys to reduce context size
            compact = {k: parsed_data[k] for k in _IMPORTANT_KEYS if k in parsed_data and parsed_data[k]}
            all_bulletins_data.append(compact)

        except Exception as e:
            all_bulletins_data.append({"source_url": url, "error": f"Failed to parse PDF: {e}"})

    result_str = json.dumps(all_bulletins_data, indent=2)
    # Hard cap on output length to keep LLM context safe
    if len(result_str) > MAX_CHARS:
        result_str = result_str[:MAX_CHARS] + "\n  ... [truncated for context window]]"
    return result_str


# ====================
# Main Execution Block
# ====================
if __name__ == '__main__':
    print("--- Testing Web Scraper (Last 7 Days) ---")
    urls_json = scrape_imd_press_release_urls.invoke({})
    print(f"Found URLs:\n{urls_json}")
    try:
        urls_list = json.loads(urls_json)
        if urls_list and isinstance(urls_list, list):
            print("\n--- Testing Intelligent PDF Parser ---")
            extracted_info = parse_imd_bulletins.invoke({"urls": urls_list})
            print("Extracted Info (JSON):")
            print(extracted_info)
        else:
            print("\nNo valid URLs found to parse.")
    except json.JSONDecodeError:
        print("\nScraper did not return a valid JSON list of URLs.")
