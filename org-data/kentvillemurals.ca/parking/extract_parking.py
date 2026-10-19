"""Extract Kentville's downtown parking from the Town's ParkingMap2025.pdf.

The PDF is a drawing (CorelDRAW), not a georeferenced map, so the pixel to
map transform is a second-order polynomial fit to street corners matched
by hand with OpenStreetMap (CONTROL_POINTS below; it prints the residuals). Positions are good
to the block, not the metre.

Usage (page rendered at 300 dpi with `pdftoppm -r 300 -png`):
    extract_parking.py <page png> <osm-streets.geojson> <out.geojson> <preview.png>
"""
import collections
import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer
from scipy import ndimage
from shapely.geometry import LineString, Point, Polygon, mapping, shape
import warnings
from shapely.ops import transform as shp_transform
from skimage import measure

warnings.filterwarnings('ignore', category=DeprecationWarning)
src, streets_path, out_path, preview_path = sys.argv[1:5]
img = Image.open(src).convert('RGB')
a = np.asarray(img).astype(int)
K = img.width / 1210  # control points were read on a 110 dpi render (1210 px wide)

to_utm = Transformer.from_crs('EPSG:4326', 'EPSG:2961', always_xy=True)  # NAD83(CSRS) UTM 20N
to_wgs = Transformer.from_crs('EPSG:2961', 'EPSG:4326', always_xy=True)

# (corner, x, y on the 110 dpi render, lat, lon of the OSM intersection node)
CONTROL_POINTS = [
    ('Aberdeen St / Main St', 618, 682, 45.0772503, -64.4966945),
    ('Aberdeen St / Webster St', 618, 482, 45.0783272, -64.4964409),
    ('Aberdeen St / Station Ln', 618, 388, 45.0788421, -64.4963314),
    ('Bridge St / Webster St', 925, 490, 45.0780273, -64.4942081),
    ('Bridge St / Station Ln', 908, 388, 45.0785407, -64.4941950),
    ('Bridge St / Main St', 932, 692, 45.0767973, -64.4940675),
    ('Webster St / Main St (west)', 93, 676, 45.0776906, -64.5008994),
    ('Station Ln / Webster St (west)', 475, 478, 45.0784631, -64.4975790),
    ('Aberdeen St / River St', 735, 213, 45.0795858, -64.4953723),
    ('Aberdeen St / Bridge St (north)', 790, 165, 45.0799842, -64.4944997),
    ('River St / Webster St (west)', 100, 490, 45.0785946, -64.5002783),
]


def terms(col, row):
    """Second-order polynomial terms: the drawing bends a little (streets
    are straightened and blocks resized), which an affine fit can't follow."""
    col, row = np.asarray(col, float) / 1000, np.asarray(row, float) / 1000
    return np.stack([np.ones_like(col), col, row, col * row, col ** 2, row ** 2], axis=-1)


P = terms([x * K for _, x, *_ in CONTROL_POINTS], [y * K for _, _, y, *_ in CONTROL_POINTS])
E = np.array([to_utm.transform(lon, lat) for *_, lat, lon in CONTROL_POINTS])
COEF, *_ = np.linalg.lstsq(P, E, rcond=None)
for (name, *_), err in zip(CONTROL_POINTS, np.hypot(*(P @ COEF - E).T)):
    print(f'  control point {name:32s} {err:5.1f} m')
# m2 per pixel near the middle of downtown (Centre Square), for the size filter
_c = np.array([700 * K, 580 * K])
_J = np.array([(terms(*(_c + d)) @ COEF - terms(*_c) @ COEF) for d in ([1, 0], [0, 1])])
PX_M2 = abs(np.linalg.det(_J))


def px_to_lonlat(col, row):
    x, y = np.moveaxis(terms(col, row) @ COEF, -1, 0)
    return to_wgs.transform(x, y)


# Map body only: drop the legend swatches and the title (110 dpi px boxes).
body = np.ones(a.shape[:2], bool)
for x0, y0, x1, y1 in [(330, 60, 700, 175), (30, 30, 320, 200)]:
    body[int(y0 * K):int(y1 * K), int(x0 * K):int(x1 * K)] = False


def colour_mask(rgb, tol):
    d = np.sqrt(((a - np.array(rgb)) ** 2).sum(axis=2))
    return (d <= tol) & body


# legend colour -> category, colour used in Strollopia
AREAS = [
    ('2 Hour Parking', (0, 133, 202), '#0085ca'),
    ('All Day Parking', (190, 209, 43), '#9aab1f'),
]
MIN_AREA_M2 = 40

# Lots get a descriptive name instead of "<category> - <street>": matched by
# which of these 110 dpi points falls inside the extracted polygon.
LOT_NAMES = {
    (1000, 250): 'All Day Parking - Department of Justice lot',
    (790, 345): 'All Day Parking - Bridge Street and Station Lane',
    (505, 420): 'All Day Parking - Webster Street lot',
    (250, 540): 'All Day Parking - Centennial Arena',
    (870, 770): 'All Day Parking - Recreation Centre (6 AM to 10 PM only)',
    (797, 327): '2 Hour Parking - Bridge Street and Station Lane lot',
    (745, 855): 'All Day Parking - Gaspereau Press lot',
    (760, 580): '2 Hour Parking - Centre Square',
    (935, 720): '2 Hour Parking - Recreation Centre',
}
NOTES = {
    'All Day Parking - Recreation Centre (6 AM to 10 PM only)': 'Open 6 AM to 10 PM only.',
}

