#!/usr/bin/env python3
"""Build dist/weather.environmentcanada-<version>.zip for Kodi's "Install from zip file".

Kodi expects the zip to contain a single top-level folder named after the add-on id.
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_ID = 'weather.environmentcanada'
SKIP_DIRS = {'__pycache__'}
SKIP_SUFFIXES = ('.pyc', '.pyo')


def main():
    source = os.path.join(ROOT, ADDON_ID)
    with open(os.path.join(source, 'addon.xml'), encoding='utf-8') as handle:
        version = re.search(r'<addon\b[^>]*\bversion="([^"]+)"', handle.read()).group(1)
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    target = os.path.join(ROOT, 'dist', '%s-%s.zip' % (ADDON_ID, version))
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for folder, dirs, files in os.walk(source):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if name.endswith(SKIP_SUFFIXES) or name.startswith('.'):
                    continue
                path = os.path.join(folder, name)
                archive.write(path, os.path.join(ADDON_ID, os.path.relpath(path, source)))
    print(target)
    return 0


if __name__ == '__main__':
    sys.exit(main())
