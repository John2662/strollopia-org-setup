# Load-time comparison: legacy vs. new (2026-10-06)

Measured directly via HTTP (document + every real asset it loads: CSS, JS,
images, inline background-images — not nav links). Decompressed body sizes
throughout, for apples-to-apples comparison.

## Landing page

| | valleyartmap.ca (legacy) | valleyartmap.strollopia.com (new) |
|---|---|---|
| Document | 8.2 KB | 14.0 KB |
| Assets | 9 (incl. a 1.3MB SVG + 459KB background JPG) | 1 (8.5KB CSS) |
| **Total page weight** | **~1.97 MB** | **~22.6 KB** |
| TTFB (doc only, 3-run range) | ~325–820ms | ~200–300ms |

## Interactive map

Legacy: `maps.valleyartmap.ca`, an old Vue SPA (a pre-Django-REST
generation of "Strollopia" — confirmed via its `/admin/` login page,
"Sign in to Strollopia", which is a Wagtail CMS, not today's strollopia-api).

New: `prod.strollopia.com/embed/maps/10`, Leaflet-based.

| | maps.valleyartmap.ca (legacy) | embed/maps/10 (new) |
|---|---|---|
| Document | 1.0 KB | 5.9 KB |
| Assets | 6 (1.7MB vendor JS bundle + 270KB vendor CSS dominate) | 10 (Leaflet + clustering + our render engine, all small) |
| **Total page weight** | **~2.03 MB** | **~297.5 KB** |

## Map data payload

Legacy endpoint: `GET https://maps.valleyartmap.ca/strolls/?limit=1000`
(Wagtail API, found via the browser's Network tab — not discoverable by
static inspection, no public docs). Returns all 17 installations in one
call: `{"meta": {"total_count": 17}, "items": [...]}`.

New endpoint: `GET https://prod.strollopia.com/api/content/maps/10/?org_domain_name=valleyartmap.strollopia.com`
(pre-rendered S3 snapshot, served by `MapDetailSerializer`).

| | Legacy `/strolls/` | New `/api/content/maps/10/` |
|---|---|---|
| Size | 64.9 KB | 125.4 KB |
| Fetch time (3-run avg) | ~700ms | ~1.5s (1 run) |

Our data payload is actually ~2x *heavier* than theirs for the same 17
installations — likely `MapDetailSerializer` returning full nested media
metadata (waveform data, processed S3 keys, etc.) per POI rather than just
display fields. Not fixed proactively (legitimately-used data, not huge
in absolute terms), but worth trimming later if map-load time on weak
connections ever becomes a complaint.

## Full journey totals (splash → map app → data)

| | Legacy | New |
|---|---|---|
| Splash | 1.97 MB | 22.6 KB |
| Map app shell | 2.03 MB | 297.5 KB |
| Map data | 64.9 KB | 125.4 KB |
| **Total** | **~4.06 MB** | **~445.5 KB** |

**The new site is ~9x lighter overall.** The gap is almost entirely old
framework/vendor bloat and oversized uncompressed legacy images (the
"iPhoneTurn.svg" asset alone is 1.3MB — likely a mislabeled raster export,
not a real SVG), not actual content weight.

## Method notes / caveats

- Sequential `requests.get()` timing from this dev machine, not a real
  browser (no connection reuse/parallelism modeling, no render time). A
  rough proxy for transfer weight and server response time, not a
  Lighthouse-grade benchmark.
- Legacy backend (`maps.valleyartmap.ca`) couldn't be found via static
  JS/HTML inspection — no `axios`/`fetch(` strings, no embedded API
  domain in either bundle. Found only via a real browser's Network tab
  (the `/strolls/` endpoint).
