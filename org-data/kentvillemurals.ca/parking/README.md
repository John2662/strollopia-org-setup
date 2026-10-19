# Kentville downtown parking

Parking and public washrooms for downtown Kentville, traced from the Town of
Kentville's **Downtown Parking Map** (`ParkingMap2025.pdf`, April 2025, from
https://www.kentville.ca/streets-and-parking). The map is the Town's work:
get their OK before it is shown publicly beyond the demo, and credit them
(each card names the source).

Imported into the **business map** (map 31) on prod on 2026-10-19 for the
pitch demo, with the "park once" walking view (Routes & Parking add-on).

## Files

| File | What it is |
|---|---|
| `kentville-downtown-parking.geojson` | 42 features: 36 areas (`kind: area`) and 6 washrooms (`kind: poi`), each with `category`, `name`, `street`, `street_distance_m`; areas also `color`, `area_m2`, `lot`, `note` |
| `extract_parking.py` | PDF page image to GeoJSON (see below) |
| `import_parking.py` | Imports the GeoJSON into the business map; reuses the Wolfville importer |
| `osm-streets.geojson` | Named roads around downtown from OpenStreetMap (ODbL), for the street names and the control points |
| `extraction-preview.png` | The source map with every traced area outlined in red and each washroom circled |

| Category | Count | Colour | Walking minutes |
|---|---|---|---|
| 2 Hour Parking | 28 on-street stretches + 2 lots (Centre Square, Recreation Centre) | `#0085ca` | 10 |
| All Day Parking (free) | 6 lots | `#9aab1f` | 15 |
| Public Washroom (Visitor Services) | 6 points | `#555555` | - |

## How it was made

Unlike Wolfville's map, this PDF is a drawing (CorelDRAW): no coordinates,
not to scale. So:

1. `pdftoppm -r 300 -png ParkingMap2025.pdf page` renders it.
2. `extract_parking.py` maps pixels to coordinates with a second-order
   polynomial fitted to 11 street corners matched by hand with OpenStreetMap
   (`CONTROL_POINTS`; it prints each corner's error: 1-6 m downtown, up to
   about 20 m at the north corners of Aberdeen Street). It traces the legend
   colours (2-hour blue, all-day green), fills the holes left by labels and
   icons, names the lots from `LOT_NAMES`, and names each on-street stretch
   after the nearest street on the map that runs the same way.
3. The washrooms are placed by hand (`WASHROOMS`, icon centres).

```bash
pdftoppm -r 300 -png media/ParkingMap2025.pdf /tmp/kparking
python extract_parking.py /tmp/kparking-1.png osm-streets.geojson \
    kentville-downtown-parking.geojson extraction-preview.png
```

Needs `numpy pillow scipy shapely pyproj scikit-image`. The PDF itself is
not committed.

Positions are good to the block, not the metre. The stretches follow the
drawing, which straightens and widens streets.

## Importing

```bash
python org-data/kentvillemurals.ca/parking/import_parking.py --dry-run
USE_PROD=1 python org-data/kentvillemurals.ca/parking/import_parking.py
```

It adds the categories Parking (2 Hour, All Day) and Visitor Services
(Public Washroom), then the 36 areas (each with a linked POI and a text
card) and the 6 washroom POIs. Names already on the map are skipped. There
is no toilet glyph in the shared library, so washrooms use the default pin.
Dev still has Kentville under its old name (`--org kentville.strollopia.com`),
but its admin login differs, so dev was not used.

Then the walking view: `~/setup_kentville_addons.py` (a copy of the
Wolfville setup script) activates `walking_routes` for kentvillemurals.ca,
maps 2 Hour = 10 min and All Day = 15 min, and hides Parking from the
"within walking distance" list; then `compute_reach_areas --org
kentvillemurals.ca` on the server.
