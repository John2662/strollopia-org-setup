# strollopia-org-setup

Org configuration and data import tools for Strollopia.

## Repo Structure

```
strollopia-org-setup/
├── tools/
│   ├── strollopia_import.py    # Unified data import tool
│   └── api_client.py           # API helpers
│
└── org-data/
    └── <org_domain_name>/      # e.g. kentville.strollopia.com
        ├── org-setup.yaml      # Org config + admin credentials
        │
        └── <map-name>/         # Directory name = org map name
            ├── import-schema.yaml
            ├── map-data.tsv
            └── media/
```

The directory name under each org **is** the org map name. The import script
derives map name, media paths, and org credentials from the directory structure.

## Usage

```bash
pip install -r requirements.txt

# Import a single map
python tools/strollopia_import.py org-data/kentville.strollopia.com/main-map/

# Dry run (build payloads without posting)
python tools/strollopia_import.py org-data/kentville.strollopia.com/main-map/ --dry-run

# Validate only (check schema columns match data headers)
python tools/strollopia_import.py org-data/kentville.strollopia.com/main-map/ --validate-only

# Import all maps for an org
python tools/strollopia_import.py org-data/kentville.strollopia.com/ --all-maps
```

Explicit overrides are available: `--schema`, `--data`, `--org-credentials`, `--delimiter`.

## Environment Variables

| Variable | Target |
|----------|--------|
| `USE_LOCAL_HOST=1` | `http://127.0.0.1:8000/` |
| `USE_PROD=1` | `https://prod.strollopia.com/` |
| (default) | `https://dev.strollopia.com/` |
