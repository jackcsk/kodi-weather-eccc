# Weather panel on the picture slideshow (optional)

Kodi hides weather while a picture slideshow plays. This extra adds a panel in the top-right corner of
the slideshow:

- current temperature with one decimal, condition icon and text, feels-like
- today's high and low, chance of precipitation
- temperatures 1, 4 and 8 hours ahead
- the selected location, e.g. `Markham, ON`
- active weather alerts, in orange
- when the add-on can't fetch the weather, a short panel saying since when, e.g.
  `Weather unavailable since 3:55 PM`

It needs the `weather.environmentcanada` add-on set as Kodi's weather service. With another weather
add-on, the big temperature and the alert line stay empty.

## How it works

Kodi add-ons can't draw on top of a skin's slideshow, so this is a skin change. `install_overlay.py`
copies the Estuary skin that ships with Kodi into your Kodi user folder as a new skin,
**Estuary (weather overlay)** (`skin.estuary.weather`). It then replaces that copy's `SlideShow.xml`,
adds the rounded panel image, and copies your Estuary skin settings across. Kodi's own Estuary is not
touched, so you can switch back at any time.

`xml/SlideShow.xml` is written for Estuary 3.0.10 (Kodi 20) and was tested on Kodi 20.5.

## Install

On the machine running Kodi (for LibreELEC, over SSH):

```sh
python3 install_overlay.py
```

It finds Kodi's Estuary and your Kodi user folder on Linux, LibreELEC/CoreELEC, macOS and Windows. If it
can't, point it there:

```sh
python3 install_overlay.py --estuary /path/to/kodi/addons/skin.estuary --kodi-home /path/to/.kodi
```

Then:

1. Restart Kodi. If it asks whether to enable the new add-on, answer **Yes**. Otherwise enable it in
   **Settings → Add-ons → My add-ons → Look and feel → Skin → Estuary (weather overlay)**.
2. **Settings → Interface → Skin → Estuary (weather overlay)**, and confirm **Keep** when asked.
3. Kodi resets theme and colours when the skin changes; set them again under **Settings → Interface → Skin**
   if you had changed them.

Re-run `install_overlay.py` after upgrading Kodi, so the copy follows the new Estuary.

## Undo

**Settings → Interface → Skin → Estuary**. Then delete the `addons/skin.estuary.weather` folder in your
Kodi user folder, or uninstall it under **Settings → Add-ons → My add-ons → Look and feel → Skin**.

## Customize

- Position and size: the panel is the `<control type="group">` in `xml/SlideShow.xml`. Coordinates are in
  a 1920×1080 space and Kodi scales them to the screen.
- Corner shape: `python3 make_panel_texture.py` regenerates `media/kodi-weather-panel.png`. Change
  `RADIUS` (and `border="40"` in `SlideShow.xml` to match) or `EXPONENT` (2 = circular, ~5 = macOS-style).

Re-run `install_overlay.py` after editing, then reload the skin (or restart Kodi).

## Licence

GPL-2.0 (see [LICENSE](LICENSE)). `xml/SlideShow.xml` is derived from Kodi's Estuary skin by phil65 (Team
Kodi), whose code is licensed GPL-2.0.
