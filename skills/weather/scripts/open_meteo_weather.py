#!/usr/bin/env python3

import argparse
import datetime
import hashlib
import json
import os
import pathlib
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo


DEFAULT_CACHE_RELATIVE_PATH = "weather/open-meteo-v1"
DEFAULT_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
DEFAULT_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_CACHE_SECONDS = 30 * 24 * 60 * 60
CURRENT_CACHE_SECONDS = 6 * 60 * 60
FORECAST_DAYS_INCLUDING_TODAY = 16

CURRENT_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
]

DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
]

WEATHER_CODE_DESCRIPTIONS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

KOREAN_LOCATION_ALIASES = {
    "서울": "Seoul",
    "서울시": "Seoul",
    "서울특별시": "Seoul",
    "부산": "Busan",
    "부산시": "Busan",
    "부산광역시": "Busan",
    "대구": "Daegu",
    "인천": "Incheon",
    "광주": "Gwangju",
    "대전": "Daejeon",
    "울산": "Ulsan",
    "세종": "Sejong",
    "세종시": "Sejong",
    "제주": "Jeju",
    "제주시": "Jeju-si",
    "경기": "Gyeonggi-do",
    "경기도": "Gyeonggi-do",
    "강원": "Gangwon-do",
    "강원도": "Gangwon-do",
    "충북": "Chungcheongbuk-do",
    "충청북도": "Chungcheongbuk-do",
    "충남": "Chungcheongnam-do",
    "충청남도": "Chungcheongnam-do",
    "전북": "Jeollabuk-do",
    "전라북도": "Jeollabuk-do",
    "전남": "Jeollanam-do",
    "전라남도": "Jeollanam-do",
    "경북": "Gyeongsangbuk-do",
    "경상북도": "Gyeongsangbuk-do",
    "경남": "Gyeongsangnam-do",
    "경상남도": "Gyeongsangnam-do",
}


def main():
    arguments = parse_arguments()
    result = run_weather_lookup(arguments)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


def default_cache_directory():
    configured = os.environ.get("WEATHER_CACHE_DIR", "").strip()
    if configured != "":
        return configured
    for environment_name in ("BLUECLAW_DEPENDENCY_CACHE", "XDG_CACHE_HOME", "TMPDIR"):
        root = os.environ.get(environment_name, "").strip()
        if root != "":
            return str(Path(root) / DEFAULT_CACHE_RELATIVE_PATH)
    return str(Path(tempfile.gettempdir()) / DEFAULT_CACHE_RELATIVE_PATH)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Fetch Open-Meteo weather with shared caching.")
    parser.add_argument("--location", default="")
    parser.add_argument("--date", default="today")
    parser.add_argument("--language", default="ko")
    parser.add_argument("--cache-directory", default=default_cache_directory())
    parser.add_argument("--geocoding-url", default=os.environ.get("OPEN_METEO_GEOCODING_URL", DEFAULT_GEOCODING_URL))
    parser.add_argument("--forecast-url", default=os.environ.get("OPEN_METEO_FORECAST_URL", DEFAULT_FORECAST_URL))
    return parser.parse_args()


def run_weather_lookup(arguments):
    fetched_at = current_utc_time()
    location_query = normalize_text(arguments.location)
    language = normalize_language(arguments.language)

    if location_query == "":
        return clarification_result("missing_location", "날씨를 확인할 지역을 알려주세요.")

    cache_directory = pathlib.Path(arguments.cache_directory)
    geocoding_result = resolve_location(location_query, language, cache_directory, arguments.geocoding_url, fetched_at)
    if geocoding_result["status"] != "ok":
        return geocoding_result

    location = geocoding_result["location"]
    requested_date_result = resolve_requested_date(arguments.date, location, fetched_at)
    if requested_date_result["status"] != "ok":
        return requested_date_result

    requested_date = requested_date_result["requestedDate"]
    cache_status = {"geocoding": geocoding_result["cacheStatus"]}
    return resolve_weather(location, requested_date, cache_directory, arguments.forecast_url, fetched_at, cache_status)


