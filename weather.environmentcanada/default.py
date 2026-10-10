"""Kodi weather add-on entry point.

Kodi runs this with argv[1] = location index ('1'..'3') to refresh the weather window.
The settings dialog runs it with 'find<N>' to search for location N.
"""
import sys

from lib import addon

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode.startswith('find'):
        addon.find_location(mode[len('find'):])
    elif mode:
        addon.refresh(mode)
