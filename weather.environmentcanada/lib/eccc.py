"""Environment and Climate Change Canada (ECCC) city page weather -> Kodi weather window properties.

Pure Python (no Kodi imports) so the transform runs and is tested off-device.
Data: https://api.weather.gc.ca/collections/citypageweather-realtime (Open Government Licence - Canada).
"""
import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = 'https://api.weather.gc.ca/collections/citypageweather-realtime/items'
GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'
NOWCAST_URL = 'https://api.open-meteo.com/v1/forecast'
USER_AGENT = 'weather.environmentcanada/1.0 (Kodi weather add-on)'
TIMEOUT = 20

PROVIDER = 'Environment and Climate Change Canada, Open-Meteo'
# A nowcast older than this is ignored in favour of the ECCC observation.
NOWCAST_MAX_AGE = timedelta(hours=1)
MAX_HOURS = 24
MAX_DAYS = 7
# Slots skins may read. Slots past the available data are blanked so values from an
# earlier fetch or another location never linger on screen.
HOUR_SLOTS = 48
DAILY_SLOTS = 14
DAY_SLOTS = 7

# ECCC icon code -> Kodi icon/fanart code (resource.images.weathericons.default/<code>.png).
# ECCC: 0-19 and 22-28 day/neutral, 30-39 night, 40-48 hazards; 29 = not available.
ICONS = {
    0: '32', 1: '34', 2: '30', 3: '28', 4: '28', 5: '30', 6: '39', 7: '5', 8: '14', 9: '37',
    10: '26', 11: '12', 12: '12', 13: '40', 14: '10', 15: '5', 16: '16', 17: '16', 18: '42', 19: '4',
    20: '20', 21: '20', 22: '30', 23: '21', 24: '20', 25: '15', 26: '25', 27: '18', 28: '9',
    30: '31', 31: '33', 32: '29', 33: '27', 34: '27', 35: '29', 36: '45', 37: '5', 38: '46', 39: '47',
    40: '15', 41: '0', 42: '0', 43: '24', 44: '22', 45: '19', 46: '3', 47: '3', 48: '0',
}

# ECCC compass abbreviation -> Kodi localized string id ('VR' = variable).
WIND_DIRECTIONS = {
    'N': 71, 'NNE': 72, 'NE': 73, 'ENE': 74, 'E': 75, 'ESE': 76, 'SE': 77, 'SSE': 78,
    'S': 79, 'SSW': 80, 'SW': 81, 'WSW': 82, 'W': 83, 'WNW': 84, 'NW': 85, 'NNW': 86, 'VR': 87,
}

# Multipliers from km/h to each Kodi speed unit.
SPEED_FACTORS = {
    'km/h': 1.0, 'm/min': 1000 / 60, 'm/s': 1 / 3.6, 'ft/h': 3280.84, 'ft/min': 3280.84 / 60,
    'ft/s': 3280.84 / 3600, 'mph': 0.621371, 'kts': 0.539957, 'inch/s': 39370.1 / 3600,
    'yard/s': 1093.61 / 3600, 'Furlong/Fortnight': 4.97097 * 336,
}
BEAUFORT_UPPER_KMH = (1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118)

WEEKDAYS = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
STR_TODAY = 33006
STR_TOMORROW = 33007
STR_LONG_MONDAY = 11
STR_SHORT_MONDAY = 41

CURRENT_KEYS = (
    'Location', 'Current.Location', 'Current.Condition', 'Current.Temperature', 'Current.FeelsLike',
    'Current.DewPoint', 'Current.Humidity', 'Current.Wind', 'Current.WindDirection', 'Current.WindGust',
    'Current.Pressure', 'Current.Precipitation', 'Current.UVIndex', 'Current.OutlookIcon',
    'Current.FanartCode', 'Current.Station', 'Current.ObservationTime', 'Current.IsFetched', 'Alerts',
    'Current.TemperatureLabel',
    'Today.Sunrise', 'Today.Sunset', 'Today.IsFetched',
    'Forecast.City', 'Forecast.Country', 'Forecast.Updated', 'Forecast.IsFetched',
    'Hourly.IsFetched', 'Daily.IsFetched', 'WeatherProvider', 'WeatherProviderLogo',
)
HOURLY_FIELDS = (
    'Time', 'ShortDate', 'LongDate', 'Temperature', 'FeelsLike', 'Outlook', 'OutlookIcon', 'FanartCode',
    'WindSpeed', 'WindDirection', 'WindGust', 'Precipitation', 'UVIndex',
)
DAILY_FIELDS = (
    'ShortDay', 'LongDay', 'ShortDate', 'LongDate', 'HighTemperature', 'LowTemperature', 'Outlook',
    'OutlookIcon', 'FanartCode', 'Precipitation', 'WindSpeed', 'WindDirection', 'Humidity', 'UVIndex',
    'Summary',
)
DAY_FIELDS = ('Title', 'HighTemp', 'LowTemp', 'Outlook', 'OutlookIcon', 'FanartCode')

