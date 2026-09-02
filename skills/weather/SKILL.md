---
name: weather
description: Look up current and date-specific weather through Open-Meteo with shared caching. Use for weather, forecast, temperature, rain, umbrella, wind, 날씨, 기온, 비 와, 우산, 바람, 오늘 날씨, 내일 날씨, or a specific-date weather request.
compatibility: Requires python3 and network access to the Open-Meteo API.
---


# Weather

Use the bundled Open-Meteo script to retrieve weather. The script resolves the location, fetches current and daily forecast data, and reuses shared cache entries across users.

## Workflow

1. Identify the location from the user's request.
2. Identify the requested date.
3. Ask one concise question if the location or date is missing or ambiguous.
4. Run the script.
5. Summarize the returned JSON naturally in the user's language.

Use this command shape:

```json
{
  "command": "python3 <skill>/scripts/open_meteo_weather.py --location \"<location>\" --date \"<YYYY-MM-DD|today|tomorrow>\" --language \"<ko|en>\"",
  "workingDirectoryPath": "<skill>"
}
```

Quote arguments safely. Do not concatenate raw user text into shell syntax outside the `--location` value.

For Korean requests, use `--language ko`. For English requests, use `--language en`.

## Date Rules

- For "today" or "오늘", pass `today`.
- For "tomorrow" or "내일", pass `tomorrow`.
- For a specific date, resolve it to `YYYY-MM-DD` before calling the script.
- Do not use this skill for historical weather. If the user asks for a past date, explain that this Open-Meteo skill handles today and forecast dates only.

## Answer Rules

- If `status` is `ok`, answer from `current` and `daily`.
- If `cacheStatus` says cached data was used, do not apologize. Cached weather is expected for repeated same-location requests.
- Mention precipitation probability or precipitation amount when the user asks about rain, umbrella, commute, or outdoor plans.
- Mention apparent temperature when it differs meaningfully from temperature.
- If `status` is `needs_clarification`, ask the clarification from the returned `message`.
- If `status` is `not_found`, say the location could not be resolved and ask for a more specific city, district, or country.
- If `status` is `out_of_range`, say this skill supports today and available forecast dates only.
- If `status` is `unavailable`, say the weather source could not be reached and no usable cache was available.

Do not claim weather was retrieved until the script returns successful JSON.
