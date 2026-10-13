"""Tests for the ECCC -> Kodi property transform. Run: python3 -m unittest discover tests"""
import json
import os
import sys
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'weather.environmentcanada'))

from lib import eccc  # noqa: E402

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
STRINGS = {33006: 'Today', 33007: 'Tomorrow', 83: 'W', 87: 'VAR'}
STRINGS.update({11 + i: day for i, day in enumerate(DAYS)})
STRINGS.update({41 + i: day[:3] for i, day in enumerate(DAYS)})
# Fixtures were captured 2026-10-09 ~17:35 EDT (Friday).
NOW = datetime(2026, 10, 9, 21, 40, tzinfo=timezone.utc)


def fixture(name):
    with open(os.path.join(HERE, 'fixtures', name), encoding='utf-8') as handle:
        return json.load(handle)['properties']


def formatter():
    return eccc.Formatter(localize=lambda string_id: STRINGS.get(string_id, '#%d' % string_id),
                          timefmt='%I:%M:%S %p', datefmt='%d/%m/%Y', tz=ZoneInfo('America/Toronto'))


def period(name, value, temp, icon=2, summary=''):
    return {
        'period': {'textForecastName': {'en': name}, 'value': {'en': value}},
        'temperatures': {'temperature': [{'value': {'en': temp}}]},
        'abbreviatedForecast': {'icon': {'value': icon}, 'textSummary': {'en': name + ' outlook'}},
        'textSummary': {'en': summary},
    }


class PeriodPairing(unittest.TestCase):
    def test_evening_issue_starts_with_tonight_low_only(self):
        props = eccc.build_properties(fixture('markham-on-85.json'), 'Markham, ON', formatter(), NOW)
        self.assertEqual(('Tonight', '', '2°C'), (props['Daily.1.ShortDay'], props['Daily.1.HighTemperature'],
                                                  props['Daily.1.LowTemperature']))
        dates = [props['Daily.%d.ShortDate' % i] for i in range(1, 8)]
        self.assertEqual(['09/10', '10/10', '11/10', '12/10', '13/10', '14/10', '15/10'], dates)
        self.assertEqual(('Thursday', '15°C', ''), (props['Daily.7.LongDay'], props['Daily.7.HighTemperature'],
                                                    props['Daily.7.LowTemperature']))

    def test_legacy_day_slots_never_carry_blank_temperatures(self):
        # Kodi renders blank Day<N> temperatures as 0: today's high falls back to observed/hourly
        # values, and the final day (no night period yet) is left out.
        props = eccc.build_properties(fixture('markham-on-85.json'), 'Markham, ON', formatter(), NOW)
        self.assertEqual(('Today', '19', '2'), (props['Day0.Title'], props['Day0.HighTemp'], props['Day0.LowTemp']))
        self.assertEqual(('Saturday', '18', '11'), (props['Day1.Title'], props['Day1.HighTemp'], props['Day1.LowTemp']))
        self.assertEqual('Wednesday', props['Day5.Title'])
        self.assertEqual('', props['Day6.Title'])

    def test_morning_issue_pairs_today_with_tonight(self):
        city = fixture('markham-on-85.json')
        city['forecastGroup']['timestamp'] = {'en': '2026-10-09T09:30:00Z'}
        city['forecastGroup']['forecasts'] = [
            period('Today', 'Friday', 15, summary='Sunny. 30 percent chance of showers late.'),
            period('Tonight', 'Friday night', 5, summary='Cloudy. 60 percent chance of showers.'),
            period('Saturday', 'Saturday', 12),
        ]
        props = eccc.build_properties(city, 'Markham, ON', formatter(), NOW)
        self.assertEqual(('Today', '15', '5'), (props['Day0.Title'], props['Day0.HighTemp'], props['Day0.LowTemp']))
        self.assertEqual(('12°C', ''), (props['Daily.2.HighTemperature'], props['Daily.2.LowTemperature']))
        self.assertEqual('60%', props['Daily.1.Precipitation'])
        self.assertEqual('', props['Day1.Title'])