# ECCC states probability of precipitation as e.g. "40 percent chance of showers".
POP_RE = re.compile(r'(\d+) percent chance of')


# ---------------------------------------------------------------- network

def fetch_json(url, params=None):
    if params:
        url = '%s?%s' % (url, urllib.parse.urlencode(params))
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.load(response)


def fetch_city(site_id):
    """City page feature (GeoJSON: 'properties', 'geometry') for an ECCC site id such as 'on-85'."""
    url = '%s/%s' % (API_URL, urllib.parse.quote(site_id))
    return fetch_json(url, {'f': 'json', 'lang': 'en'})


def fetch_nowcast(lat, lon):
    """Open-Meteo's 15-minute modelled current conditions at a point.

    Used for "now" because an ECCC city page reports the observation of its assigned
    station, which can be far away: Markham's is Billy Bishop airport on the lakeshore,
    28 km south, which ran 2.6 C warmer than Markham-area stations on average (up to
    5.6 C on a clear morning) in a 22-hour comparison on 2026-10-09; Open-Meteo's
    best-match blend was within 0.5 C on average.
    """
    data = fetch_json(NOWCAST_URL, {
        'latitude': lat, 'longitude': lon, 'timezone': 'auto', 'forecast_days': 1, 'wind_speed_unit': 'kmh',
        'current': 'temperature_2m,relative_humidity_2m,dew_point_2m,wind_speed_10m,'
                   'wind_direction_10m,wind_gusts_10m',
        'daily': 'temperature_2m_max',
    })
    current = data['current']
    local_time = datetime.fromisoformat(current['time'])
    highs = (data.get('daily') or {}).get('temperature_2m_max') or [None]
    return {
        'time': (local_time - timedelta(seconds=data.get('utc_offset_seconds', 0))).replace(tzinfo=timezone.utc),
        'temp': current.get('temperature_2m'),
        'humidity': current.get('relative_humidity_2m'),
        'dewpoint': current.get('dew_point_2m'),
        'wind': current.get('wind_speed_10m'),
        'gust': current.get('wind_gusts_10m'),
        'direction': compass(current.get('wind_direction_10m')),
        'today_high': highs[0],  # whole local day, including hours already past
    }


def compass(bearing):
    """Degrees -> 16-point abbreviation ('W', 'NNE', ...); '' when unknown."""
    if bearing is None:
        return ''
    points = ('N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW')
    return points[int(bearing / 22.5 + 0.5) % 16]


def geocode(name):
    """Canadian places matching a name: [{'name', 'admin1', 'lat', 'lon'}]."""
    data = fetch_json(GEOCODE_URL, {'name': name, 'count': 10, 'language': 'en', 'format': 'json',
                                    'countryCode': 'CA'})
    return [{'name': r['name'], 'admin1': r.get('admin1', ''), 'lat': r['latitude'], 'lon': r['longitude']}
            for r in data.get('results') or []]


def nearby_sites(lat, lon):
    """ECCC city pages nearest to a point, closest first: [{'id', 'name', 'region', 'province', 'km'}]."""
    for span in (0.5, 1.5, 4.0):
        bbox = '%f,%f,%f,%f' % (lon - span, lat - span, lon + span, lat + span)
        data = fetch_json(API_URL, {'f': 'json', 'lang': 'en', 'limit': 100, 'bbox': bbox})
        sites = []
        for feature in data.get('features') or []:
            site_lon, site_lat = feature['geometry']['coordinates'][:2]
            props = feature['properties']
            sites.append({
                'id': feature['id'],
                'name': text(props, 'name'),
                'region': text(props, 'region'),
                'province': feature['id'].split('-')[0].upper(),
                'km': distance_km(lat, lon, site_lat, site_lon),
            })
        if sites:
            return sorted(sites, key=lambda site: site['km'])
    return []


def distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- payload access

