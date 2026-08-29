# Go-Live Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `tools/go_live.py`, an orchestrator in `strollopia-org-setup` that takes a city name to a locally-generated, ready-to-run Cloudflare deploy script for a live trial site — chaining the existing (but currently stranded/inconsistent) discovery, org-creation, and import tools together.

**Architecture:** `go_live.py` is a thin sequencer over four pieces: `city_discover.py` (ported from an abandoned local clone), `post_org_setup.py` and `strollopia_import.py` (both get a small fix so their directory-naming convention matches what `city_discover.py` already produces), and two new scripts, `generate_deploy_script.py` and `check_live.py`. Every stage stays independently runnable — `go_live.py` calls existing functions directly (not subprocesses), stopping on the first failure with whatever that stage already prints.

**Tech Stack:** Python 3, `requests`, `pyyaml`, `pytest` (new dev dependency — this repo has no test suite yet).

**Spec:** `docs/superpowers/specs/2026-08-29-go-live-pipeline-design.md`

## Global Constraints

- Simple-map path only (`--path map`); `--path pwa` and `--source template` are stubbed (clear stop-and-explain, not built).
- No Cloudflare API automation for custom-domain attachment or DNS — those stay a printed manual checklist (spec: no `zone:write`-scoped token held today).
- Don't touch `strollopia-clean` beyond reading from it once (Task 1) — it gets archived, not merged via git.
- Preserve `org_yaml_wizard.py`'s existing Step 9 (Theme) and `_deep_merge` helper untouched — they belong to the unrelated PWA path.
- All new/modified functions get real unit tests; no test doubles for the actual Google Places/Cloudflare/Django APIs beyond mocking `requests` calls, matching the existing pattern in `strollopia-clean/tests/test_city_discover.py`.

---

## Task 1: Port `city_discover.py` into `strollopia-org-setup`

**Files:**
- Create: `strollopia-org-setup/tools/city_discover.py` (copied from `strollopia-clean/tools/city_discover.py`, then modified)
- Create: `strollopia-org-setup/tests/__init__.py`
- Create: `strollopia-org-setup/tests/test_city_discover.py` (copied from `strollopia-clean/tests/test_city_discover.py`, then extended)
- Modify: `strollopia-org-setup/requirements.txt`

**Interfaces:**
- Produces: `city_discover.run(city, api_key, domain, languages, preset_names, init, no_photos, force, output_dir) -> dict` with keys `org_slug` (str), `org_dir` (str), `domain` (str), `display_name` (str). This return value is new — the ported version of `run()` printed everything but returned `None`. Task 5's `go_live.py` depends on this exact shape.
- Produces: `city_discover.PRESETS` (dict, unchanged) — Task 5 uses `PRESETS[name]["dir_name"]`.

- [ ] **Step 1: Add `pytest` to requirements and install it**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
echo "pytest>=8.0" >> requirements.txt
source env/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 2: Copy `city_discover.py` over unmodified**

```bash
cp /home/john/strollopia_git_hub/strollopia-clean/tools/city_discover.py \
   /home/john/strollopia_git_hub/strollopia-org-setup/tools/city_discover.py
```

- [ ] **Step 3: Modify `run()` to return the info `go_live.py` needs**

In `strollopia-org-setup/tools/city_discover.py`, find the end of the `run()` function:

```python
    print(f"\nNext steps:")
    if init:
        print(f"  1. Fill in main_admin_email in {org_dir}/org-setup.yaml")
        print(f"  2. python tools/post_org_setup.py {org_slug}")
    else:
        print(f"  python tools/post_org_setup.py {org_slug}")
    print(f"  python tools/strollopia_import.py {os.path.join(output_dir, org_slug)}/ --all-maps")
```

Replace it with (adds the return statement, keeps everything else identical):

```python
    print(f"\nNext steps:")
    if init:
        print(f"  1. Fill in main_admin_email in {org_dir}/org-setup.yaml")
        print(f"  2. python tools/post_org_setup.py {org_slug}")
    else:
        print(f"  python tools/post_org_setup.py {org_slug}")
    print(f"  python tools/strollopia_import.py {os.path.join(output_dir, org_slug)}/ --all-maps")

    return {
        "org_slug": org_slug,
        "org_dir": org_dir,
        "domain": domain,
        "display_name": geocode["city"],
    }
```

- [ ] **Step 4: Copy the test file and add `tests/__init__.py`**

```bash
mkdir -p /home/john/strollopia_git_hub/strollopia-org-setup/tests
touch /home/john/strollopia_git_hub/strollopia-org-setup/tests/__init__.py
cp /home/john/strollopia_git_hub/strollopia-clean/tests/test_city_discover.py \
   /home/john/strollopia_git_hub/strollopia-org-setup/tests/test_city_discover.py
```

- [ ] **Step 5: Add a new test for the return value**

Append to `strollopia-org-setup/tests/test_city_discover.py`:

```python
from unittest.mock import patch, MagicMock
from city_discover import run


def test_run_returns_org_slug_domain_and_display_name(tmp_path):
    geocode_result = {
        "lat": 47.2692, "lng": 11.4041,
        "country_code": "AT", "state": "Tirol", "city": "Innsbruck",
        "bbox": (47.24, 11.36, 47.30, 11.45),
    }
    with patch("city_discover.geocode_city", return_value=geocode_result), \
         patch("city_discover.discover_google", return_value=[]), \
         patch("city_discover.discover_osm", return_value=[]):
        result = run(
            city="Innsbruck, Austria", api_key=None, domain=None,
            languages=["en"], preset_names=["parks"],
            init=True, no_photos=True, force=False,
            output_dir=str(tmp_path),
        )

    assert result["org_slug"] == "at-tirol-innsbruck"
    assert result["domain"] == "at-tirol-innsbruck.strollopia.com"
    assert result["display_name"] == "Innsbruck"
    assert result["org_dir"] == str(tmp_path / "at-tirol-innsbruck")
```

- [ ] **Step 6: Run the tests**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_city_discover.py -v
```

Expected: all tests pass, including the new `test_run_returns_org_slug_domain_and_display_name`.

- [ ] **Step 7: Commit**

```bash
git add tools/city_discover.py tests/__init__.py tests/test_city_discover.py requirements.txt
git commit -m "feat: port city_discover.py from the abandoned strollopia-clean clone

