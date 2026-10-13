"""Kodi glue shared by the weather entry point (default.py) and the refresh service (service.py)."""
import json
from datetime import datetime, timezone

import xbmc
import xbmcaddon
import xbmcgui

from . import eccc

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
LANGUAGE = ADDON.getLocalizedString
WEATHER_WINDOW = xbmcgui.Window(12600)
MAX_LOCATIONS = 3
FETCH_ATTEMPTS = 3
RETRY_SECONDS = 10
SERVICE_INTERVAL_SECONDS = 15 * 60

STR_SEARCH_HEADING = 14024   # Kodi: "Select location"
STR_NO_RESULTS = 284         # Kodi: "No results found"
STR_SELECT_PLACE = 32020
STR_SELECT_AREA = 32021
STR_NETWORK_ERROR = 32022
STR_UNAVAILABLE = 32023      # "Weather unavailable since %s"
# Kodi caches an add-on's strings until it restarts, so right after an update a new id reads as ''.
UNAVAILABLE_FALLBACK = 'Weather unavailable since %s'


def log(message, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, message), level)


def formatter():
    return eccc.Formatter(
        localize=xbmc.getLocalizedString,
        tempunit=xbmc.getRegion('tempunit'),
        speedunit=xbmc.getRegion('speedunit'),
        timefmt=xbmc.getRegion('time'),
        datefmt=xbmc.getRegion('dateshort'),
    )


def publish_locations():
    count = 0
    for index in range(1, MAX_LOCATIONS + 1):
        name = ADDON.getSettingString('loc%d_name' % index)
        WEATHER_WINDOW.setProperty('Location%d' % index, name)
        count += 1 if name else 0
    WEATHER_WINDOW.setProperty('Locations', str(count))


def configured_location(index):
    site_id = ADDON.getSettingString('loc%s_id' % index)
    if site_id:
        return site_id, ADDON.getSettingString('loc%s_name' % index)
    return ADDON.getSettingString('loc1_id'), ADDON.getSettingString('loc1_name')


def publish(props):
    for key, value in props.items():
        WEATHER_WINDOW.setProperty(key, value)


def publish_unavailable(name):
    # A failure streak keeps the time of its first failed refresh; a successful refresh clears it.
    message = WEATHER_WINDOW.getProperty('Unavailable')
    if not message:
        template = LANGUAGE(STR_UNAVAILABLE) or UNAVAILABLE_FALLBACK
        message = template % formatter().clock(datetime.now(timezone.utc))
    publish(eccc.unavailable_properties(name, message))


def kodi_setting(name):
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue', 'params': {'setting': name}}
    return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get('result', {}).get('value')


def run_refresh_service():
    """Refresh the weather window properties every 15 minutes while this add-on is Kodi's provider.

    Kodi's own weather refresh runs every 30 minutes and is not configurable, while the current
    conditions this add-on uses update every 15. The Weather.Refresh built-in can't help: it only
    reaches Kodi when the Weather window has been opened since start-up. So the service fetches and
    publishes the window properties itself. Skins reading Window(weather).Property(...) see every
    update; Kodi's own Weather.* labels still follow Kodi's 30-minute cycle.
    """
    log('service: refreshing weather every %d minutes' % (SERVICE_INTERVAL_SECONDS // 60))
    monitor = xbmc.Monitor()
    while not monitor.waitForAbort(SERVICE_INTERVAL_SECONDS):
        if kodi_setting('weather.addon') == ADDON_ID:
            refresh(str(kodi_setting('weather.currentlocation') or 1))


def refresh(index):
    publish_locations()
    site_id, name = configured_location(index)
    if not site_id:
        log('no location configured')
        publish(eccc.blank_properties())
        return
    monitor = xbmc.Monitor()
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            feature = eccc.fetch_city(site_id)
            break
        except Exception as error:  # network/HTTP/JSON failures all mean "no data this round"
            log('fetch %s failed (attempt %d): %r' % (site_id, attempt, error), xbmc.LOGWARNING)
            if attempt == FETCH_ATTEMPTS or monitor.waitForAbort(RETRY_SECONDS):
                publish_unavailable(name)
                return
    lon, lat = feature['geometry']['coordinates'][:2]
    try:
        nowcast = eccc.fetch_nowcast(lat, lon)
    except Exception as error:  # fall back to the city page's station observation
        log('nowcast %s failed: %r' % (site_id, error), xbmc.LOGWARNING)
        nowcast = None
    props = eccc.build_properties(feature['properties'], name, formatter(), nowcast=nowcast)
    publish(props)
    log('updated %s (%s), current from %s' % (name, site_id, props['Current.Station']))


def find_location(index):
    dialog = xbmcgui.Dialog()
    keyboard = xbmc.Keyboard(ADDON.getSettingString('loc%s_name' % index).split(',')[0],
                             xbmc.getLocalizedString(STR_SEARCH_HEADING), False)
    keyboard.doModal()
    query = keyboard.getText().split(',')[0].strip() if keyboard.isConfirmed() else ''
    if not query:
        return
    try:
        places = eccc.geocode(query)
        if not places:
            dialog.ok(ADDON_NAME, xbmc.getLocalizedString(STR_NO_RESULTS))
            return
        choice = 0
        if len(places) > 1:
            choice = dialog.select(LANGUAGE(STR_SELECT_PLACE), [
                '%s, %s' % (place['name'], place['admin1']) for place in places])
            if choice < 0:
                return
        sites = eccc.nearby_sites(places[choice]['lat'], places[choice]['lon'])
    except Exception as error:
        log('location search failed: %r' % error, xbmc.LOGERROR)
        dialog.ok(ADDON_NAME, LANGUAGE(STR_NETWORK_ERROR))
        return
    if not sites:
        dialog.ok(ADDON_NAME, xbmc.getLocalizedString(STR_NO_RESULTS))
        return
    items = []
    for site in sites:
        item = xbmcgui.ListItem('%s, %s' % (site['name'], site['province']),
                                '%.0f km - %s' % (site['km'], site['region']))
        items.append(item)
    choice = dialog.select(LANGUAGE(STR_SELECT_AREA), items, useDetails=True)
    if choice < 0:
        return
    site = sites[choice]
    ADDON.setSettingString('loc%s_name' % index, '%s, %s' % (site['name'], site['province']))
    ADDON.setSettingString('loc%s_id' % index, site['id'])
    log('location %s set to %s (%s)' % (index, site['name'], site['id']))
