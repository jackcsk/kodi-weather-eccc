"""Generate media/kodi-weather-panel.png: a white rounded rectangle for the slideshow panel.

The corners are superellipse ("squircle") quarter curves, |x|^5 + |y|^5 = 1, which
approximate the continuous-curvature corners macOS/iOS use rather than circular arcs.
The skin draws it as a 9-slice image (<texture border="RADIUS">) tinted by colordiffuse,
so the corners keep their shape at any panel size. Pure standard library: no Pillow.

Usage: python3 make_panel_texture.py
"""
import os
import struct
import zlib

RADIUS = 40        # corner size in texture pixels; must match border="40" in SlideShow.xml
EXPONENT = 5.0     # 2 = circular arc; ~5 = Apple-style continuous corner
SIZE = 2 * RADIUS + 16
SUPERSAMPLE = 8
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'media', 'kodi-weather-panel.png')


def coverage(px, py):
    """Fraction (0..1) of pixel (px, py) inside the rounded rectangle."""
    # Fold every pixel into the top-left corner; only the corner squares are curved.
    cx = min(px, SIZE - 1 - px)
    cy = min(py, SIZE - 1 - py)
    if cx >= RADIUS or cy >= RADIUS:
        return 1.0
    inside = 0
    for sy in range(SUPERSAMPLE):
        for sx in range(SUPERSAMPLE):
            x = (RADIUS - (cx + (sx + 0.5) / SUPERSAMPLE)) / RADIUS
            y = (RADIUS - (cy + (sy + 0.5) / SUPERSAMPLE)) / RADIUS
            inside += abs(x) ** EXPONENT + abs(y) ** EXPONENT <= 1.0
    return inside / SUPERSAMPLE ** 2


def png(width, height, rows):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b''.join(b'\0' + bytes(row) for row in rows)
    header = struct.pack('!IIBBBBB', width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def main():
    rows = []
    for py in range(SIZE):
        row = []
        for px in range(SIZE):
            row += [255, 255, 255, round(255 * coverage(px, py))]
        rows.append(row)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'wb') as handle:
        handle.write(png(SIZE, SIZE, rows))
    print('wrote %s (%dx%d, corner %d px)' % (os.path.normpath(OUTPUT), SIZE, SIZE, RADIUS))


if __name__ == '__main__':
    main()