Brings over Google Places + OSM Overpass city/POI discovery, unmodified
except run() now returns {org_slug, org_dir, domain, display_name} so
the upcoming go_live.py orchestrator can chain into org creation and
import without re-deriving these from the city name itself."
```

---

## Task 2: Per-language schema/data support in `strollopia_import.py`

`city_discover.py` writes one schema + one data file **per language**
(`import-schema.de.yaml` + `map-data.de.tsv`, `import-schema.en.yaml` +
`map-data.en.tsv`, ...), never a bare `import-schema.yaml`. Today's
`strollopia_import.py` only looks for the bare filename, so none of
`city_discover.py`'s output is importable yet. This task fixes that,
correcting a gap in the version that existed in `strollopia-clean` (which
resolved the schema file per-language but left the data-file lookup
hardcoded to the legacy name — this task's version pairs both consistently).

**Files:**
- Modify: `strollopia-org-setup/tools/strollopia_import.py:76-141` (see current content below)
- Create: `strollopia-org-setup/tests/test_strollopia_import_schema_resolution.py`

**Interfaces:**
- Produces: `find_schemas_in_map_dir(map_dir) -> list[str]` — sorted list of schema files for a map dir; language-specific schemas win over the legacy one if both somehow exist.
- Produces: `find_data_path_for_schema(map_dir, schema_path) -> (str, str)` — returns `(data_path, delimiter)` paired to the schema's language suffix (or the legacy name if the schema has none). Raises `FileNotFoundError` if no matching data file exists.
- Modifies: `resolve_map_dir_paths(map_dir, schema_path=None) -> dict` — new optional `schema_path` param; when omitted, resolves the same way as before (legacy schema preferred, else first language-specific schema).
- Modifies: `find_map_dirs(org_dir) -> list[str]` — now recognizes language-specific schemas too.
- Consumed by: Task 4 (`post_org_setup.py`'s `check_org_maps_have_data`) and Task 5 (`go_live.py`, indirectly via `strollopia_import.main`).

- [ ] **Step 1: Write the failing tests**

Create `strollopia-org-setup/tests/test_strollopia_import_schema_resolution.py`:

```python
"""Tests for per-language schema/data resolution in strollopia_import.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import pytest
from strollopia_import import (
    find_schemas_in_map_dir, find_data_path_for_schema, resolve_map_dir_paths,
    find_map_dirs,
)


def _write(path, content="x"):
    with open(path, "w") as f:
        f.write(content)


def test_find_schemas_legacy_only(tmp_path):
    _write(tmp_path / "import-schema.yaml")
    assert find_schemas_in_map_dir(str(tmp_path)) == [str(tmp_path / "import-schema.yaml")]


def test_find_schemas_language_specific_sorted(tmp_path):
    _write(tmp_path / "import-schema.en.yaml")
    _write(tmp_path / "import-schema.de.yaml")
    result = find_schemas_in_map_dir(str(tmp_path))
    assert result == [str(tmp_path / "import-schema.de.yaml"), str(tmp_path / "import-schema.en.yaml")]


def test_find_schemas_prefers_language_specific_over_legacy(tmp_path):
    _write(tmp_path / "import-schema.yaml")
    _write(tmp_path / "import-schema.en.yaml")
    result = find_schemas_in_map_dir(str(tmp_path))
    assert result == [str(tmp_path / "import-schema.en.yaml")]


def test_find_schemas_none_found(tmp_path):
    assert find_schemas_in_map_dir(str(tmp_path)) == []


def test_find_data_path_legacy(tmp_path):
    schema = tmp_path / "import-schema.yaml"
    _write(schema)
    _write(tmp_path / "map-data.tsv")
    data_path, delimiter = find_data_path_for_schema(str(tmp_path), str(schema))
    assert data_path == str(tmp_path / "map-data.tsv")
    assert delimiter == "\t"


def test_find_data_path_language_specific(tmp_path):
    schema = tmp_path / "import-schema.de.yaml"
    _write(schema)
    _write(tmp_path / "map-data.de.tsv")
    _write(tmp_path / "map-data.tsv")  # decoy legacy file, must not be picked
    data_path, delimiter = find_data_path_for_schema(str(tmp_path), str(schema))
    assert data_path == str(tmp_path / "map-data.de.tsv")


def test_find_data_path_csv_fallback(tmp_path):
    schema = tmp_path / "import-schema.fr.yaml"
    _write(schema)
    _write(tmp_path / "map-data.fr.csv")
    data_path, delimiter = find_data_path_for_schema(str(tmp_path), str(schema))
    assert data_path == str(tmp_path / "map-data.fr.csv")
    assert delimiter == ","


def test_find_data_path_missing_raises(tmp_path):
    schema = tmp_path / "import-schema.de.yaml"
    _write(schema)
    with pytest.raises(FileNotFoundError):
        find_data_path_for_schema(str(tmp_path), str(schema))


def test_resolve_map_dir_paths_multi_language(tmp_path):
    org_dir = tmp_path / "myorg"
    map_dir = org_dir / "main-map"
    map_dir.mkdir(parents=True)
    _write(org_dir / "org-setup.yaml")
    _write(map_dir / "import-schema.de.yaml")
    _write(map_dir / "map-data.de.tsv")
    _write(map_dir / "import-schema.en.yaml")
    _write(map_dir / "map-data.en.tsv")

    # No override: resolves to the first language-specific schema (sorted)
    paths = resolve_map_dir_paths(str(map_dir))
    assert paths["schema"] == str(map_dir / "import-schema.de.yaml")
    assert paths["data"] == str(map_dir / "map-data.de.tsv")

    # Explicit override: pairs with the matching language's data file
    paths_en = resolve_map_dir_paths(str(map_dir), schema_path=str(map_dir / "import-schema.en.yaml"))
    assert paths_en["schema"] == str(map_dir / "import-schema.en.yaml")
    assert paths_en["data"] == str(map_dir / "map-data.en.tsv")


def test_find_map_dirs_recognizes_language_specific_schemas(tmp_path):
    org_dir = tmp_path / "myorg"
    map_dir = org_dir / "business-map"
    map_dir.mkdir(parents=True)
    _write(map_dir / "import-schema.en.yaml")
    other_dir = org_dir / "not-a-map"
    other_dir.mkdir()
    assert find_map_dirs(str(org_dir)) == [str(map_dir)]
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_strollopia_import_schema_resolution.py -v
```

Expected: FAIL with `ImportError: cannot import name 'find_schemas_in_map_dir'`.

- [ ] **Step 3: Implement the resolution functions**

In `strollopia-org-setup/tools/strollopia_import.py`, replace lines 76-141 (the current `resolve_map_dir_paths` and `find_map_dirs`):

```python
def find_schemas_in_map_dir(map_dir):
    """Return the ordered list of schema files to run for a map directory.

    If language-specific schemas exist (import-schema.de.yaml, import-schema.en.yaml,
    etc.) those are returned sorted alphabetically. Otherwise falls back to the
    legacy import-schema.yaml. Never returns both.
    """
    lang_schemas = sorted(glob.glob(os.path.join(map_dir, 'import-schema.*.yaml')))
    if lang_schemas:
        return lang_schemas
    legacy = os.path.join(map_dir, 'import-schema.yaml')
    if os.path.isfile(legacy):
        return [legacy]
    return []


def find_data_path_for_schema(map_dir, schema_path):
    """Return (data_path, delimiter) for a given schema file.

    A language-specific schema (import-schema.<lang>.yaml) pairs with a
    same-language data file (map-data.<lang>.tsv/.csv). The legacy
    import-schema.yaml pairs with the legacy map-data.tsv/.csv. Prefers
    .tsv, falls back to .csv.
    """
    schema_name = os.path.basename(schema_path)
    match = re.match(r'^import-schema\.(.+)\.yaml$', schema_name)
    lang_suffix = f'.{match.group(1)}' if match else ''
    tsv = os.path.join(map_dir, f'map-data{lang_suffix}.tsv')
    csv_path = os.path.join(map_dir, f'map-data{lang_suffix}.csv')
    if os.path.isfile(tsv):
        return tsv, '\t'
    if os.path.isfile(csv_path):
        return csv_path, ','
    raise FileNotFoundError(
        f'No map-data{lang_suffix}.tsv or map-data{lang_suffix}.csv found in: {map_dir}')


def resolve_map_dir_paths(map_dir, schema_path=None):
    """Resolve schema, data, media, and org-setup paths from a map directory.

    If schema_path is given, it's used directly (the multi-schema --all-maps
    case, where the caller already knows which schema this run is for).
    Otherwise resolves to the legacy import-schema.yaml if present, else the
    first language-specific schema found (sorted alphabetically).

    Returns dict with keys: map_dir, map_name, schema, data, delimiter,
    media_dir, org_credentials.
    """
    map_dir = os.path.abspath(map_dir)
    if not os.path.isdir(map_dir):
        raise FileNotFoundError(f'Map directory not found: {map_dir}')

    map_name = os.path.basename(map_dir)
    org_dir = os.path.dirname(map_dir)

    if schema_path is None:
        legacy = os.path.join(map_dir, 'import-schema.yaml')
        if os.path.isfile(legacy):
            schema_path = legacy
        else:
            candidates = find_schemas_in_map_dir(map_dir)
            if not candidates:
                raise FileNotFoundError(f'No schema found in: {map_dir}')
            schema_path = candidates[0]

    data_path, delimiter = find_data_path_for_schema(map_dir, schema_path)

    # Media directory (may not exist if no media)
    media_dir = os.path.join(map_dir, 'media')

    # Org credentials
    org_creds_path = os.path.join(org_dir, 'org-setup.yaml')
    if not os.path.isfile(org_creds_path):
        raise FileNotFoundError(f'Org setup not found: {org_creds_path}')

    return {
        'map_dir': map_dir,
        'map_name': map_name,
        'schema': schema_path,
        'data': data_path,
        'delimiter': delimiter,
        'media_dir': media_dir,
        'org_credentials': org_creds_path,
    }


def find_map_dirs(org_dir):
    """Find all map directories under an org directory.

    A map directory is any subdirectory that contains an import-schema.yaml
    or one or more import-schema.<lang>.yaml files.
    """
    org_dir = os.path.abspath(org_dir)
    map_dirs = []
    for entry in sorted(os.listdir(org_dir)):
        entry_path = os.path.join(org_dir, entry)
        if os.path.isdir(entry_path) and find_schemas_in_map_dir(entry_path):
            map_dirs.append(entry_path)
    return map_dirs
```

- [ ] **Step 4: Update `import_single_map` and `main`'s `--all-maps` loop to run once per schema**

Replace the `import_single_map` function (currently at line 888):

```python
def import_single_map(map_dir, args, schema_override=None):
    """Run import for a single map directory. Returns 0 on success, 1 on error."""
    paths = resolve_map_dir_paths(map_dir, schema_path=schema_override)
    map_name = paths['map_name']

    # Apply overrides
    schema_path = args.schema or paths['schema']
    data_path = args.data or paths['data']
    org_creds_path = args.org_credentials or paths['org_credentials']
    media_dir = paths['media_dir']
```

(Only the function signature and the `resolve_map_dir_paths` call change — everything below that line in the function body is unchanged.)

Replace the `--all-maps` branch in `main()`:

```python
    if args.all_maps:
        # Treat map_dir as an org directory, import all maps
        org_dir = os.path.abspath(args.map_dir)
        map_dirs = find_map_dirs(org_dir)
        if not map_dirs:
            logger.error(f'No map directories found in: {org_dir}')
            logger.error('(A map directory must contain import-schema.yaml or import-schema.<lang>.yaml)')
            return 1

        # Build (map_dir, schema_path) pairs — one entry per schema file per map
        runs = []
        for map_dir in map_dirs:
            for schema_path in find_schemas_in_map_dir(map_dir):
                runs.append((map_dir, schema_path))

        logger.info(f'Found {len(map_dirs)} map(s), {len(runs)} import run(s) in {org_dir}:')
        for map_dir, schema_path in runs:
            logger.info(f'  {os.path.basename(map_dir)}/ [{os.path.basename(schema_path)}]')
        logger.info('')

        overall_ok = True
        for map_dir, schema_path in runs:
            logger.info(f'{"=" * 60}')
            logger.info(f'Importing: {os.path.basename(map_dir)} [{os.path.basename(schema_path)}]')
            logger.info(f'{"=" * 60}')
            result = import_single_map(map_dir, args, schema_override=schema_path)
            if result != 0:
                overall_ok = False

        return 0 if overall_ok else 1
    else:
        return import_single_map(args.map_dir, args)
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_strollopia_import_schema_resolution.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run the full existing test suite to check for regressions**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass (there is no pre-existing suite for `strollopia_import.py` itself to regress, but this confirms nothing else broke).

- [ ] **Step 7: Commit**

```bash
git add tools/strollopia_import.py tests/test_strollopia_import_schema_resolution.py
git commit -m "feat: support per-language import-schema/map-data pairs

city_discover.py writes one schema+data pair per language
(import-schema.<lang>.yaml + map-data.<lang>.tsv) and never a bare
import-schema.yaml, so none of its output was importable before this.
find_schemas_in_map_dir/find_data_path_for_schema resolve both
consistently, fixing a gap in the version of this idea that existed in
the abandoned strollopia-clean clone (which resolved the schema per
language but left the data file hardcoded to the legacy name)."
```

---

## Task 3: `org_slug`/`org_domain_name` decoupling in `org_yaml_wizard.py`

`city_discover.py` (Task 1) names org directories after the **slug**
(`at-tirol-innsbruck`), never the full domain. The wizard still assumes the
directory name **is** the domain throughout, which will now silently break
whenever someone runs `--edit`/`--review` against a city_discover-produced
org. A previous attempt at this fix (in `strollopia-clean`) conflicts with
the Step 9 (Theme) feature added independently in this repo since — this
task re-applies the fix on top of current code, keeping Step 9 untouched.

**Files:**
- Modify: `strollopia-org-setup/tools/org_yaml_wizard.py:573-890`
- Create: `strollopia-org-setup/tests/test_org_yaml_wizard_slug.py`

**Interfaces:**
- Modifies: `_draft_path(output_dir, org_slug)`, `_save_draft(config, output_dir, org_slug)`, `_load_draft(output_dir, org_slug)`, `_delete_draft(output_dir, org_slug)` — parameter renamed from `org_domain_name`, behavior otherwise unchanged.
- Modifies: `run_wizard(defaults, existing=None, org_slug=None, org_domain_name=None, output_dir="org-data/") -> dict` — new `org_slug` parameter; returned config gains an internal `_org_slug` key (stripped before writing YAML, same as the existing `_theme`/`_wizard_step` keys).
- Modifies: `write_org_setup(config, output_dir) -> str` — directory name now comes from `config["_org_slug"]` (falling back to the domain's first label if absent), not `config["org_domain_name"]` directly.

- [ ] **Step 1: Write the failing tests**

Create `strollopia-org-setup/tests/test_org_yaml_wizard_slug.py`:

```python
"""Tests for org_slug/org_domain_name decoupling in org_yaml_wizard.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from org_yaml_wizard import (
    _draft_path, _save_draft, _load_draft, _delete_draft, write_org_setup,
)