def resolve_location(location_query, language, cache_directory, geocoding_url, fetched_at):
    cache_key = hashed_key({"query": normalize_cache_text(location_query), "language": language})
    cache_path = cache_directory / "geocoding" / f"{cache_key}.json"
    cached_document = read_unexpired_cache(cache_path, fetched_at)
    if cached_document is not None:
        return resolve_location_from_results(location_query, cached_document["results"], "hit")

    try:
        document = fetch_first_geocoding_match(location_query, language, geocoding_url)
    except Exception as error_value:
        return unavailable_result("geocoding_failed", str(error_value))

    results = document.get("results", [])
    if not isinstance(results, list) or len(results) == 0:
        return {
            "status": "not_found",
            "reason": "location_not_found",
            "message": "지역을 찾지 못했습니다. 도시, 구/군, 국가를 더 구체적으로 알려주세요.",
            "query": location_query,
        }

    cache_document = {
        "fetchedAt": fetched_at,
        "expiresAt": add_seconds(fetched_at, GEOCODING_CACHE_SECONDS),
        "results": results,
    }
    write_json_cache(cache_path, cache_document)
    return resolve_location_from_results(location_query, results, "miss")


def fetch_first_geocoding_match(location_query, language, geocoding_url):
    last_document = {"results": []}
    for candidate in location_query_candidates(location_query):
        parameters = {"name": candidate, "count": 5, "language": language, "format": "json"}
        document = fetch_json(geocoding_url, parameters)
        results = document.get("results", [])
        if isinstance(results, list) and len(results) > 0:
            return document
        last_document = document
    return last_document


def location_query_candidates(location_query):
    normalized_query = normalize_cache_text(location_query)
    alias = KOREAN_LOCATION_ALIASES.get(normalized_query)
    if alias is None:
        return [location_query]
    return [alias, location_query]


def resolve_location_from_results(location_query, results, cache_status):
    if is_ambiguous_location(location_query, results):
        return {
            "status": "needs_clarification",
            "reason": "ambiguous_location",
            "message": "동명이인 지역이 여러 곳입니다. 도시와 국가 또는 행정구역을 함께 알려주세요.",
            "alternatives": [compact_location(result) for result in results[:5]],
            "cacheStatus": cache_status,
        }
    return {"status": "ok", "location": compact_location(results[0]), "cacheStatus": cache_status}


def is_ambiguous_location(location_query, results):
    if "," in location_query or len(results) < 2:
        return False
    first_name = normalize_cache_text(str(results[0].get("name", "")))
    second_name = normalize_cache_text(str(results[1].get("name", "")))
    if first_name == "" or first_name != second_name:
        return False
    first_area = location_area_key(results[0])
    second_area = location_area_key(results[1])
    return first_area != second_area


def location_area_key(result):
    return "|".join(
        normalize_cache_text(str(result.get(field, "")))
        for field in ["admin1", "admin2", "country_code", "country"]
    )


def compact_location(result):
    latitude = result.get("latitude")
    longitude = result.get("longitude")
    return {
        "id": str(result.get("id", "")),
        "name": str(result.get("name", "")),
        "admin1": str(result.get("admin1", "")),
        "country": str(result.get("country", "")),
        "countryCode": str(result.get("country_code", "")),
        "timezone": str(result.get("timezone", "UTC") or "UTC"),
        "latitude": latitude,
        "longitude": longitude,
    }


def resolve_requested_date(raw_date, location, fetched_at):
    location_timezone = load_timezone(location.get("timezone", "UTC"))
    today = datetime.datetime.fromisoformat(fetched_at).astimezone(location_timezone).date()
    normalized_date = normalize_cache_text(raw_date)

    if normalized_date in ["", "today", "오늘"]:
        requested_date = today
    elif normalized_date in ["tomorrow", "내일"]:
        requested_date = today + datetime.timedelta(days=1)
    else:
        try:
            requested_date = datetime.date.fromisoformat(raw_date.strip())
        except ValueError:
            return clarification_result("ambiguous_date", "날씨를 확인할 날짜를 YYYY-MM-DD 형식이나 오늘/내일로 알려주세요.")

    last_forecast_date = today + datetime.timedelta(days=FORECAST_DAYS_INCLUDING_TODAY - 1)
    if requested_date < today or requested_date > last_forecast_date:
        return {
            "status": "out_of_range",
            "reason": "forecast_date_out_of_range",
            "message": "이 스킬은 오늘부터 Open-Meteo가 제공하는 예보 기간의 날짜만 지원합니다.",
            "requestedDate": requested_date.isoformat(),
            "supportedStartDate": today.isoformat(),
            "supportedEndDate": last_forecast_date.isoformat(),
        }
    return {"status": "ok", "requestedDate": requested_date.isoformat()}


