#!/usr/bin/env python3
"""Install "Estuary (weather overlay)": a copy of Kodi's Estuary skin with a weather panel
on the picture slideshow.

Run it on the machine that runs Kodi:  python3 install_overlay.py
It copies the Estuary skin that ships with Kodi into your Kodi user folder as a new skin,
skin.estuary.weather, lays this folder's xml/ and media/ files over it, and copies your
Estuary skin settings across. Kodi's own Estuary is not modified.
Then restart Kodi and pick the skin in Settings > Interface > Skin.

Re-run it after upgrading Kodi so the copy follows the new Estuary.
"""
import argparse
import os
import shutil
import sys

SKIN_ID = 'skin.estuary.weather'
SKIN_NAME = 'Estuary (weather overlay)'
HERE = os.path.dirname(os.path.abspath(__file__))

# Where Kodi installs its bundled add-ons (Estuary lives there).
ESTUARY_CANDIDATES = [
    '/usr/share/kodi/addons/skin.estuary',                                   # Linux packages, LibreELEC
    '/usr/local/share/kodi/addons/skin.estuary',                             # Linux, built from source
    '/Applications/Kodi.app/Contents/Resources/Kodi/addons/skin.estuary',    # macOS
    os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'), 'Kodi', 'addons', 'skin.estuary'),  # Windows
]
# Kodi's per-user data folder.
KODI_HOME_CANDIDATES = [
    '/storage/.kodi',                                                        # LibreELEC / CoreELEC
    os.path.expanduser('~/.kodi'),                                           # Linux
    os.path.expanduser('~/Library/Application Support/Kodi'),                # macOS
    os.path.join(os.environ.get('APPDATA', ''), 'Kodi'),                     # Windows
]


def first_existing(paths, what, option):
    for path in paths:
        if path and os.path.isdir(path):
            return path
    sys.exit('Could not find %s. Pass it with %s. Looked in:\n  %s' % (what, option, '\n  '.join(p for p in paths if p)))


def install(estuary, kodi_home):
    target = os.path.join(kodi_home, 'addons', SKIN_ID)
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(estuary, target)

    manifest = os.path.join(target, 'addon.xml')
    with open(manifest, encoding='utf-8') as handle:
        xml = handle.read()
    if 'id="skin.estuary"' not in xml:
        sys.exit('%s does not look like the Estuary skin' % estuary)
    xml = xml.replace('id="skin.estuary"', 'id="%s"' % SKIN_ID, 1).replace('name="Estuary"', 'name="%s"' % SKIN_NAME, 1)
    with open(manifest, 'w', encoding='utf-8') as handle:
        handle.write(xml)

    # Kodi loads images missing from media/Textures.xbt straight from media/.
    for folder in ('xml', 'media'):
        shutil.copytree(os.path.join(HERE, folder), os.path.join(target, folder), dirs_exist_ok=True)

    settings_src = os.path.join(kodi_home, 'userdata', 'addon_data', 'skin.estuary', 'settings.xml')
    settings_dst = os.path.join(kodi_home, 'userdata', 'addon_data', SKIN_ID, 'settings.xml')
    if os.path.exists(settings_src) and not os.path.exists(settings_dst):
        os.makedirs(os.path.dirname(settings_dst), exist_ok=True)
        shutil.copyfile(settings_src, settings_dst)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--estuary', help="Kodi's bundled Estuary skin folder (auto-detected)")
    parser.add_argument('--kodi-home', help="Kodi's user data folder, the one containing addons/ and userdata/ "
                                            '(auto-detected)')
    args = parser.parse_args()
    estuary = args.estuary or first_existing(ESTUARY_CANDIDATES, "Kodi's Estuary skin", '--estuary')
    kodi_home = args.kodi_home or first_existing(KODI_HOME_CANDIDATES, "Kodi's user data folder", '--kodi-home')
    target = install(estuary, kodi_home)
    print('Installed %s\n  from %s\n  to   %s' % (SKIN_NAME, estuary, target))
    print('Next: restart Kodi, then Settings > Interface > Skin > "%s".' % SKIN_NAME)


if __name__ == '__main__':
    main()