def test_draft_path_uses_slug_not_domain(tmp_path):
    path = _draft_path(str(tmp_path), "kentville")
    assert path == os.path.join(str(tmp_path), "kentville", ".org-setup-draft.yaml")


def test_save_and_load_draft_roundtrip(tmp_path):
    _save_draft({"org_domain_name": "kentville.strollopia.com", "_wizard_step": 3},
                str(tmp_path), "kentville")
    config, step = _load_draft(str(tmp_path), "kentville")
    assert config["org_domain_name"] == "kentville.strollopia.com"
    assert step == 3


def test_delete_draft(tmp_path):
    _save_draft({"_wizard_step": 1}, str(tmp_path), "kentville")
    _delete_draft(str(tmp_path), "kentville")
    config, step = _load_draft(str(tmp_path), "kentville")
    assert config is None


def test_write_org_setup_uses_slug_for_directory(tmp_path):
    config = {
        "org_domain_name": "at-tirol-innsbruck.strollopia.com",
        "_org_slug": "at-tirol-innsbruck",
        "org_maps": {"main-map": {"is_public": True}},
    }
    path = write_org_setup(config, str(tmp_path))
    assert path == str(tmp_path / "at-tirol-innsbruck" / "org-setup.yaml")
    assert os.path.isdir(tmp_path / "at-tirol-innsbruck" / "main-map" / "media")


def test_write_org_setup_falls_back_to_domain_first_label(tmp_path):
    # No explicit _org_slug (e.g. a YAML written before this change) — falls
    # back to the domain's first label, same as before this task.
    config = {"org_domain_name": "kentville.strollopia.com", "org_maps": {}}
    path = write_org_setup(config, str(tmp_path))
    assert path == str(tmp_path / "kentville" / "org-setup.yaml")


def test_write_org_setup_strips_internal_slug_key(tmp_path):
    config = {
        "org_domain_name": "kentville.strollopia.com",
        "_org_slug": "kentville",
        "org_maps": {},
    }
    path = write_org_setup(config, str(tmp_path))
    with open(path) as f:
        content = f.read()
    assert "_org_slug" not in content
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_org_yaml_wizard_slug.py -v
```

Expected: FAIL — `test_draft_path_uses_slug_not_domain` and others fail because the current functions build paths from `org_domain_name` positionally (the rename hasn't happened yet, so passing "kentville" as the second positional arg technically already works today since it's untyped — the real failures will show in `test_write_org_setup_uses_slug_for_directory`, which currently ignores `_org_slug` entirely and would produce a path using the full domain). Confirm at least that test fails before proceeding.

- [ ] **Step 3: Rename the draft helpers' parameter**

In `strollopia-org-setup/tools/org_yaml_wizard.py`, replace lines 573-601:

```python
def _draft_path(output_dir, org_slug):
    """Return path to the draft file for an org."""
    return os.path.join(output_dir, org_slug, DRAFT_FILENAME)