def resolve_weather(location, requested_date, cache_directory, forecast_url, fetched_at, cache_status):
    location_timezone = load_timezone(location.get("timezone", "UTC"))
    requested_local_date = datetime.date.fromisoformat(requested_date)
    fetched_local_date = datetime.datetime.fromisoformat(fetched_at).astimezone(location_timezone).date()
    should_include_current = requested_local_date == fetched_local_date
    daily_cache_path = daily_cache_file(cache_directory, location, requested_date)
    current_cache_path = current_cache_file(cache_directory, location, requested_date)

    daily_cache = read_unexpired_cache(daily_cache_path, fetched_at)
    current_cache = read_unexpired_cache(current_cache_path, fetched_at) if should_include_current else None

    if daily_cache is not None and (current_cache is not None or not should_include_current):
        cache_status["daily"] = "hit"
        cache_status["current"] = "hit" if should_include_current else "skipped"
        return weather_result(location, requested_date, current_cache, daily_cache, cache_status, fetched_at)

    try:
        fetched_weather = fetch_weather(location, requested_date, should_include_current, forecast_url)
    except Exception as error_value:
        if daily_cache is not None:
            cache_status["daily"] = "hit"
            cache_status["current"] = "unavailable" if should_include_current else "skipped"
            result = weather_result(location, requested_date, None, daily_cache, cache_status, fetched_at)
            result["warnings"] = [f"fresh_fetch_failed: {error_value}"]
            return result
        return unavailable_result("forecast_failed", str(error_value))

    daily_document = daily_cache_document(location, requested_date, fetched_weather["daily"], fetched_at, location_timezone)
    write_json_cache(daily_cache_path, daily_document)
    cache_status["daily"] = "miss" if daily_cache is None else "refresh"

    current_document = None
    if should_include_current and fetched_weather.get("current") is not None:
        current_document = current_cache_document(location, requested_date, fetched_weather["current"], fetched_at)
        write_json_cache(current_cache_path, current_document)
        cache_status["current"] = "miss" if current_cache is None else "refresh"
    else:
        cache_status["current"] = "skipped"

    return weather_result(location, requested_date, current_document, daily_document, cache_status, fetched_at)


def fetch_weather(location, requested_date, should_include_current, forecast_url):
    parameters = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": "auto",
        "start_date": requested_date,
        "end_date": requested_date,
    }
    if should_include_current:
        parameters["current"] = ",".join(CURRENT_VARIABLES)

    document = fetch_json(forecast_url, parameters)
    daily = extract_daily_weather(document, requested_date)
    current = extract_current_weather(document) if should_include_current else None
    return {"daily": daily, "current": current}


def extract_daily_weather(document, requested_date):
    daily = document.get("daily", {})
    times = daily.get("time", [])
    if requested_date not in times:
        raise ValueError("forecast response did not include requested date")
    index = times.index(requested_date)
    weather_code = value_at(daily, "weather_code", index)
    return {
        "date": requested_date,
        "weatherCode": weather_code,
        "weatherDescription": describe_weather_code(weather_code),
        "temperatureMaxC": value_at(daily, "temperature_2m_max", index),
        "temperatureMinC": value_at(daily, "temperature_2m_min", index),
        "precipitationSumMM": value_at(daily, "precipitation_sum", index),
        "precipitationProbabilityMaxPercent": value_at(daily, "precipitation_probability_max", index),
        "windSpeedMaxKPH": value_at(daily, "wind_speed_10m_max", index),
        "windGustsMaxKPH": value_at(daily, "wind_gusts_10m_max", index),
    }


def extract_current_weather(document):
    current = document.get("current")
    if not isinstance(current, dict):
        return None
    weather_code = current.get("weather_code")
    return {
        "time": current.get("time"),
        "weatherCode": weather_code,
        "weatherDescription": describe_weather_code(weather_code),
        "temperatureC": current.get("temperature_2m"),
        "apparentTemperatureC": current.get("apparent_temperature"),
        "relativeHumidityPercent": current.get("relative_humidity_2m"),
        "precipitationMM": current.get("precipitation"),
        "windSpeedKPH": current.get("wind_speed_10m"),
    }


def value_at(document, key, index):
    values = document.get(key, [])
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def daily_cache_document(location, requested_date, daily, fetched_at, location_timezone):
    return {
        "fetchedAt": fetched_at,
        "expiresAt": next_local_midnight_utc(requested_date, location_timezone),
        "location": location,
        "requestedDate": requested_date,
        "daily": daily,
        "source": source_document(),
    }


