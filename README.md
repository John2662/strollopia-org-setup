# strollopia-org-setup

Org configuration and data import tools for Strollopia.

## Repo Structure

```
strollopia-org-setup/
├── tools/
│   ├── org_yaml_wizard.py      # Interactive wizard to create org-setup.yaml
│   ├── wizard_defaults.yaml    # Default values used by the wizard
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

## Setting Up a New Organization

Use the interactive wizard to create the `org-setup.yaml` configuration file for
a new organization. The wizard walks through each setting step by step.

```bash
pip install -r requirements.txt

# Start the wizard for a new org
python tools/org_yaml_wizard.py myorg.strollopia.com

# Resume a wizard that was interrupted (Ctrl+C)
python tools/org_yaml_wizard.py myorg.strollopia.com --resume

# Edit an existing org config
python tools/org_yaml_wizard.py --edit org-data/myorg.strollopia.com/org-setup.yaml
```

The wizard saves progress after each step, so you can press Ctrl+C at any time
and resume later with `--resume`. On completion it writes `org-setup.yaml` and
creates the directory structure under `org-data/`.

For a detailed explanation of every wizard step (suitable for end-users and the
website team), see **[wizard-guide.txt](wizard-guide.txt)**.

## Importing Data

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