def _save_draft(config, output_dir, org_slug):
    """Save current wizard state to draft file."""
    draft = _draft_path(output_dir, org_slug)
    os.makedirs(os.path.dirname(draft), exist_ok=True)
    with open(draft, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _load_draft(output_dir, org_slug):
    """Load draft file if it exists, return (config, last_completed_step) or (None, 0)."""
    draft = _draft_path(output_dir, org_slug)
    if not os.path.exists(draft):
        return None, 0
    with open(draft) as f:
        config = yaml.safe_load(f) or {}
    step = config.pop("_wizard_step", 0)
    return config, step


def _delete_draft(output_dir, org_slug):
    """Remove draft file if it exists."""
    draft = _draft_path(output_dir, org_slug)
    if os.path.exists(draft):
        os.remove(draft)
```

- [ ] **Step 4: Thread `org_slug` through `run_wizard`**

Replace lines 617-695 (`run_wizard`, keeping the Step 9/theme-nesting tail exactly as-is):

```python
def run_wizard(defaults, existing=None, org_slug=None, org_domain_name=None, output_dir="org-data/"):
    """Run wizard steps and return the complete org config dict.

    Parameters
    ----------
    defaults : dict
        Wizard default values loaded from wizard_defaults.yaml.
    existing : dict | None
        Previously saved config (for --edit or --resume mode).  Every value
        in this dict is offered as the default for its prompt so the user
        can press Enter to keep it or retype to correct it.
    org_slug : str | None
        Directory label for this org (e.g. 'kentville'). Used for draft
        saving and the output directory — separate from the runtime domain,
        so an org can move to a new domain later without renaming its
        directory or losing draft/git history.
    org_domain_name : str | None
        Pre-fill for Step 1's domain prompt.
    output_dir : str
        Base directory for org data (used for draft saving).
    """
    if existing is None:
        existing = {}

    print("=" * 50)
    print("  Strollopia Org Setup Wizard")
    print("=" * 50)

    if existing:
        print("\nPrevious answers are shown in [brackets] — press Enter to keep them.")

    config = {}

    # The slug is fixed for the whole wizard session — it's the directory
    # label, not the domain, and doesn't change when the user edits the
    # domain in step 1.
    draft_slug = org_slug or existing.get("_org_slug")

    step_funcs = {
        1: lambda: step_org_identity(defaults, existing, org_domain_name=org_domain_name),
        2: lambda: step_admin(defaults, existing),
        3: lambda: step_map_defaults(existing),
        4: lambda: step_access(defaults, existing),
        5: lambda: step_categories(existing),
        6: lambda: step_media_layouts(defaults, existing),
        7: lambda: step_maps(defaults, existing),
        8: lambda: step_ui_support(defaults, existing),
        9: lambda: step_theme(defaults, existing),
    }

    try:
        for step_num in range(1, 10):
            result = step_funcs[step_num]()
            _deep_merge(config, result)

            # After step 1, we know the slug for draft saving (if not already set)
            if step_num == 1 and draft_slug is None:
                domain = config.get("org_domain_name", "")
                draft_slug = domain.split(".")[0] if domain else None

            # Save draft after each completed step
            if draft_slug:
                draft_config = dict(config)
                draft_config["_org_slug"] = draft_slug
                draft_config["_wizard_step"] = step_num
                _save_draft(draft_config, output_dir, draft_slug)

    except (KeyboardInterrupt, EOFError):
        print("\n\nInterrupted.")
        if draft_slug:
            draft = _draft_path(output_dir, draft_slug)
            if os.path.exists(draft):
                print(f"Draft saved to: {draft}")
            else:
                print("No steps were completed. Nothing saved.")
            print(
                f"Resume with: python tools/org_yaml_wizard.py {draft_slug} --review"
            )
        sys.exit(1)

    # Nest theme data into ui_support.ui_config.theme
    theme_data = config.pop("_theme", None)
    if theme_data:
        ui = config.setdefault("ui_support", {})
        ui_config = ui.setdefault("ui_config", {})
        ui_config["theme"] = theme_data

    if draft_slug:
        config["_org_slug"] = draft_slug

    return config
```

- [ ] **Step 5: Use `_org_slug` for the output directory in `write_org_setup`**

Replace lines 698-701:

```python
def write_org_setup(config, output_dir):
    """Write org-setup.yaml and create directory structure."""
    # Directory label: use the explicit slug if set, otherwise fall back to
    # the domain's first label. This decouples the directory name from the
    # runtime org_domain_name so orgs can be relaunched under a different
    # domain without renaming directories or losing git history.
    org_slug = config.get("_org_slug") or config["org_domain_name"].split(".")[0]
    org_dir = os.path.join(output_dir, org_slug)
```

(The rest of `write_org_setup` — directory/media creation, key ordering, YAML dump — is unchanged. `_org_slug` is already stripped from the output by the existing `clean = {k: v for k, v in config.items() if not k.startswith("_")}` line, since it starts with an underscore like `_theme` and `_wizard_step` already did.)

- [ ] **Step 6: Update `main()` to take `org_slug` instead of `org_domain_name`**

Replace lines 757-887 (`main`) in full:

```python
def main():
    parser = argparse.ArgumentParser(
        description="CLI wizard to build org-setup.yaml for Strollopia organizations."
    )
    parser.add_argument(
        "org_slug",
        nargs="?",
        help="Directory label for this org (e.g. 'kentville'). The runtime "
             "domain is set in step 1. Required unless --edit is used.",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Re-run the wizard with previous answers as defaults so you can review and correct them. Requires org_slug.",
    )
    parser.add_argument(
        "--output-dir",
        default="org-data/",
        help="Base directory for org data (default: org-data/)",
    )
    parser.add_argument(
        "--edit",
        metavar="PATH",
        help="Load existing org-setup.yaml and re-run wizard with current values as defaults",
    )
    parser.add_argument(
        "--defaults",
        metavar="PATH",
        default=os.path.join(os.path.dirname(__file__), "wizard_defaults.yaml"),
        help="Override defaults file (default: tools/wizard_defaults.yaml)",
    )
    args = parser.parse_args()

    # Validate argument combinations
    if not args.edit and not args.org_slug:
        parser.error("org_slug is required unless --edit is provided")

    if args.review and not args.org_slug:
        parser.error("org_slug is required with --review")

    if args.review and args.edit:
        parser.error("--review and --edit cannot be used together")

    # Load defaults
    defaults_path = args.defaults
    if os.path.exists(defaults_path):
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
    else:
        print(f"Warning: defaults file not found at {defaults_path}, using built-in defaults.")
        defaults = {}

    # Determine org_slug, domain default, and existing config
    existing = {}
    org_slug = args.org_slug
    # Domain default for step 1: if the slug looks like a full domain use it
    # as-is, else suggest <slug>.strollopia.com so the user can accept or override.
    domain_default = org_slug if (org_slug and "." in org_slug) else (
        f"{org_slug}.strollopia.com" if org_slug else None
    )

    if args.edit:
        # --edit mode: derive slug from existing YAML or the directory containing it
        if not os.path.exists(args.edit):
            print(f"Error: file not found: {args.edit}")
            sys.exit(1)
        with open(args.edit) as f:
            existing = yaml.safe_load(f) or {}
        org_slug = existing.get("_org_slug") or os.path.basename(
            os.path.dirname(os.path.abspath(args.edit))
        )
        domain_default = existing.get("org_domain_name")
        print(f"Loaded existing config from {args.edit}")

    elif args.review:
        # --review mode: load draft or finished org-setup.yaml, re-run all steps with saved values
        draft_config, last_step = _load_draft(args.output_dir, org_slug)
        if draft_config is not None:
            existing = draft_config
            print(f"Loaded draft for {org_slug} (completed through step {last_step}: {STEP_NAMES.get(last_step, '?')})")
        else:
            # No draft — try the finished org-setup.yaml
            yaml_path = os.path.join(args.output_dir, org_slug, "org-setup.yaml")
            if not os.path.exists(yaml_path):
                print(f"Error: no draft or org-setup.yaml found for slug '{org_slug}'")
                print(f"  Looked for: {_draft_path(args.output_dir, org_slug)}")
                print(f"         and: {yaml_path}")
                sys.exit(1)
            with open(yaml_path) as f:
                existing = yaml.safe_load(f) or {}
            print(f"Loaded existing config from {yaml_path}")
        domain_default = existing.get("org_domain_name", domain_default)
        print("All steps will be re-run with your previous answers as defaults.")

    else:
        # New org: check if directory already exists
        org_dir = os.path.join(args.output_dir, org_slug)
        if os.path.isdir(org_dir):
            print(f"Warning: directory already exists: {org_dir}")
            print("  Existing files will be preserved, org-setup.yaml will be overwritten.")
            if not ask_yes_no("Continue?", default=True):
                print("Aborted.")
                sys.exit(0)

    # Run wizard
    config = run_wizard(
        defaults,
        existing,
        org_slug=org_slug,
        org_domain_name=domain_default,
        output_dir=args.output_dir,
    )

    # Step 10: Review & Write
    print("\n=== Step 10: Review & Write ===\n")
    # Show clean config without internal keys
    display = {k: v for k, v in config.items() if not k.startswith("_")}
    print("Generated org-setup.yaml:\n")
    print("---")
    print(yaml.dump(display, default_flow_style=False, sort_keys=False))

    if ask_yes_no("Write this config to disk?", default=True):
        path = write_org_setup(config, args.output_dir)
        print(f"\nWritten to: {path}")

        # Delete draft file on successful write
        final_slug = config.get("_org_slug") or config["org_domain_name"].split(".")[0]
        _delete_draft(args.output_dir, final_slug)

        # List created directories
        org_dir = os.path.join(args.output_dir, final_slug)
        print(f"Org directory: {org_dir}")
        for map_name in config.get("org_maps", {}):
            print(f"  Map directory: {os.path.join(org_dir, map_name)}/")
            print(f"    Media: {os.path.join(org_dir, map_name, 'media')}/")

        print("\nDone!")

        # Offer to post the config to the server
        _offer_post_to_server(path)
    else:
        print("Aborted. No files written.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_org_yaml_wizard_slug.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add tools/org_yaml_wizard.py tests/test_org_yaml_wizard_slug.py
git commit -m "fix: key org_yaml_wizard drafts/output by org_slug, not domain

city_discover.py already names org directories after a stable slug, not
the full domain, so an org can move to a new domain without renaming its
directory. The wizard assumed directory name == domain throughout,
which silently breaks --edit/--review against a city_discover-produced
org. Re-applies a fix that previously existed only in the abandoned
strollopia-clean clone, where it conflicted with this repo's own Step 9
(Theme) addition — Step 9 and _deep_merge are left untouched here."
```

---

## Task 4: `org_slug`/`org_domain_name` decoupling in `post_org_setup.py`

**Files:**
- Modify: `strollopia-org-setup/tools/post_org_setup.py` (full file, 145 lines)
- Create: `strollopia-org-setup/tests/test_post_org_setup.py`

**Interfaces:**
- Consumes: `find_schemas_in_map_dir`, `find_data_path_for_schema` from Task 2.
- Modifies: `check_org_maps_have_data(yaml_path)` — now recognizes per-language schema/data pairs as "ready", not just the legacy filenames.
- `post_org_setup(yaml_path) -> bool` — **signature unchanged**. Task 5's `go_live.py` calls this function directly, so it isn't affected by the CLI arg rename below.
- Modifies: `main()`'s CLI — positional arg renamed `org_domain_name` → `org_slug`, matching Task 3 and `city_discover.py`'s directory convention.

- [ ] **Step 1: Write the failing tests**

Create `strollopia-org-setup/tests/test_post_org_setup.py`:

```python
"""Tests for post_org_setup.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import yaml
from post_org_setup import check_org_maps_have_data


def _write_org_setup(org_dir, org_maps):
    os.makedirs(org_dir, exist_ok=True)
    yaml_path = os.path.join(org_dir, "org-setup.yaml")
    with open(yaml_path, "w") as f:
        yaml.dump({"org_domain_name": "test.strollopia.com", "org_maps": org_maps}, f)
    return yaml_path


def test_check_org_maps_have_data_passes_for_legacy_schema(tmp_path, capsys):
    yaml_path = _write_org_setup(tmp_path, {"main-map": {"is_public": True}})
    map_dir = tmp_path / "main-map"
    map_dir.mkdir()
    (map_dir / "import-schema.yaml").write_text("x")
    (map_dir / "map-data.tsv").write_text("x")

    check_org_maps_have_data(str(yaml_path))

    assert "WARNING" not in capsys.readouterr().out


def test_check_org_maps_have_data_passes_for_language_specific_schema(tmp_path, capsys):
    # This is the case that broke before this task: a city_discover.py
    # output with only import-schema.en.yaml + map-data.en.tsv, no bare
    # import-schema.yaml, used to be incorrectly flagged as incomplete.
    yaml_path = _write_org_setup(tmp_path, {"business-map": {"is_public": True}})
    map_dir = tmp_path / "business-map"
    map_dir.mkdir()
    (map_dir / "import-schema.en.yaml").write_text("x")
    (map_dir / "map-data.en.tsv").write_text("x")

    check_org_maps_have_data(str(yaml_path))

    assert "WARNING" not in capsys.readouterr().out


def test_check_org_maps_have_data_warns_when_schema_has_no_data(tmp_path, capsys):
    yaml_path = _write_org_setup(tmp_path, {"empty-map": {"is_public": True}})
    map_dir = tmp_path / "empty-map"
    map_dir.mkdir()
    (map_dir / "import-schema.en.yaml").write_text("x")
    # no map-data.en.tsv

    check_org_maps_have_data(str(yaml_path))

    assert "empty-map" in capsys.readouterr().out


def test_check_org_maps_have_data_warns_when_map_dir_missing(tmp_path, capsys):
    yaml_path = _write_org_setup(tmp_path, {"missing-map": {"is_public": True}})

    check_org_maps_have_data(str(yaml_path))

    assert "missing-map" in capsys.readouterr().out
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_post_org_setup.py -v
```

Expected: `test_check_org_maps_have_data_passes_for_language_specific_schema` FAILS (current code only checks the legacy filenames, so it incorrectly warns).

- [ ] **Step 3: Fix `check_org_maps_have_data` and rename the CLI arg**

Replace the full contents of `strollopia-org-setup/tools/post_org_setup.py`:

```python
#!/usr/bin/env python3
"""Post an org-setup.yaml to the Strollopia server to create/initialize an organization.

Can be run standalone or called from the wizard.

Standalone usage:
    python tools/post_org_setup.py kentville
    python tools/post_org_setup.py kentville --output-dir org-data/

The org_slug is the directory label (e.g. 'kentville'), not the domain name.
The runtime org_domain_name is read from the org-setup.yaml inside that directory.
"""

import argparse
import getpass
import os
import sys

import yaml

from api_client import admin_login, initialize_org_from_yaml, login, print_api_base_url
from strollopia_import import find_schemas_in_map_dir, find_data_path_for_schema


def check_org_maps_have_data(yaml_path):
    """Warn about any org_maps entry with no ready import-schema/map-data yet.

    initialize_org_from_yaml will happily create a map with no content --
    the gap only surfaces later, as a confusing failure in the import step.
    Catching it here, before posting, is cheap.
    """
    with open(yaml_path) as f:
        org_creds = yaml.safe_load(f)
    org_maps = org_creds.get('org_maps') or {}
    if not org_maps:
        return
    map_root = os.path.dirname(yaml_path)
    incomplete = []
    for map_name in org_maps:
        map_dir = os.path.join(map_root, map_name)
        ready = False
        for schema_path in find_schemas_in_map_dir(map_dir):
            try:
                find_data_path_for_schema(map_dir, schema_path)
                ready = True
                break
            except FileNotFoundError:
                continue
        if not ready:
            incomplete.append(map_name)
    if incomplete:
        print("WARNING: these org_maps entries have no ready import-schema/map-data yet:")
        for name in incomplete:
            print(f"  - {name}")
        print("They'll be created empty on the server with nothing to import.")
        print("Consider removing them from org_maps until their data is ready.\n")


def verify_org_admin_login(yaml_path):
    """Confirm the org admin defined in the YAML can actually log in.

    initialize_org_from_yaml does NOT reset the password of an
    already-existing user -- if this email/org combination was set up
    before (even with an old placeholder password), the account keeps
    its original password even after a successful post. Catching that
    here, right after posting, avoids discovering it much later during
    the data import.
    """
    with open(yaml_path) as f:
        org_creds = yaml.safe_load(f)
    email = org_creds.get('main_admin_email')
    password = org_creds.get('main_admin_password')
    org_domain_name = org_creds.get('org_domain_name')
    if not (email and password and org_domain_name):
        return

    print(f"\nVerifying org admin can log in with the password in {yaml_path} ...")
    try:
        login(email, password, org_domain_name)
        print("  OK: org admin login verified.")
    except RuntimeError:
        print("  WARNING: org admin login FAILED with the password in this YAML.")
        print("  This usually means the account already existed (from an earlier")
        print("  setup attempt) and kept its old password -- initialize_org_from_yaml")
        print("  does not change the password of an existing user.")
        print("  Before importing data, find/reset the account's real working")
        print("  password (e.g. an earlier placeholder value), or reset it through")
        print("  the actual admin backend -- then update this YAML to match, or pass")
        print("  --email/--password overrides to strollopia_import.py.")


def post_org_setup(yaml_path):
    """Prompt for super-admin credentials, log in, and post the YAML file.

    Returns True on success, False on failure.
    """
    print_api_base_url()
    check_org_maps_have_data(yaml_path)

    print("A Django super-admin account is required to create an organization.\n")
    email = input("Super-admin email: ").strip()
    if not email:
        print("No email provided. Aborted.")
        return False
    password = getpass.getpass("Super-admin password: ")
    if not password:
        print("No password provided. Aborted.")
        return False

    print(f"\nLogging in as {email} via admin.strollopia.com ...")
    token = admin_login(email, password)
    if not token:
        return False

    print("Login successful.")
    print(f"Posting {yaml_path} ...")
    success, data = initialize_org_from_yaml(yaml_path, token)
    if success:
        print(f"Organization created: {data}")
        verify_org_admin_login(yaml_path)
    else:
        print(f"Post failed: {data}")
    return success


def main():
    parser = argparse.ArgumentParser(
        description="Post an org-setup.yaml to the Strollopia server."
    )
    parser.add_argument(
        "org_slug",
        help="Directory label for this org (e.g. 'kentville'). The runtime domain is read from org-setup.yaml.",
    )
    parser.add_argument(
        "--output-dir",
        default="org-data/",
        help="Base directory for org data (default: org-data/)",
    )
    args = parser.parse_args()

    yaml_path = os.path.join(args.output_dir, args.org_slug, "org-setup.yaml")
    if not os.path.exists(yaml_path):
        print(f"Error: file not found: {yaml_path}")
        sys.exit(1)

    with open(yaml_path) as f:
        org_domain_name = (yaml.safe_load(f) or {}).get('org_domain_name', args.org_slug)

    print(f"\n=== Post Org Setup: {org_domain_name} (slug: {args.org_slug}) ===\n")
    print(f"YAML file: {yaml_path}\n")

    success = post_org_setup(yaml_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_post_org_setup.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tools/post_org_setup.py tests/test_post_org_setup.py
git commit -m "fix: post_org_setup.py takes org_slug, recognizes per-language map data

Matches city_discover.py's directory convention (Task 1) and
strollopia_import.py's per-language schema support (Task 2) -- without
this, check_org_maps_have_data incorrectly warned that every
city_discover-produced map was empty."
```

---

## Task 5: `go_live.py` orchestrator (discovery → org → import)

**Files:**
- Create: `strollopia-org-setup/tools/go_live.py`
- Create: `strollopia-org-setup/tests/test_go_live.py`

**Interfaces:**
- Consumes: `city_discover.run(...)` (Task 1), `post_org_setup.post_org_setup(yaml_path)` (Task 4), `strollopia_import.main(argv)` (Task 2, signature unchanged).
- Produces: `go_live.main(argv=None) -> int` (exit code) — the only entry point Task 6/7's wiring (Task 8) needs.

- [ ] **Step 1: Write the failing tests**

Create `strollopia-org-setup/tests/test_go_live.py`:

```python
"""Tests for go_live.py's orchestration and stub behavior."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from unittest.mock import patch
from go_live import main


def test_source_template_stub_stops_before_discovery():
    with patch("go_live.city_discover.run") as mock_run:
        result = main(["Kentville, NS", "--source", "template"])
    assert result == 1
    mock_run.assert_not_called()


def test_path_pwa_stops_after_import_before_deploy_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=True) as mock_post, \
         patch("go_live.strollopia_import.main", return_value=0) as mock_import, \
         patch("go_live.generate_deploy_script") as mock_deploy, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS", "--path", "pwa"])

    assert result == 0
    mock_post.assert_called_once()
    mock_import.assert_called_once()
    mock_deploy.assert_not_called()


def test_dry_run_stops_before_deploy_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=True), \
         patch("go_live.strollopia_import.main", return_value=0) as mock_import, \
         patch("go_live.generate_deploy_script") as mock_deploy, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS", "--dry-run", "--sites-repo", "/tmp/sites"])

    assert result == 0
    assert "--dry-run" in mock_import.call_args[0][0]
    mock_deploy.assert_not_called()