# Public washrooms (centre of each icon, 110 dpi px) and the building they're in.
WASHROOMS = [
    (290, 292, 'Kentville Police Department'),
    (818, 350, 'Bridge Street and Station Lane lot'),
    (951, 527, 'Webster Court'),
    (357, 645, 'Volunteer Fire Department'),
    (510, 746, 'Main Street'),
    (855, 738, 'Town Hall and Recreation Centre'),
]

# Streets drawn on the Town's map; on-street stretches are named after the nearest of these.
MAP_STREETS = {'Main Street', 'Webster Street', 'Aberdeen Street', 'Station Lane', 'River Street',
               'Bridge Street', 'Webster Court', 'Justice Way'}
utm = to_utm.transform
streets = [(f['properties']['name'], shp_transform(utm, shape(f['geometry'])))
           for f in json.load(open(streets_path))['features']
           if f['properties'].get('name') in MAP_STREETS]

features = []
prev = img.copy()
draw = ImageDraw.Draw(prev, 'RGBA')

for cat, rgb, colour in AREAS:
    m = ndimage.binary_closing(colour_mask(rgb, 45), structure=np.ones((9, 9)))
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    for i in range(1, n + 1):
        comp = lab == i
        if comp.sum() * PX_M2 < MIN_AREA_M2:
            continue
        contours = measure.find_contours(np.pad(comp, 1).astype(float), 0.5)
        ring = max(contours, key=len) - 1
        poly_px = Polygon([(c, r) for r, c in ring]).simplify(3)
        if not poly_px.is_valid:
            poly_px = poly_px.buffer(0)
        name = next((v for (x, y), v in LOT_NAMES.items() if poly_px.contains(Point(x * K, y * K))), None)
        draw.polygon(list(poly_px.exterior.coords), outline=(255, 0, 0, 255), width=4)
        poly = shp_transform(lambda xs, ys: px_to_lonlat(np.array(xs), np.array(ys)), poly_px)
        features.append({'type': 'Feature', 'geometry': mapping(poly), 'properties': {
            'kind': 'area', 'category': cat, 'name': name, 'color': colour,
            'area_m2': round(comp.sum() * PX_M2), 'lot': name is not None,
            'note': NOTES.get(name, ''),
        }})

for x, y, where in WASHROOMS:
    lon, lat = px_to_lonlat(np.array(x * K), np.array(y * K))
    draw.ellipse([x * K - 25, y * K - 25, x * K + 25, y * K + 25], outline=(255, 0, 0, 255), width=6)
    features.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [float(lon), float(lat)]},
                     'properties': {'kind': 'poi', 'category': 'Public Washroom',
                                    'name': f'Public Washroom - {where}', 'where': where}})

# Street names for the on-street stretches (and every area's card text).


def heading(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180


def street_heading_near(line, pt):
    """Heading of the street segment closest to pt."""
    seg = min(zip(line.coords, line.coords[1:]), key=lambda s: LineString(s).distance(pt))
    return heading(*seg)


def nearest_street(g):
    """Nearest map street; for a long thin stretch, only streets running the
    same way (within 35 degrees) count, so a stretch beside a corner is named
    after the street it lines, not the one it touches."""
    rect = g.minimum_rotated_rectangle
    c = list(rect.exterior.coords) if rect.geom_type == 'Polygon' else []
    candidates = streets
    if len(c) >= 4:
        sides = sorted([(math.dist(c[0], c[1]), c[0], c[1]), (math.dist(c[1], c[2]), c[1], c[2])])
        (short, *_), (long_, a, b) = sides
        if long_ > 2.5 * short:
            h = heading(a, b)
            pt = g.centroid
            candidates = [(nm, s) for nm, s in streets
                          if min(abs(street_heading_near(s, pt) - h), 180 - abs(street_heading_near(s, pt) - h)) < 35]
    return min((g.distance(s), nm) for nm, s in candidates or streets)


counts = collections.Counter()
for f in features:
    g = shp_transform(utm, shape(f['geometry']))
    dist, street = nearest_street(g)
    f['properties']['street'] = street
    f['properties']['street_distance_m'] = round(dist, 1)
    if not f['properties']['name']:
        counts[(f['properties']['category'], street)] += 1
seen = collections.Counter()
for f in sorted(features, key=lambda f: shape(f['geometry']).centroid.x):
    p = f['properties']
    if p['name']:
        continue
    key = (p['category'], p['street'])
    seen[key] += 1
    p['name'] = f"{p['category']} - {p['street']}" + (f' ({seen[key]})' if counts[key] > 1 else '')

json.dump({'type': 'FeatureCollection', 'name': 'kentville-downtown-parking-2025',
           'source': 'Town of Kentville, Downtown Parking Map (ParkingMap2025.pdf, April 2025)',
           'features': features}, open(out_path, 'w'), indent=1)
prev.resize((prev.width // 2, prev.height // 2)).save(preview_path)
for f in sorted(features, key=lambda f: f['properties']['name']):
    p = f['properties']
    print(f"  {p['name']:<62} {p.get('area_m2', ''):>6} m2  {p['street_distance_m']:>5} m from {p['street']}")
print(collections.Counter(f['properties']['category'] for f in features))
