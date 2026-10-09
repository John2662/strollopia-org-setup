"""Name each parking area after its nearest street (OSM roads, not trails).
Usage: name_areas.py <parking.geojson> <streets.geojson> <out.geojson>"""
import collections, json, sys
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

ROADS = {'primary', 'secondary', 'tertiary', 'residential', 'unclassified', 'living_street', 'service'}
src, streets_path, out = sys.argv[1:4]
utm = Transformer.from_crs('EPSG:4326', 'EPSG:2961', always_xy=True).transform
streets = [(f['properties']['name'], transform(utm, shape(f['geometry'])))
           for f in json.load(open(streets_path))['features']
           if f['properties'].get('name') and f['properties'].get('highway') in ROADS
           and f['geometry']['type'] == 'LineString']
d = json.load(open(src))
areas = [f for f in d['features'] if f['properties']['kind'] == 'area']
named = collections.Counter()
for f in areas:
    poly = transform(utm, shape(f['geometry']))
    dist, street = min((poly.distance(g), n) for n, g in streets)
    f['properties']['street'] = street
    f['properties']['street_distance_m'] = round(dist, 1)
    named[(f['properties']['category'], street)] += 1
seen = collections.Counter()
for f in sorted(areas, key=lambda f: (f['properties']['category'], f['properties']['street'],
                                       shape(f['geometry']).centroid.x)):
    p = f['properties']
    key = (p['category'], p['street'])
    seen[key] += 1
    p['name'] = f"{p['category']} - {p['street']}" + (f" ({seen[key]})" if named[key] > 1 else '')
json.dump(d, open(out, 'w'), indent=1)
for f in areas:
    p = f['properties']; print(f"{p['name']:<45} {p['street_distance_m']:>5} m  {p['area_m2']} m2")