def test_org_creation_failure_stops_the_pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=False), \
         patch("go_live.strollopia_import.main") as mock_import, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS"])

    assert result == 1
    mock_import.assert_not_called()


def test_import_failure_stops_before_deploy_script(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("go_live.city_discover.run") as mock_discover, \
         patch("go_live.post_org_setup", return_value=True), \
         patch("go_live.strollopia_import.main", return_value=1), \
         patch("go_live.generate_deploy_script") as mock_deploy, \
         patch("builtins.input", return_value=""):
        mock_discover.return_value = {
            "org_slug": "ca-ns-kentville", "org_dir": str(tmp_path / "ca-ns-kentville"),
            "domain": "ca-ns-kentville.strollopia.com", "display_name": "Kentville",
        }
        result = main(["Kentville, NS", "--sites-repo", "/tmp/sites"])

    assert result == 1
    mock_deploy.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_go_live.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'go_live'`.

- [ ] **Step 3: Implement `go_live.py`**

Create `strollopia-org-setup/tools/go_live.py`:

```python
#!/usr/bin/env python3
"""Go-live pipeline: city name -> provisioned org+data -> generated deploy script.

Chains city_discover.py (Google Places + OSM discovery), post_org_setup.py
(org creation), and strollopia_import.py (POI import) together, then hands
off to generate_deploy_script.py for the strollopia-sites/Cloudflare side.
Each stage is also independently runnable with its own tool, the same way
it's always been done -- this script only sequences them and stops on the
first failure.

Usage:
    python tools/go_live.py "Kentville, NS" --sites-repo ../strollopia-sites
    python tools/go_live.py "Kentville, NS" --dry-run
"""
import argparse
import os
import sys

import city_discover
import strollopia_import
from post_org_setup import post_org_setup
from api_client import get_org_policy
from strollopia_import import get_map_pk_from_policy
from generate_deploy_script import generate_deploy_script, print_manual_checklist


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Discover a city's POIs, provision the org, and generate "
                    "the deploy script for a strollopia.com trial site."
    )
    parser.add_argument("city", help='City name passed to geocoder (e.g. "Kentville, NS")')
    parser.add_argument("--api-key", default=os.environ.get("GOOGLE_PLACES_API_KEY"),
                        help="Google Places API key (or set GOOGLE_PLACES_API_KEY env var)")
    parser.add_argument("--domain", default=None,
                        help="Explicit org domain. If omitted, auto-generated from geocoder result.")
    parser.add_argument("--languages", default="en",
                        help="Comma-separated language codes (default: en)")
    parser.add_argument("--maps", default="businesses,landmarks,public-art,parks",
                        help="Comma-separated presets to run (default: all four)")
    parser.add_argument("--source", choices=["google", "template"], default="google",
                        help="POI data source. 'template' (org-supplied CSV) is not yet implemented.")
    parser.add_argument("--path", choices=["map", "pwa"], default="map",
                        help="Deploy target. 'pwa' is not yet implemented.")
    parser.add_argument("--sites-repo", default=None,
                        help="Path to a strollopia-sites checkout (required for --path map)")
    parser.add_argument("--output-dir", default="org-data",
                        help="Base output directory (default: org-data)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run import in dry-run mode; stop before deploy-script generation")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing discovery output files")
    args = parser.parse_args(argv)

    if args.source == "template":
        print("--source template is not yet implemented.")
        print("Build org-setup.yaml, map-data.tsv, and import-schema.yaml by hand")
        print("(see README.md), then run post_org_setup.py / strollopia_import.py")
        print("directly against that directory.")
        return 1

    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    preset_names = [name.strip() for name in args.maps.split(",") if name.strip()]

    print("=== Stage 1: Discovery ===")
    result = city_discover.run(
        city=args.city, api_key=args.api_key, domain=args.domain,
        languages=languages, preset_names=preset_names,
        init=True, no_photos=False, force=args.force, output_dir=args.output_dir,
    )
    org_slug = result["org_slug"]
    domain = result["domain"]
    display_name = result["display_name"]
    yaml_path = os.path.join(args.output_dir, org_slug, "org-setup.yaml")

    print(f"\nmain_admin_email is blank in {yaml_path} -- fill it in before continuing.")
    input("Press Enter once org-setup.yaml is ready to post (Ctrl+C to stop here): ")

    print("\n=== Stage 2: Org creation ===")
    if not post_org_setup(yaml_path):
        print("\nOrg creation failed -- fix the error above, then re-run:")
        print(f"  python tools/post_org_setup.py {org_slug}")
        return 1

    print("\n=== Stage 3: Data import ===")
    import_argv = [os.path.join(args.output_dir, org_slug), "--all-maps"]
    if args.dry_run:
        import_argv.append("--dry-run")
    import_result = strollopia_import.main(import_argv)
    if import_result != 0:
        print("\nImport failed -- fix the error above, then re-run:")
        print(f"  python tools/strollopia_import.py {os.path.join(args.output_dir, org_slug)} --all-maps")
        return 1

    if args.dry_run:
        print("\n--dry-run: stopping before deploy-script generation.")
        return 0

    if args.path == "pwa":
        print(f"\n--path pwa is not yet implemented.")
        print(f"Org and data are provisioned under '{org_slug}'. Finish onboarding")
        print("manually via strollopia_pwa's own setup for the PWA deploy path.")
        return 0

    print("\n=== Stage 4: Deploy script generation ===")
    if not args.sites_repo:
        print("--sites-repo is required for --path map (path to a strollopia-sites checkout).")
        return 1

    org_policy = get_org_policy(domain)
    primary_map_dir = city_discover.PRESETS[preset_names[0]]["dir_name"]
    map_id = get_map_pk_from_policy(org_policy, primary_map_dir)
    if map_id is None:
        print(f"Could not find map pk for '{primary_map_dir}' in org policy -- "
              f"check the org was created correctly.")
        return 1

    script_path = os.path.join(args.output_dir, org_slug, "deploy.sh")
    generate_deploy_script(
        org_slug=org_slug, display_name=display_name, map_id=map_id,
        sites_repo=args.sites_repo, output_path=script_path,
    )
    print(f"Deploy script written to: {script_path}")
    print("Review it, then run it to deploy the trial site.")
    print_manual_checklist(org_slug, domain)

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_go_live.py -v
```

Expected: all tests PASS. (`generate_deploy_script.py` doesn't exist yet — Task 6 creates it — but since the tests patch `go_live.generate_deploy_script`/`go_live.city_discover.run` etc. rather than calling the real implementations, importing `go_live` only requires the *module* `generate_deploy_script.py` to exist so the `from generate_deploy_script import ...` line resolves. If Step 4 fails with `ModuleNotFoundError: No module named 'generate_deploy_script'`, stop and do Task 6 first, then resume here.)

- [ ] **Step 5: Commit**

```bash
git add tools/go_live.py tests/test_go_live.py
git commit -m "feat: add go_live.py orchestrator for the simple-map onboarding path

