# Wolfville downtown parking

Parking areas, accessible-parking spaces, loading zones and bus stops for
downtown Wolfville, extracted from the Town of Wolfville's
**Map 23A - Downtown Parking (2024-07-26)**. The map is © Town of Wolfville and
marked "not for navigation or legal purposes": get the town's OK before
publishing it on a public map, and credit them (each area's description names
the source).

## Files

| File | What it is |
|---|---|
| `media/MAP 23A - DOWNTOWN PARKING - July 26, 2024.pdf` | The source PDF (pCloud symlink, not committed) |
| `wolfville-downtown-parking.geojson` | All 66 features: 32 parking areas (polygons) and 34 points, each with `kind` (`area`/`poi`), `category`, `name` and, for areas, `color`, `street`, `street_distance_m`, `area_m2` |
| `map-areas.json` | The 32 areas as payloads for `POST /api/geo/map-area/`; set `owning_map` first |
| `extraction-preview.png` | The source map with everything found outlined (areas) or circled (red: accessible and loading zones; green: bus stops) |
| `extract_parking.py` | Step 1: PDF image to GeoJSON |
| `name_areas.py` | Step 2: names each area after its nearest road |
| `osm-streets.geojson` | Roads around downtown from OpenStreetMap (ODbL), used by step 2 |

| Category | Count | Colour |
|---|---|---|
| 1 Hr Parking | 1 area | `#a4a233` |
| 3 Hr Parking | 19 areas | `#33a8a5` |
| All Day Parking | 12 areas | `#ea3e82` |
| Accessible Parking | 23 points | |
| Loading Zone | 7 points | |
| Bus Stop | 4 points | |

## How it was made

The PDF is a georeferenced (geospatial) PDF from Esri ArcMap: GDAL reads its
coordinate system (NAD83(CSRS) / UTM zone 20N, EPSG:2961) and pixel-to-map
transform. The map body is an image, not vectors, so:

1. `pdftoppm -r 600 -png` renders the page; the transform is GDAL's 150 dpi
   GeoTransform divided by 4.
2. `extract_parking.py` picks the legend's exact colours, fills holes left by
   labels and icons, drops slivers under 40 m², traces each area's outline,
   and finds the icons by colour (accessible blue `#0070ff`, loading-zone blue
   `#1d75bc`) or shape (solid black bus icons, anchored at their bottom tip).
3. `name_areas.py` names each area "<category> - <nearest road>", numbered left
   to right when a road has several.

Positions should be within a metre or two (1:3,500 map at 600 dpi), but they
haven't been checked against the real streets.

To re-run with a new version of the map (needs `numpy pillow scipy shapely
pyproj scikit-image`, and GDAL to read the new transform with `gdalinfo`;
update `GT` in `extract_parking.py` if it changed):

```bash
pdftoppm -r 600 -png "media/MAP 23A - DOWNTOWN PARKING - July 26, 2024.pdf" /tmp/parking
python extract_parking.py /tmp/parking-1.png /tmp/parking.geojson /tmp/preview.png
python name_areas.py /tmp/parking.geojson osm-streets.geojson wolfville-downtown-parking.geojson
```

## Known gaps

- Two accessible-parking icons that touch (Front Street, by the Railtown lot)
  came out as one point.
- Not extracted: the "No Parking" street edges and one-way arrows.
- Areas more than ~30 m from a road (`street_distance_m`) are lots set back
  from the street; their road name is the nearest, not necessarily the
  entrance.
- Not yet imported anywhere: choose the org's map and the POI categories
  first. `POST /api/geo/map-area/` accepts `create_poi: true` to also make a
  POI for each area.
