"""Extract parking areas and icon points from the georeferenced Wolfville
Downtown Parking PDF (Map 23A, 2024-07-26), rendered at 600 dpi.

Usage: extract_parking.py <hi-res png> <out.geojson> <preview.png>
"""
import json
import sys

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage
from shapely.geometry import Polygon, mapping
from shapely.ops import transform as shp_transform
from skimage import measure

Image.MAX_IMAGE_PIXELS = None
src, out_path, preview_path = sys.argv[1:4]
img = Image.open(src).convert('RGB')
a = np.asarray(img).astype(int)

# GDAL's GeoTransform for the page at 150 dpi; this image is 600 dpi (x4).
GT = (392309.5694855741, 0.5797237803258525 / 4, 0.1234115363321264 / 4,
      4994323.630116448, 0.1234590552030401 / 4, -0.5795421120944897 / 4)
to_wgs = Transformer.from_crs('EPSG:2961', 'EPSG:4326', always_xy=True)  # NAD83(CSRS) UTM 20N


def px_to_lonlat(col, row):
    x = GT[0] + col * GT[1] + row * GT[2]
    y = GT[3] + col * GT[4] + row * GT[5]
    return to_wgs.transform(x, y)


# Map body only (inside the frame, above the legend), in 600 dpi pixels.
X0, X1, Y0, Y1 = 610, 6285, 735, 4315
body = np.zeros(a.shape[:2], bool)
body[Y0:Y1, X0:X1] = True


def colour_mask(rgb, tol):
    d = np.sqrt(((a - np.array(rgb)) ** 2).sum(axis=2))
    return (d <= tol) & body


AREAS = [
    # (category, legend colour sampled from the PDF, colour for Strollopia)
    ('1 Hr Parking', (164, 162, 51), '#a4a233'),
    ('3 Hr Parking', (51, 168, 165), '#33a8a5'),
    ('All Day Parking', (234, 62, 130), '#ea3e82'),
]
MIN_AREA_M2 = 40  # drops slivers; a single parking space is ~12.5 m2
PX_M2 = abs(GT[1] * GT[5] - GT[2] * GT[4])

features = []
prev = img.copy()
draw = ImageDraw.Draw(prev, 'RGBA')

for cat, rgb, colour in AREAS:
    m = colour_mask(rgb, 40)
    # Labels and icons printed on top of a lot leave holes; close and fill them.
    m = ndimage.binary_closing(m, structure=np.ones((9, 9)))
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    k = 0
    for i in range(1, n + 1):
        comp = lab == i
        if comp.sum() * PX_M2 < MIN_AREA_M2:
            continue
        contours = measure.find_contours(np.pad(comp, 1).astype(float), 0.5)
        ring = max(contours, key=len) - 1  # (row, col), undo padding
        poly_px = Polygon([(c, r) for r, c in ring]).simplify(4)  # ~0.6 m at 600 dpi
        if not poly_px.is_valid or poly_px.is_empty:
            poly_px = poly_px.buffer(0)
        draw.polygon(list(poly_px.exterior.coords), outline=(0, 0, 0, 255), fill=None, width=6)
        poly = shp_transform(lambda xs, ys: px_to_lonlat(np.array(xs), np.array(ys)), poly_px)
        k += 1
        features.append({
            'type': 'Feature',
            'geometry': mapping(poly),
            'properties': {
                'kind': 'area', 'category': cat, 'name': f'{cat} {k}', 'color': colour,
                'area_m2': round(comp.sum() * PX_M2),
            },
        })
    print(f'{cat}: {k} areas')

ICONS = [
    ('Accessible Parking', (0, 112, 255), 30),
    ('Loading Zone', (29, 117, 188), 22),
]
for cat, rgb, tol in ICONS:
    m = ndimage.binary_closing(colour_mask(rgb, tol), structure=np.ones((7, 7)))
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    pts = []
    for sl, i in zip(ndimage.find_objects(lab), range(1, n + 1)):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if not (40 <= h <= 140 and 40 <= w <= 140):  # icon squares are ~70-80 px
            continue
        r, c = ndimage.center_of_mass(lab[sl] == i)
        pts.append((sl[1].start + c, sl[0].start + r))
    for k, (c, r) in enumerate(pts, 1):
        draw.ellipse([c - 30, r - 30, c + 30, r + 30], outline=(255, 0, 0, 255), width=8)
        lon, lat = px_to_lonlat(c, r)
        features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                         'properties': {'kind': 'poi', 'category': cat, 'name': f'{cat} {k}'}})
    print(f'{cat}: {len(pts)} points')

# Bus stops: solid black rounded icons with a white bus; text strokes are thin,
# so keep black blobs that are icon-sized and mostly filled after closing.
black = (a.sum(axis=2) < 60) & body
m = ndimage.binary_fill_holes(ndimage.binary_closing(black, structure=np.ones((11, 11))))
lab, n = ndimage.label(m)
pts = []
for sl, i in zip(ndimage.find_objects(lab), range(1, n + 1)):
    h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
    comp = lab[sl] == i
    if 55 <= h <= 120 and 50 <= w <= 110 and comp.mean() > 0.7 and black[sl][comp].mean() > 0.5:
        # Anchor at the icon's bottom tip (it's a pin shape).
        pts.append((sl[1].start + w / 2, sl[0].stop))
for k, (c, r) in enumerate(pts, 1):
    draw.ellipse([c - 30, r - 30, c + 30, r + 30], outline=(0, 200, 0, 255), width=8)
    lon, lat = px_to_lonlat(c, r)
    features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                     'properties': {'kind': 'poi', 'category': 'Bus Stop', 'name': f'Bus Stop {k}'}})
print(f'Bus Stop: {len(pts)} points')

json.dump({'type': 'FeatureCollection', 'name': 'wolfville-downtown-parking-2024-07-26',
           'source': 'Town of Wolfville, Map 23A Downtown Parking, 2024-07-26 (georeferenced PDF)',
           'features': features}, open(out_path, 'w'), indent=1)
prev.resize((prev.width // 3, prev.height // 3)).save(preview_path)