Sequences city_discover.py -> post_org_setup.py -> strollopia_import.py
-> generate_deploy_script.py, stopping on the first failure. --path pwa
and --source template are stubbed with a clear explanation rather than
built, per the go-live pipeline design spec."
```

---

## Task 6: `generate_deploy_script.py`

Turns `_template`'s manual `ONBOARDING.md` steps (copy, token-substitute,
create KV namespace, create Pages project, deploy) into one generated,
reviewable shell script. Does not execute anything itself, and does not
attempt the Cloudflare custom-domain/DNS steps — those get printed as a
checklist (`print_manual_checklist`), since they need dashboard access or
an elevated API token this pipeline doesn't have.

**Files:**
- Create: `strollopia-org-setup/tools/generate_deploy_script.py`
- Create: `strollopia-org-setup/tests/test_generate_deploy_script.py`

**Interfaces:**
- Produces: `generate_deploy_script(org_slug, display_name, map_id, sites_repo, output_path=None) -> str` — returns the script text; writes+chmods it executable at `output_path` if given.
- Produces: `print_manual_checklist(org_slug, domain) -> None`.
- Consumed by: Task 5's `go_live.py` (already written above, assuming these two names).

- [ ] **Step 1: Write the failing tests**

Create `strollopia-org-setup/tests/test_generate_deploy_script.py`:

```python
"""Tests for generate_deploy_script.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

import stat
from generate_deploy_script import generate_deploy_script


def test_generated_script_substitutes_all_tokens():
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/home/john/strollopia_git_hub/strollopia-sites",
    )
    assert "REPLACE_MAP_ID" not in script
    assert "REPLACE_WITH_SITE_SLUG" not in script
    assert "Your Site Name" not in script
    assert "ca-ns-kentville" in script
    assert "Kentville" in script
    assert "42" in script
    assert "/home/john/strollopia_git_hub/strollopia-sites" in script


def test_generated_script_references_correct_site_dir():
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert "sites/ca-ns-kentville" in script
    assert "cp -r _template sites/ca-ns-kentville" in script


def test_generated_script_creates_kv_namespace_with_slug_prefix():
    script = generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites",
    )
    assert 'ca-ns-kentville-SPLASH_CONTENT' in script


def test_generate_deploy_script_writes_executable_file(tmp_path):
    output_path = tmp_path / "deploy.sh"
    generate_deploy_script(
        org_slug="ca-ns-kentville", display_name="Kentville",
        map_id=42, sites_repo="/tmp/sites", output_path=str(output_path),
    )
    assert output_path.exists()
    mode = output_path.stat().st_mode
    assert mode & stat.S_IXUSR
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_generate_deploy_script.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'generate_deploy_script'`.

- [ ] **Step 3: Implement it**

Create `strollopia-org-setup/tools/generate_deploy_script.py`:

```python
#!/usr/bin/env python3
"""Generate a reviewable shell script that deploys a trial site from
strollopia-sites/_template for a newly-provisioned org.

