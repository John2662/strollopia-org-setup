# strollopia-org-setup

Org configuration and data import tools for Strollopia.

## Repo Structure

```
strollopia-org-setup/
├── tools/
│   ├── org_yaml_wizard.py      # Interactive wizard to create org-setup.yaml
│   ├── wizard_defaults.yaml    # Default values used by the wizard
│   ├── post_org_setup.py       # Post org-setup.yaml to the server
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

# Review/correct a draft after interrupting (Ctrl+C)
python tools/org_yaml_wizard.py myorg.strollopia.com --review

# Edit an existing org config
python tools/org_yaml_wizard.py --edit org-data/myorg.strollopia.com/org-setup.yaml
```

The wizard saves progress after each step, so you can press Ctrl+C at any time
and pick up later with `--review`. The review flag re-runs every step with your
previous answers as defaults — just press Enter to keep a value or retype it to
correct it. On completion the wizard writes `org-setup.yaml` and creates the
directory structure under `org-data/`.

For a detailed explanation of every wizard step (suitable for end-users and the
website team), see **[wizard-guide.txt](wizard-guide.txt)**.

## Posting an Org to the Server

After the wizard writes `org-setup.yaml`, it offers to post it to the server.
You can also post it separately using the standalone script. A Django super-admin
account is required (this is different from the org admin defined in the YAML).

```bash
# Post an org-setup.yaml to the server (prompts for super-admin credentials)
python tools/post_org_setup.py myorg.strollopia.com
```

The target server is controlled by the environment variables listed below.

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