def lookup(node, *path):
    """Walk nested keys / list indexes; unwraps ECCC's {'en': .., 'fr': ..} leaves. None when absent."""
    for key in path:
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and isinstance(key, int) and -len(node) <= key < len(node):
            node = node[key]
        else:
            return None
    if isinstance(node, dict) and 'en' in node:
        node = node['en']
    return node


def text(node, *path):
    value = lookup(node, *path)
    return '' if value is None else str(value)


def number(node, *path):
    value = lookup(node, *path)
    try:
        return None if value is None or value == '' else float(value)
    except (TypeError, ValueError):
        return None


def parse_time(stamp):
    """ECCC UTC timestamp ('2026-10-09T21:00:00Z') -> aware datetime, or None.

    Uses fromisoformat, not strptime: Kodi reuses the interpreter between runs and
    datetime.strptime then fails with "'NoneType' object is not callable".
    """
    if not stamp or not stamp.endswith('Z'):
        return None
    try:
        return datetime.fromisoformat(stamp[:-1]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ---------------------------------------------------------------- weather maths

def round_half_up(value):
    return int(math.floor(value + 0.5))


def feels_like(temp, wind_kmh, dewpoint):
    """ECCC feels-like: wind chill at <= 10 C with wind >= 5 km/h, humidex when >= 25 at >= 20 C.

    The observation's own 'windChill' field is not used: the API reports implausible values
    (e.g. -5 at 19.4 C).
    """
    if temp is None:
        return None
    if temp <= 10 and wind_kmh is not None and wind_kmh >= 5:
        v = wind_kmh ** 0.16
        return min(temp, 13.12 + 0.6215 * temp - 11.37 * v + 0.3965 * temp * v)
    if temp >= 20 and dewpoint is not None:
        vapour = 6.11 * math.exp(5417.7530 * (1 / 273.16 - 1 / (273.15 + dewpoint)))
        humidex = temp + 0.5555 * (vapour - 10)
        if humidex >= 25:
            return humidex
    return temp


def icon_code(eccc_code):
    if eccc_code is None:
        return 'na'
    return ICONS.get(int(eccc_code), 'na')


def chance_of_precipitation(*periods):
    """Highest 'NN percent chance' stated in ECCC period text, or None."""
    found = [int(m) for period in periods if period for m in POP_RE.findall(text(period, 'textSummary'))]
    return max(found) if found else None


# ---------------------------------------------------------------- formatting

class Formatter:
    """Kodi regional display settings. localize(id) returns a Kodi localized string."""

    def __init__(self, localize, tempunit='°C', speedunit='km/h', timefmt='%H:%M:%S', datefmt='%d/%m/%Y',
                 tz=None):
        self.localize = localize
        self.tempunit = tempunit if tempunit in ('°C', '°F', 'K') else '°C'
        self.speedunit = speedunit if speedunit in SPEED_FACTORS or speedunit == 'Beaufort' else 'km/h'
        self.timefmt = timefmt.replace(':%S', '')
        no_year = re.sub(r'([/.\- ])\1+', r'\1', datefmt.replace('%Y', '').replace('%y', ''))
        self.datefmt = no_year.strip('/.- ') or '%d/%m'
        self.tz = tz

    def temperature(self, celsius, decimals=0):
        if celsius is None:
            return ''
        if self.tempunit == '°F':
            value = celsius * 1.8 + 32
        elif self.tempunit == 'K':
            value = celsius + 273.15
        else:
            value = celsius
        if abs(value) >= 99.95:
            decimals = 0  # three-digit values (°F, K) drop the decimal to keep labels from overflowing
        scale = 10 ** decimals
        value = round_half_up(value * scale) / scale + 0.0  # + 0.0 turns -0.0 into 0.0
        return '%.*f%s' % (decimals, value, self.tempunit)

    def speed(self, kmh):
        if kmh is None:
            return ''
        if self.speedunit == 'Beaufort':
            force = next((i for i, top in enumerate(BEAUFORT_UPPER_KMH) if kmh < top), 12)
            return '%d Beaufort' % force
        return '%d %s' % (round_half_up(kmh * SPEED_FACTORS[self.speedunit]), self.speedunit)

    def wind_direction(self, abbreviation):
        if not abbreviation:
            return ''
        string_id = WIND_DIRECTIONS.get(abbreviation)
        return self.localize(string_id) if string_id else abbreviation

    def local(self, moment):
        return moment.astimezone(self.tz) if moment else None

    def clock(self, moment):
        if not moment:
            return ''
        label = self.local(moment).strftime(self.timefmt)
        return label.lstrip('0') if self.timefmt.startswith('%I') else label

    def short_date(self, day):
        return day.strftime(self.datefmt)

    def relative_date(self, day, today):
        if day == today:
            return self.localize(STR_TODAY)
        if day == today + timedelta(days=1):
            return self.localize(STR_TOMORROW)
        return self.short_date(day)

    def long_day(self, day):
        return self.localize(STR_LONG_MONDAY + day.weekday())

    def short_day(self, day):
        return self.localize(STR_SHORT_MONDAY + day.weekday())


def celsius_number(value):
    """Kodi's standard numeric properties take whole degrees C / km/h; Kodi converts units itself."""
    return '' if value is None else str(round_half_up(value))


def percent(value):
    return '' if value is None else '%d%%' % round_half_up(value)


# ---------------------------------------------------------------- forecast periods

def group_periods(forecasts, issued_on):
    """Pair ECCC day/night periods into calendar days.

    ECCC issues alternating periods ('Today', 'Tonight', 'Saturday', 'Saturday night', ...);
    the first may be a night. period.value carries the weekday ('Friday night'), which is
    resolved to the first matching date on/after the previous period's date.
    Returns [{'date', 'day': period|None, 'night': period|None}].
    """
    days = []
    cursor = issued_on
    for period in forecasts:
        label = text(period, 'period', 'value').lower()
        is_night = label.endswith('night')
        weekday = label[:-len('night')].strip() if is_night else label.strip()
        if weekday in WEEKDAYS:
            target = WEEKDAYS.index(weekday)
            while cursor.weekday() != target:
                cursor += timedelta(days=1)
        last = days[-1] if days else None
        if not last or last['date'] != cursor or last['night'] or (last['day'] and not is_night):
            days.append({'date': cursor, 'day': None, 'night': None})
        days[-1]['night' if is_night else 'day'] = period
    return days


# ---------------------------------------------------------------- properties

def blank_properties():
    props = dict.fromkeys(CURRENT_KEYS, '')
    for i in range(1, HOUR_SLOTS + 1):
        props.update(('Hourly.%d.%s' % (i, field), '') for field in HOURLY_FIELDS)
    for i in range(1, DAILY_SLOTS + 1):
        props.update(('Daily.%d.%s' % (i, field), '') for field in DAILY_FIELDS)
    for i in range(DAY_SLOTS):
        props.update(('Day%d.%s' % (i, field), '') for field in DAY_FIELDS)
    return props


def build_properties(city, location_name, fmt, now=None, nowcast=None):
    """Full Kodi weather window property set (every key, blanks included) for one city page.

    nowcast: fetch_nowcast() result for the site; when fresh it supplies the current
    temperature, humidity, dew point and wind instead of the city page's station observation.
    """
    now = now or datetime.now(timezone.utc)
    today = fmt.local(now).date()
    props = blank_properties()
    props['WeatherProvider'] = PROVIDER
    props['Location'] = location_name

    hourly = [hour for hour in lookup(city, 'hourlyForecastGroup', 'hourlyForecasts') or []
              if (parse_time(hour.get('timestamp')) or now) + timedelta(hours=1) > now]
    if nowcast and not (-timedelta(minutes=15) <= now - nowcast['time'] <= NOWCAST_MAX_AGE):
        nowcast = None
    temp = _current(props, city, hourly[0] if hourly else {}, nowcast, fmt)
    _hourly(props, hourly[:MAX_HOURS], fmt, today)
    _daily(props, city, hourly, [temp, nowcast.get('today_high') if nowcast else None], fmt, today)
    props['Alerts'] = active_alerts(city, now)
    return props


def active_alerts(city, now):
    """Unexpired ECCC alerts as one line, e.g. 'Yellow Advisory - Frost'."""
    titles = []
    for warning in city.get('warnings') or []:
        expires = parse_time(text(warning, 'expiryTime'))
        title = text(warning, 'description').title()
        if title and (expires is None or expires > now) and title not in titles:
            titles.append(title)
    return ' · '.join(titles)


def _current(props, city, next_hour, nowcast, fmt):
    """Sets Current.* / Today.* / Forecast.*; returns the current temperature (C) or None."""
    obs = city.get('currentConditions') or {}
    if nowcast:
        temp, humidity, dewpoint = nowcast['temp'], nowcast['humidity'], nowcast['dewpoint']
        wind, gust, direction = nowcast['wind'], nowcast['gust'], nowcast['direction']
        source, observed = 'Open-Meteo model at %s' % text(city, 'name'), nowcast['time']
    else:
        temp = number(obs, 'temperature', 'value')
        humidity, dewpoint = number(obs, 'relativeHumidity', 'value'), number(obs, 'dewpoint', 'value')
        wind, direction = number(obs, 'wind', 'speed', 'value'), text(obs, 'wind', 'direction', 'value')
        gust = number(obs, 'wind', 'gust', 'value')
        source, observed = text(obs, 'station', 'value'), parse_time(text(obs, 'timestamp'))
    if temp is None:
        temp = number(next_hour, 'temperature', 'value')
    if wind is None:
        wind = number(next_hour, 'wind', 'speed', 'value')
        direction = text(next_hour, 'wind', 'direction', 'value')
    # The station's sky condition describes the station, not the site, and automatic stations
    # report none: in those cases use the site's forecast for the coming hour.
    condition, icon = ('', None) if nowcast else (text(obs, 'condition'), number(obs, 'iconCode', 'value'))
    if not condition:
        condition, icon = text(next_hour, 'condition'), number(next_hour, 'iconCode', 'value')
    pressure = number(obs, 'pressure', 'value')
    tendency = text(obs, 'pressure', 'tendency')
    code = icon_code(icon)

    props.update({
        'Current.Location': text(city, 'name'),
        'Current.Condition': condition,
        'Current.Temperature': celsius_number(temp),
        # Kodi's own Weather.Temperature is whole degrees; skins wanting a decimal use this.
        # At most 7 characters ('-88.8°C', '-128°F'), which the slideshow panel fits.
        'Current.TemperatureLabel': fmt.temperature(temp, decimals=1),
        'Current.FeelsLike': celsius_number(feels_like(temp, wind, dewpoint)),
        'Current.DewPoint': celsius_number(dewpoint),
        'Current.Humidity': celsius_number(humidity),
        'Current.Wind': celsius_number(wind),
        'Current.WindDirection': fmt.wind_direction(direction),
        'Current.WindGust': fmt.speed(gust),
        'Current.Pressure': ('%.1f kPa %s' % (pressure, tendency)).strip() if pressure is not None else '',
        'Current.Precipitation': percent(number(next_hour, 'lop', 'value')),
        'Current.UVIndex': celsius_number(number(next_hour, 'uv', 'index', 'value')),
        'Current.OutlookIcon': '%s.png' % code,
        'Current.FanartCode': code,
        'Current.Station': source,
        'Current.ObservationTime': fmt.clock(observed),
        'Current.IsFetched': 'true' if temp is not None else '',
        'Today.Sunrise': fmt.clock(parse_time(text(city, 'riseSet', 'sunrise'))),
        'Today.Sunset': fmt.clock(parse_time(text(city, 'riseSet', 'sunset'))),
        'Today.IsFetched': 'true',
        'Forecast.City': text(city, 'name'),
        'Forecast.Country': text(city, 'region'),
        'Forecast.Updated': fmt.clock(parse_time(text(city, 'lastUpdated'))),
    })
    return temp


def _hourly(props, hours, fmt, today):
    for i, hour in enumerate(hours, 1):
        moment = parse_time(hour.get('timestamp'))
        temp = number(hour, 'temperature', 'value')
        chill, humidex = number(hour, 'windChill', 'value'), number(hour, 'humidex', 'value')
        code = icon_code(number(hour, 'iconCode', 'value'))
        prefix = 'Hourly.%d.' % i
        props.update({
            prefix + 'Time': fmt.clock(moment),
            prefix + 'ShortDate': fmt.relative_date(fmt.local(moment).date(), today) if moment else '',
            prefix + 'LongDate': fmt.short_date(fmt.local(moment).date()) if moment else '',
            prefix + 'Temperature': fmt.temperature(temp),
            prefix + 'FeelsLike': fmt.temperature(next((v for v in (chill, humidex) if v is not None), temp)),
            prefix + 'Outlook': text(hour, 'condition'),
            prefix + 'OutlookIcon': '%s.png' % code,
            prefix + 'FanartCode': code,
            prefix + 'WindSpeed': fmt.speed(number(hour, 'wind', 'speed', 'value')),
            prefix + 'WindDirection': fmt.wind_direction(text(hour, 'wind', 'direction', 'value')),
            prefix + 'WindGust': fmt.speed(number(hour, 'wind', 'gust', 'value')),
            prefix + 'Precipitation': percent(number(hour, 'lop', 'value')),
            prefix + 'UVIndex': celsius_number(number(hour, 'uv', 'index', 'value')),
        })
    props['Hourly.IsFetched'] = 'true' if hours else ''


def _daily(props, city, hourly, today_known, fmt, today):
    forecasts = lookup(city, 'forecastGroup', 'forecasts') or []
    issued = parse_time(text(city, 'forecastGroup', 'timestamp'))
    if not forecasts or not issued:
        return
    hourly_pop, today_temps = {}, list(today_known)
    for hour in hourly:
        moment, pop = parse_time(hour.get('timestamp')), number(hour, 'lop', 'value')
        if moment and pop is not None:
            day = fmt.local(moment).date()
            hourly_pop[day] = max(pop, hourly_pop.get(day, 0))
        if moment and fmt.local(moment).date() == today:
            today_temps.append(number(hour, 'temperature', 'value'))
    today_temps = [t for t in today_temps if t is not None]

    # Kodi turns blank Day<N>.HighTemp/LowTemp into "0", so the legacy Day<N> set only gets
    # days with both values. An evening forecast starts with "Tonight" (no high): for that day
    # use the highest of the current temperature, the nowcast's whole-day high and the
    # forecast for the rest of today.
    day_slot = 0

    days = group_periods(forecasts, fmt.local(issued).date())[:MAX_DAYS]
    for i, entry in enumerate(days):
        day, night = entry['day'], entry['night']
        lead = day or night
        if entry['date'] <= today:
            long_day = short_day = text(lead, 'period', 'textForecastName') or fmt.localize(STR_TODAY)
        else:
            long_day, short_day = fmt.long_day(entry['date']), fmt.short_day(entry['date'])
        high = number(day, 'temperatures', 'temperature', 0, 'value') if day else None
        low = number(night, 'temperatures', 'temperature', 0, 'value') if night else None
        pops = [p for p in (chance_of_precipitation(day, night), hourly_pop.get(entry['date'])) if p is not None]
        outlook = text(lead, 'abbreviatedForecast', 'textSummary')
        code = icon_code(number(lead, 'abbreviatedForecast', 'icon', 'value'))
        summary = ' '.join('%s: %s' % (text(p, 'period', 'textForecastName'), text(p, 'textSummary'))
                           for p in (day, night) if p)
        prefix = 'Daily.%d.' % (i + 1)
        props.update({
            prefix + 'ShortDay': short_day,
            prefix + 'LongDay': long_day,
            prefix + 'ShortDate': fmt.short_date(entry['date']),
            prefix + 'LongDate': fmt.short_date(entry['date']),
            prefix + 'HighTemperature': fmt.temperature(high),
            prefix + 'LowTemperature': fmt.temperature(low),
            prefix + 'Outlook': outlook,
            prefix + 'OutlookIcon': '%s.png' % code,
            prefix + 'FanartCode': code,
            prefix + 'Precipitation': percent(max(pops)) if pops else '',
            prefix + 'WindSpeed': fmt.speed(number(lead, 'winds', 'periods', 0, 'speed', 'value')),
            prefix + 'WindDirection': fmt.wind_direction(text(lead, 'winds', 'periods', 0, 'direction')),
            prefix + 'Humidity': percent(number(lead, 'relativeHumidity', 'value')),
            prefix + 'UVIndex': text(day, 'uv', 'index') if day else '',
            prefix + 'Summary': summary,
        })
        day_high = high
        day_title = long_day
        if day_high is None and entry['date'] <= today and today_temps:
            day_high, day_title = max(today_temps), fmt.localize(STR_TODAY)
        if day_high is not None and low is not None and day_slot < DAY_SLOTS:
            props.update({
                'Day%d.Title' % day_slot: day_title,
                'Day%d.HighTemp' % day_slot: celsius_number(day_high),
                'Day%d.LowTemp' % day_slot: celsius_number(low),
                'Day%d.Outlook' % day_slot: outlook,
                'Day%d.OutlookIcon' % day_slot: '%s.png' % code,
                'Day%d.FanartCode' % day_slot: code,
            })
            day_slot += 1
    props['Forecast.IsFetched'] = 'true'
    props['Daily.IsFetched'] = 'true' if days else ''