This does not execute anything -- it only writes a script for a human to
read and run. The Cloudflare custom-domain and DNS steps are deliberately
left out of the script (see print_manual_checklist) since they need
dashboard access or an elevated API token this pipeline doesn't have.
"""
import os


DEPLOY_SCRIPT_TEMPLATE = """#!/bin/bash
set -euo pipefail
cd {sites_repo}

# 1. Copy the template
cp -r _template {site_dir}

# 2. Replace placeholders
find {site_dir} -type f \\( -name '*.html' -o -name '*.toml' \\) -exec \\
  sed -i \\
    -e 's/REPLACE_MAP_ID/{map_id}/g' \\
    -e 's/REPLACE_WITH_SITE_SLUG/{org_slug}/g' \\
    -e 's/Your Site Name/{display_name}/g' \\
  {{}} +
sed -i 's/const MAP_ID      = null;.*/const MAP_ID      = {map_id};/' {site_dir}/admin.html
mv {site_dir}/maps/REPLACE_MAP_ID {site_dir}/maps/{map_id}

# 3. Create the KV namespace, then paste its id into wrangler.toml by hand
#    (wrangler prints the id; there's no scripted way to feed it back into
#    this same run without a second manual step)
npx wrangler kv namespace create "{kv_title}"
echo "Paste the id above into {site_dir}/wrangler.toml's REPLACE_WITH_NEW_KV_NAMESPACE_ID, then press Enter to continue."
read -r

# 4. Create the Cloudflare Pages project
npx wrangler pages project create {org_slug} --production-branch main

# 5. Deploy
cd {site_dir} && npx wrangler pages deploy . --project-name {org_slug} --commit-dirty=true
"""


def generate_deploy_script(org_slug, display_name, map_id, sites_repo, output_path=None):
    """Build the deploy script for one org. Returns the script text.

    Writes it to output_path (executable) if given.
    """
    site_dir = os.path.join("sites", org_slug)
    kv_title = f"{org_slug}-SPLASH_CONTENT"
    script = DEPLOY_SCRIPT_TEMPLATE.format(
        sites_repo=sites_repo,
        site_dir=site_dir,
        map_id=map_id,
        org_slug=org_slug,
        display_name=display_name,
        kv_title=kv_title,
    )
    if output_path:
        with open(output_path, "w") as f:
            f.write(script)
        os.chmod(output_path, 0o755)
    return script


def print_manual_checklist(org_slug, domain):
    """Print the Cloudflare-dashboard-only steps that can't be scripted."""
    print(f"""
Manual steps (Cloudflare dashboard -- need dashboard access or an elevated API token):
  1. Attach custom domain: Workers & Pages -> {org_slug} -> Custom domains
     -> Add a domain -> {domain}
  2. Create DNS record: strollopia.com zone -> DNS -> Add record
       Type: CNAME   Name: {org_slug}   Target: {org_slug}.pages.dev
       Proxy status: Proxied
  3. Wait ~1-2 minutes for the certificate, then run:
       python tools/check_live.py {domain}
""")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_generate_deploy_script.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Now that this module exists, re-run Task 5's tests**

```bash
python -m pytest tests/test_go_live.py -v
```

Expected: all tests PASS (this resolves the `ModuleNotFoundError` noted at the end of Task 5, if it was hit).

- [ ] **Step 6: Commit**

```bash
git add tools/generate_deploy_script.py tests/test_generate_deploy_script.py
git commit -m "feat: add generate_deploy_script.py for the Cloudflare/site deploy step

Generates (does not execute) the copy/token-substitute/KV/Pages/deploy
script from strollopia-sites' _template, per Approach B in the go-live
pipeline design spec -- automate the data layer, generate the deploy
commands for human review rather than executing them directly."
```

---

## Task 7: `check_live.py`

**Files:**
- Create: `strollopia-org-setup/tools/check_live.py`
- Create: `strollopia-org-setup/tests/test_check_live.py`

**Interfaces:**
- Produces: `check_live(domain, map_id=None, timeout=10) -> bool`.
- Produces: `main(argv=None) -> int` (CLI entry point; run by hand after the manual Cloudflare steps, per the spec — not called from `go_live.py`).

- [ ] **Step 1: Write the failing tests**

Create `strollopia-org-setup/tests/test_check_live.py`:

```python
"""Tests for check_live.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from unittest.mock import patch, MagicMock
import requests
from check_live import check_live


def _mock_response(status_code, text):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_check_live_succeeds_for_valid_template_site():
    with patch("check_live.requests.get", return_value=_mock_response(200, "...Open the Map...")):
        assert check_live("ca-ns-kentville.strollopia.com") is True


def test_check_live_fails_on_non_200():
    with patch("check_live.requests.get", return_value=_mock_response(404, "not found")):
        assert check_live("ca-ns-kentville.strollopia.com") is False


def test_check_live_fails_when_page_doesnt_look_like_the_template():
    with patch("check_live.requests.get", return_value=_mock_response(200, "<html>parked domain</html>")):
        assert check_live("ca-ns-kentville.strollopia.com") is False


def test_check_live_fails_on_connection_error():
    with patch("check_live.requests.get", side_effect=requests.exceptions.ConnectionError("dns failure")):
        assert check_live("ca-ns-kentville.strollopia.com") is False


def test_check_live_also_checks_map_page_when_map_id_given():
    splash = _mock_response(200, "...Open the Map...")
    map_page = _mock_response(200, "/embed/maps/42/")
    with patch("check_live.requests.get", side_effect=[splash, map_page]) as mock_get:
        assert check_live("ca-ns-kentville.strollopia.com", map_id=42) is True
    urls_requested = [call.args[0] for call in mock_get.call_args_list]
    assert "https://ca-ns-kentville.strollopia.com/" in urls_requested
    assert "https://ca-ns-kentville.strollopia.com/maps/42/" in urls_requested


def test_check_live_fails_when_map_page_missing_embed_reference():
    splash = _mock_response(200, "...Open the Map...")
    map_page = _mock_response(200, "<html>no iframe here</html>")
    with patch("check_live.requests.get", side_effect=[splash, map_page]):
        assert check_live("ca-ns-kentville.strollopia.com", map_id=42) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_check_live.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'check_live'`.

- [ ] **Step 3: Implement it**

Create `strollopia-org-setup/tools/check_live.py`:

```python
#!/usr/bin/env python3
"""HTTP-level check that a deployed trial site is live and correctly wired.

Run by hand after completing the manual Cloudflare custom-domain/DNS steps
printed by generate_deploy_script.py's print_manual_checklist -- this is
not called automatically by go_live.py.

Usage:
    python tools/check_live.py ca-ns-kentville.strollopia.com
    python tools/check_live.py ca-ns-kentville.strollopia.com --map-id 42
"""
import argparse
import sys

import requests


def check_live(domain, map_id=None, timeout=10):
    """Return True if the trial site is live and looks like our template.

    Prints a diagnosis either way. If map_id is given, also checks that the
    map page responds and references the right embed URL.
    """
    url = f"https://{domain}/"
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        print(f"FAIL: could not reach {url}: {exc}")
        return False

    if resp.status_code != 200:
        print(f"FAIL: {url} returned HTTP {resp.status_code}")
        return False

    if "Open the Map" not in resp.text:
        print(f"FAIL: {url} responded 200 but doesn't look like the strollopia "
              f"template (missing \"Open the Map\" link)")
        return False

    print(f"OK: {url} is live and looks like the strollopia template.")

    if map_id is None:
        return True

    map_url = f"https://{domain}/maps/{map_id}/"
    try:
        map_resp = requests.get(map_url, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        print(f"FAIL: could not reach {map_url}: {exc}")
        return False

    if map_resp.status_code != 200:
        print(f"FAIL: {map_url} returned HTTP {map_resp.status_code}")
        return False

    if f"/embed/maps/{map_id}/" not in map_resp.text:
        print(f"FAIL: {map_url} responded 200 but doesn't reference "
              f"/embed/maps/{map_id}/ -- MAP_ID may be wrong.")
        return False

    print(f"OK: {map_url} is live and correctly wired to map {map_id}.")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check that a deployed trial site is live and correctly wired."
    )
    parser.add_argument("domain", help="e.g. ca-ns-kentville.strollopia.com")
    parser.add_argument("--map-id", type=int, default=None,
                        help="Also check the map page at /maps/<id>/")
    args = parser.parse_args(argv)

    ok = check_live(args.domain, map_id=args.map_id)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_check_live.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/check_live.py tests/test_check_live.py
git commit -m "feat: add check_live.py for post-deploy verification

Plain HTTP check (not a full browser harness) confirming the trial site
responds, looks like the strollopia template, and -- when --map-id is
given -- that the map page is correctly wired to the right embed URL.
Run by hand after the manual Cloudflare custom-domain/DNS steps."
```

---

## Task 8: Full pipeline smoke test + README/CLAUDE.md update

**Files:**
- Modify: `strollopia-org-setup/README.md`
- Create: `strollopia-org-setup/CLAUDE.md`
- Create: `strollopia-org-setup/tests/test_go_live_integration.py`