def current_cache_document(location, requested_date, current, fetched_at):
    return {
        "fetchedAt": fetched_at,
        "expiresAt": add_seconds(fetched_at, CURRENT_CACHE_SECONDS),
        "location": location,
        "requestedDate": requested_date,
        "current": current,
        "source": source_document(),
    }


def weather_result(location, requested_date, current_cache, daily_cache, cache_status, fetched_at):
    return {
        "status": "ok",
        "location": location,
        "requestedDate": requested_date,
        "current": None if current_cache is None else current_cache.get("current"),
        "daily": daily_cache.get("daily"),
        "cacheStatus": cache_status,
        "source": source_document(),
        "fetchedAt": fetched_at,
    }


def clarification_result(reason, message):
    return {"status": "needs_clarification", "reason": reason, "message": message}


def unavailable_result(reason, message):
    return {"status": "unavailable", "reason": reason, "message": message}


def source_document():
    return {
        "provider": "Open-Meteo",
        "forecastAPI": DEFAULT_FORECAST_URL,
        "geocodingAPI": DEFAULT_GEOCODING_URL,
    }


def fetch_json(base_url, parameters):
    url = base_url + "?" + urllib.parse.urlencode(parameters)
    request = urllib.request.Request(url, headers={"User-Agent": "internkim-weather-skill/1"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error_value:
        body = error_value.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Open-Meteo returned HTTP {error_value.code}: {body}") from error_value
    except urllib.error.URLError as error_value:
        raise RuntimeError(f"Open-Meteo request failed: {error_value.reason}") from error_value


def read_unexpired_cache(path, fetched_at):
    document = read_json_cache(path)
    if document is None:
        return None
    expires_at = document.get("expiresAt")
    if not isinstance(expires_at, str):
        return None
    if datetime.datetime.fromisoformat(expires_at) <= datetime.datetime.fromisoformat(fetched_at):
        return None
    return document


def read_json_cache(path):
    try:
        with path.open("r", encoding="utf-8") as cache_file:
            return json.load(cache_file)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None


def make_shared_cache_directory(directory_path):
    # A shared cache tree can be setgid to a group every requester belongs to
    # while each requester runs as a different unprivileged UID, so a directory
    # this call creates must stay group-writable regardless of the default umask.
    previous_umask = os.umask(0o002)
    try:
        directory_path.mkdir(parents=True, exist_ok=True)
    finally:
        os.umask(previous_umask)


def write_json_cache(path, document):
    make_shared_cache_directory(path.parent)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary_file:
        json.dump(document, temporary_file, ensure_ascii=False, separators=(",", ":"))
        temporary_path = pathlib.Path(temporary_file.name)
    os.replace(temporary_path, path)


def daily_cache_file(cache_directory, location, requested_date):
    return cache_directory / "daily" / location_cache_key(location) / f"{requested_date}.json"


def current_cache_file(cache_directory, location, requested_date):
    return cache_directory / "current" / location_cache_key(location) / f"{requested_date}.json"


def location_cache_key(location):
    location_id = normalize_cache_text(str(location.get("id", "")))
    if location_id != "":
        return location_id
    return hashed_key(
        {
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "timezone": location.get("timezone"),
        }
    )


def hashed_key(document):
    encoded = json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


def normalize_language(language):
    normalized_language = normalize_cache_text(language)
    if normalized_language.startswith("ko"):
        return "ko"
    return "en"


def normalize_text(value):
    return " ".join(str(value).strip().split())


def normalize_cache_text(value):
    return normalize_text(value).casefold()


def current_utc_time():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def add_seconds(iso_time, seconds):
    timestamp = datetime.datetime.fromisoformat(iso_time)
    return (timestamp + datetime.timedelta(seconds=seconds)).isoformat()


def next_local_midnight_utc(requested_date, location_timezone):
    local_date = datetime.date.fromisoformat(requested_date)
    next_midnight = datetime.datetime.combine(local_date + datetime.timedelta(days=1), datetime.time(), location_timezone)
    return next_midnight.astimezone(datetime.timezone.utc).isoformat()


def load_timezone(timezone_name):
    try:
        return zoneinfo.ZoneInfo(str(timezone_name))
    except zoneinfo.ZoneInfoNotFoundError:
        return datetime.timezone.utc


def describe_weather_code(weather_code):
    if isinstance(weather_code, float):
        weather_code = int(weather_code)
    if not isinstance(weather_code, int):
        return "unknown"
    return WEATHER_CODE_DESCRIPTIONS.get(weather_code, "unknown")


if __name__ == "__main__":
    main()