class CurrentConditions(unittest.TestCase):
    def test_automatic_station_uses_next_hour_condition(self):
        props = eccc.build_properties(fixture('richmond-hill-on-59.json'), 'Richmond Hill, ON', formatter(), NOW)
        self.assertEqual('King City North', props['Current.Station'])
        self.assertEqual(('Sunny', '32.png'), (props['Current.Condition'], props['Current.OutlookIcon']))
        self.assertEqual('16', props['Current.Temperature'])

    def test_feels_like_ignores_reported_wind_chill_when_warm(self):
        city = fixture('markham-on-85.json')
        self.assertEqual(-5, city['currentConditions']['windChill']['value']['en'])
        props = eccc.build_properties(city, 'Markham, ON', formatter(), NOW)
        self.assertEqual('19', props['Current.FeelsLike'])

    def test_feels_like_thresholds(self):
        self.assertEqual(-20, eccc.round_half_up(eccc.feels_like(-10, 30, None)))
        self.assertEqual(-10, eccc.feels_like(-10, 4, None))
        self.assertEqual(20, eccc.feels_like(20, 10, 5))
        self.assertGreater(eccc.feels_like(30, 10, 22), 38)

    def test_alerts_drop_after_expiry(self):
        city = fixture('markham-on-85.json')
        self.assertEqual('Yellow Advisory - Frost', eccc.build_properties(city, 'M', formatter(), NOW)['Alerts'])
        after = datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc)
        self.assertEqual('', eccc.build_properties(city, 'M', formatter(), after)['Alerts'])

    def test_fresh_nowcast_replaces_distant_station_observation(self):
        city = fixture('markham-on-85.json')
        nowcast = {'time': datetime(2026, 10, 9, 21, 30, tzinfo=timezone.utc), 'temp': 16.6, 'humidity': 45,
                   'dewpoint': 4.6, 'wind': 14.0, 'gust': 30.0, 'direction': eccc.compass(275)}
        props = eccc.build_properties(city, 'Markham, ON', formatter(), NOW, nowcast=nowcast)
        self.assertEqual(('17', 'W', 'Open-Meteo model at Markham'),
                         (props['Current.Temperature'], props['Current.WindDirection'], props['Current.Station']))
        self.assertEqual('Sunny', props['Current.Condition'])  # site's next-hour forecast, not Billy Bishop's sky
        stale = dict(nowcast, time=datetime(2026, 10, 9, 20, 30, tzinfo=timezone.utc))
        props = eccc.build_properties(city, 'Markham, ON', formatter(), NOW, nowcast=stale)
        self.assertEqual(('19', 'Toronto City Centre Airport'), (props['Current.Temperature'], props['Current.Station']))

    def test_current_temperature_label_keeps_one_decimal(self):
        fmt = formatter()
        self.assertEqual(('15.4°C', '0.0°C', '-0.1°C', '15°C'),
                         (fmt.temperature(15.44, 1), fmt.temperature(-0.04, 1), fmt.temperature(-0.06, 1),
                          fmt.temperature(15.44)))
        props = eccc.build_properties(fixture('markham-on-85.json'), 'Markham, ON', fmt, NOW)
        self.assertEqual(('19.4°C', '19'), (props['Current.TemperatureLabel'], props['Current.Temperature']))

    def test_three_digit_temperatures_drop_the_decimal(self):
        # Keeps the label within the slideshow panel's width ('-88.8°C' is the widest that fits).
        fahrenheit = eccc.Formatter(localize=str, tempunit='°F')
        self.assertEqual(('-128°F', '99.9°F', '100°F', '-88.8°C'),
                         (fahrenheit.temperature(-88.8, 1), fahrenheit.temperature(37.7, 1),
                          fahrenheit.temperature(38, 1), formatter().temperature(-88.8, 1)))


class Slots(unittest.TestCase):
    def test_finished_hours_are_dropped(self):
        later = datetime(2026, 10, 9, 23, 30, tzinfo=timezone.utc)
        props = eccc.build_properties(fixture('markham-on-85.json'), 'Markham, ON', formatter(), later)
        self.assertEqual('7:00 PM', props['Hourly.1.Time'])

    def test_slots_beyond_data_are_blank(self):
        city = fixture('markham-on-85.json')
        city['hourlyForecastGroup']['hourlyForecasts'] = city['hourlyForecastGroup']['hourlyForecasts'][:3]
        city['forecastGroup']['forecasts'] = city['forecastGroup']['forecasts'][:3]
        props = eccc.build_properties(city, 'Markham, ON', formatter(), NOW)
        self.assertNotEqual('', props['Hourly.3.Time'])
        self.assertEqual('', props['Hourly.4.Time'])
        self.assertEqual('', props['Day2.Title'])
        self.assertEqual('', props['Daily.3.HighTemperature'])


class FailedRefresh(unittest.TestCase):
    def test_failure_blanks_readings_and_recovery_clears_message(self):
        # Kodi window properties persist between refreshes; publishing only sets the keys given.
        window = {}
        city = fixture('markham-on-85.json')
        window.update(eccc.build_properties(city, 'Markham, ON', formatter(), NOW))
        window.update(eccc.unavailable_properties('Markham, ON', 'Weather unavailable since 5:55 PM'))
        self.assertEqual(('', '', '', 'Markham, ON', 'Weather unavailable since 5:55 PM'),
                         (window['Current.TemperatureLabel'], window['Hourly.1.Time'], window['Alerts'],
                          window['Location'], window['Unavailable']))
        window.update(eccc.build_properties(city, 'Markham, ON', formatter(), NOW))
        self.assertEqual(('19.4°C', ''), (window['Current.TemperatureLabel'], window['Unavailable']))


if __name__ == '__main__':
    unittest.main()