**Interfaces:** None new — this task documents and integration-tests what Tasks 1-7 produced.

- [ ] **Step 1: Write an integration test exercising the real (non-mocked) discovery→schema-resolution chain**

This complements Task 5's unit tests (which mock every stage) by proving the
real output of `city_discover.run()` is something `strollopia_import`'s own
path-resolution functions can actually consume — the exact gap that made
Task 2 necessary in the first place.

Create `strollopia-org-setup/tests/test_go_live_integration.py`:

```python
"""Integration test: city_discover.py's real output is importable.

Exercises the actual glue between Task 1 (city_discover.py) and Task 2
(per-language schema/data resolution in strollopia_import.py) without
mocking either -- only the network calls (geocoding, Places, OSM) are
mocked, since this test must not require a real API key or network access.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

from unittest.mock import patch
from city_discover import run
from strollopia_import import find_map_dirs, resolve_map_dir_paths


def test_city_discover_output_is_importable(tmp_path):
    geocode_result = {
        "lat": 45.0779, "lng": -64.4934,
        "country_code": "CA", "state": "Nova Scotia", "city": "Kentville",
        "bbox": (45.05, -64.52, 45.10, -64.46),
    }
    fake_place = {
        "name": "Test Cafe", "lat": 45.0779, "lng": -64.4934,
        "category": "Business", "subcategory": "Cafe",
        "description": "<b>Test Cafe</b>", "phone": "", "website": "", "address": "",
        "hours_mon": "closed", "hours_tue": "closed", "hours_wed": "closed",
        "hours_thu": "closed", "hours_fri": "closed", "hours_sat": "closed",
        "hours_sun": "closed", "image_file": "",
        "_source": "google", "_place_id": "abc", "_photo_reference": None,
    }
    with patch("city_discover.geocode_city", return_value=geocode_result), \
         patch("city_discover.discover_google", return_value=[fake_place]), \
         patch("city_discover.discover_osm", return_value=[]):
        result = run(
            city="Kentville, NS", api_key="fake-key", domain=None,
            languages=["en", "fr"], preset_names=["businesses"],
            init=True, no_photos=True, force=False,
            output_dir=str(tmp_path),
        )

    org_dir = result["org_dir"]
    map_dirs = find_map_dirs(org_dir)
    assert len(map_dirs) == 1
    assert os.path.basename(map_dirs[0]) == "business-map"

    # Both languages produced a schema+data pair strollopia_import can resolve
    paths_en = resolve_map_dir_paths(map_dirs[0], schema_path=os.path.join(map_dirs[0], "import-schema.en.yaml"))
    assert os.path.isfile(paths_en["data"])
    paths_fr = resolve_map_dir_paths(map_dirs[0], schema_path=os.path.join(map_dirs[0], "import-schema.fr.yaml"))
    assert os.path.isfile(paths_fr["data"])
```

- [ ] **Step 2: Run the test to verify it fails before Task 2's fix would have existed**

This step is a sanity check on the test itself, not on current code (Task 2
is already done by this point in the plan). Run it directly and confirm it
passes for the right reason:

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
python -m pytest tests/test_go_live_integration.py -v
```

Expected: PASS. If it fails, re-check Task 2's implementation before proceeding.

- [ ] **Step 3: Run the entire test suite one more time**

```bash
python -m pytest tests/ -v
```

Expected: every test across Tasks 1-8 passes.

- [ ] **Step 4: Write `CLAUDE.md`**

Create `strollopia-org-setup/CLAUDE.md`:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Setup

```bash
pip install -r requirements.txt
```

All scripts in `tools/` must be run from the repo root (they use relative paths like `org-data/`).

## Common Commands

```bash
# Run the full go-live pipeline for a new town (simple-map path)
python tools/go_live.py "Kentville, NS" --sites-repo ../strollopia-sites

# Dry run (discovery + org creation for real, import in dry-run mode, stops before deploy script)
python tools/go_live.py "Kentville, NS" --dry-run

# Run any stage standalone (same tools go_live.py calls internally):
python tools/city_discover.py "Kentville, NS" --languages en --init
python tools/post_org_setup.py <org_slug>
python tools/strollopia_import.py org-data/<org_slug>/ --all-maps
python tools/check_live.py <domain> --map-id <pk>

# Run tests
python -m pytest tests/ -v
```

## Environment Variables

| Variable | Target |
|---|---|
| `USE_LOCAL_HOST=1` | `http://127.0.0.1:8000/` |
| `USE_PROD=1` | `https://prod.strollopia.com/` |
| (default) | `https://dev.strollopia.com/` |
| `GOOGLE_PLACES_API_KEY` | Enables Google Places discovery in `city_discover.py`/`go_live.py`; falls back to OSM-only without it |

## Architecture

### Tool Overview

- **`tools/city_discover.py`** — Discovers businesses/landmarks/public-art/parks for a city via Google Places + OpenStreetMap Overpass, writes `map-data.<lang>.tsv` + `import-schema.<lang>.yaml` per preset per language, and (with `--init`) `org-setup.yaml`. `run()` returns `{org_slug, org_dir, domain, display_name}`.
- **`tools/go_live.py`** — Orchestrates `city_discover.py` -> `post_org_setup.py` -> `strollopia_import.py` -> `generate_deploy_script.py` for the simple-map onboarding path. `--path pwa` and `--source template` are stubbed, not implemented.
- **`tools/generate_deploy_script.py`** — Generates (does not execute) the `strollopia-sites` `_template` copy/token-substitution/Cloudflare KV+Pages+deploy script for one org. The custom-domain/DNS steps are printed as a manual checklist instead, since they need dashboard access or an elevated API token.
- **`tools/check_live.py`** — Plain HTTP check that a deployed trial site (and optionally its map page) is live and correctly wired. Run by hand after the manual Cloudflare steps.
- **`tools/org_yaml_wizard.py`** — 9-step interactive CLI wizard that creates `org-setup.yaml` (adds a Theme step for the separate PWA path). Saves progress as `.org-setup-draft.yaml` after each step. `--review` re-runs all steps with saved answers as defaults.
- **`tools/post_org_setup.py`** — Posts an `org-setup.yaml` to the server's `/api/core/admin/organizations/initialize/yaml/` endpoint. Requires Django super-admin credentials.
- **`tools/strollopia_import.py`** — Unified POI data import tool. Reads TSV/CSV + schema YAML (legacy `import-schema.yaml` or per-language `import-schema.<lang>.yaml`) and POSTs GeoJSON Features to the REST API.
- **`tools/api_client.py`** — Low-level HTTP helpers used by every other tool.

### Directory Convention

Directory names are **stable slugs**, not domain names — e.g. `org-data/kentville/`, never `org-data/kentville.strollopia.com/`. The runtime `org_domain_name` lives inside `org-setup.yaml` and is the authoritative source, so an org can relaunch under a new domain by editing that one field, without renaming its directory or losing git history.

```
org-data/
└── <org_slug>/
    ├── org-setup.yaml          # contains org_domain_name: kentville.strollopia.com
    ├── deploy.sh               # generated by generate_deploy_script.py, not committed
    └── <map-name>/             # directory name = org map name
        ├── import-schema.<lang>.yaml   # or legacy import-schema.yaml
        ├── map-data.<lang>.tsv         # or legacy map-data.tsv
        └── media/
```

### Two Deploy Paths

- **Simple map** (this repo's `go_live.py`, implemented) — a Cloudflare Pages site from `strollopia-sites`' `_template`, embedding the map via iframe. No PWA features, fastest to roll out.
- **PWA** (`data_logger`/`strollopia_pwa` on Vercel, limited pilot, not built here) — richer, app-like experience. `org_yaml_wizard.py`'s Step 9 (Theme) belongs to this path. `go_live.py --path pwa` stops after data provisioning and points at finishing manually.
```

- [ ] **Step 5: Update `README.md`**

Add a new section right after the "## Setting Up a New Organization" heading in `strollopia-org-setup/README.md`:

```markdown
## Go-Live Pipeline (New Towns)

For a brand-new town with no existing data, `go_live.py` chains discovery,
org creation, and import into one command, then generates the Cloudflare
deploy script:

```bash
python tools/go_live.py "Kentville, NS" --sites-repo ../strollopia-sites
```

Each stage is also runnable standalone with its own tool below, the same
way it's always been done — `go_live.py` only sequences them and stops on
the first failure. See `CLAUDE.md` for the full command reference.

```

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md tests/test_go_live_integration.py
git commit -m "docs: document the go-live pipeline in CLAUDE.md/README.md

Adds an integration test proving city_discover.py's real (unmocked)
output is importable by strollopia_import.py's schema-resolution
functions -- the exact gap Task 2 fixed -- and documents the full
tool set, directory convention, and the two deploy paths (simple-map,
implemented; PWA, stubbed) for future Claude Code sessions."
```

---

## Deliberately Not Built (per spec)

- `strollopia-clean` is left in place but should be treated as archived —
  no further work should happen there. (Not deleted, per the spec's
  reconciliation plan, in case anything was missed.)
- `--source template` (org-supplied Excel/CSV upload) and `--path pwa`
  (Vercel/data_logger deploy) — both stop cleanly with an explanation,
  per the spec's explicitly deferred scope.
- Cloudflare API automation for custom-domain attachment and DNS record
  creation.
