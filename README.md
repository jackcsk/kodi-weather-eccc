# Environment Canada weather for Kodi

A Kodi weather add-on (`weather.environmentcanada`) for Canadian locations. Forecasts and alerts come from
[Environment and Climate Change Canada](https://weather.gc.ca) (ECCC); current conditions come from
[Open-Meteo](https://open-meteo.com) for the exact location. No API key or account is needed.

The weather add-ons in Kodi's official repository either cover only the US (NOAA) or use global data
sources. This one uses Canada's national weather service: the same forecasts as weather.gc.ca.

Also included: an optional weather panel for the picture slideshow, see
[extras/slideshow-overlay](extras/slideshow-overlay/README.md).

## What you get

- Current temperature, feels-like (wind chill / humidex), humidity, wind, condition
- 24-hour hourly forecast and 7-day forecast with chance of precipitation
- Active ECCC weather alerts, sunrise and sunset
- Updates every 15 minutes, instead of Kodi's usual 30
- Up to 3 saved locations anywhere in Canada

Works with any skin that shows weather, Estuary included.

## Requirements

- Kodi 19 (Matrix) or newer. Tested on Kodi 20.5 (Nexus) on a Raspberry Pi 5.
- Internet access to `api.weather.gc.ca`, `api.open-meteo.com` and `geocoding-api.open-meteo.com`.

## Install

1. Get the add-on zip, `weather.environmentcanada-<version>.zip`, either way:
   - download it from the [Releases page](https://github.com/jackcsk/kodi-weather-eccc/releases), or
   - build it from this repository: `python3 tools/build_zip.py` writes it to `dist/`.

   GitHub's automatic "Source code (zip)" download is not installable in Kodi.
2. In Kodi, allow zip installs once: **Settings → System → Add-ons → Unknown sources → On**.
3. **Settings → Add-ons → Install from zip file**, then pick the zip.

## Choose your city

1. **Settings → Services → Weather → Service for weather information → Environment Canada**.
2. On the same screen, open **Settings** for the add-on.
3. Click **Location 1** and type a place name, e.g. `Markham` or `Saint-Jérôme`.
4. Pick the place from the list. Several towns can share a name; the list shows the province.
5. Pick the **Environment Canada forecast area**. The list is sorted by distance, so the first entry is
   normally the right one. Small towns use the forecast area of the nearest city that ECCC covers.

Add **Location 2** and **Location 3** the same way if you want more. Switch between them on Kodi's Weather
screen.

Moved or travelling? Change the location the same way. The add-on does not detect where Kodi is.

## Where the numbers come from

| Shown | Source |
|---|---|
| Hourly and 7-day forecast, chance of precipitation, alerts, sunrise/sunset, condition text | ECCC city page forecast for the chosen forecast area (`api.weather.gc.ca`) |
| Current temperature, feels-like, humidity, wind | Open-Meteo, 15-minute model data for the forecast area's coordinates |
| Current conditions if Open-Meteo is unavailable | The ECCC observation station assigned to the forecast area |
| Location search | Open-Meteo geocoding, then the nearest ECCC forecast areas |

Why not ECCC's own observation for "now"? Each ECCC city page reports one assigned station, which can be
far away. Markham, Ontario's is Billy Bishop airport on the Toronto lakeshore, 28 km south. Over one day
it read 2.6 °C warmer than stations in Markham on average, and 5.6 °C warmer on a clear morning.
Open-Meteo's estimate for the location was within 0.5 °C on average.

## For skin authors

Besides Kodi's standard weather properties, the add-on sets these on the Weather window
(`Window(weather).Property(...)`):

| Property | Example |
|---|---|
| `Current.TemperatureLabel` | `15.4°C`: one decimal in the user's unit; whole degrees from 100 up (`-128°F`), so it never exceeds 7 characters. Kodi's own label is always whole degrees. |
| `Current.Station` | `Open-Meteo model at Markham`, or the ECCC station name |
| `Current.ObservationTime` | `6:30 PM` |
| `Alerts` | `Yellow Advisory - Frost`: active ECCC alerts joined with ` · `; empty when none |
| `Unavailable` | `Weather unavailable since 3:55 PM`: set when a refresh fails (the readings are then blank), with the time of the first failure in a row; empty after the next successful refresh |
| `Daily.N.Summary` | ECCC's full forecast text for that day and night |

The background service refreshes these properties every 15 minutes. Kodi's own `Weather.*` labels keep
Kodi's 30-minute cycle.

## Development

```sh
python3 -m unittest discover tests      # tests run without Kodi
python3 tools/build_zip.py              # builds dist/weather.environmentcanada-<version>.zip
uvx kodi-addon-checker --branch matrix weather.environmentcanada   # Team Kodi's add-on linter
```

`weather.environmentcanada/lib/eccc.py` turns ECCC/Open-Meteo data into Kodi properties and has no Kodi
imports. `lib/addon.py` is the Kodi side. CI runs the tests and Team Kodi's add-on checker on every push.

### Releasing

The version lives in one place: the `version` attribute of `<addon>` in
`weather.environmentcanada/addon.xml`. Kodi compares it to decide whether an installed copy needs
updating, and `tools/build_zip.py` puts it in the zip's file name.

1. In `addon.xml`, raise `version` (e.g. `1.1.0` → `1.2.0`) and replace the `<news>` text with what
   changed.
2. Commit, then tag and push the tag with the same version and a `v` prefix:
   ```sh
   git tag v1.2.0 && git push origin main v1.2.0
   ```
3. GitHub Actions runs the tests and the add-on checker, checks that the tag matches `addon.xml`, builds
   the zip and publishes a GitHub release with it attached. If any check fails, nothing is published.

## Credits and licences

- Code: MIT, see [LICENSE](LICENSE). The slideshow overlay in `extras/slideshow-overlay` is GPL-2.0
  because it is derived from Kodi's Estuary skin.
- Forecast data: Environment and Climate Change Canada. Contains information licensed under the
  [Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada).
- Current conditions and geocoding: [Open-Meteo.com](https://open-meteo.com),
  data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Open-Meteo's free API is for
  non-commercial use.

This project is not affiliated with or endorsed by Environment and Climate Change Canada, Open-Meteo or
Team Kodi.
