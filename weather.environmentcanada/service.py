"""Background service: refresh the weather window properties every 15 minutes.

Kodi's own weather refresh runs every 30 minutes and is not configurable, while the
current conditions this add-on uses update every 15. The Weather.Refresh built-in can't
help: it only reaches Kodi when the Weather window has been opened since start-up. So this
service fetches and publishes the window properties itself. Skins reading
Window(weather).Property(...) (like the slideshow panel) see every update; Kodi's own
Weather.* labels still follow Kodi's 30-minute cycle.
"""
import json

import xbmc

from lib import addon

INTERVAL_SECONDS = 15 * 60


def setting(name):
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'Settings.GetSettingValue', 'params': {'setting': name}}
    return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get('result', {}).get('value')


if __name__ == '__main__':
    addon.log('service: refreshing weather every %d minutes' % (INTERVAL_SECONDS // 60))
    monitor = xbmc.Monitor()
    while not monitor.waitForAbort(INTERVAL_SECONDS):
        if setting('weather.addon') == addon.ADDON_ID:
            addon.refresh(str(setting('weather.currentlocation') or 1))
