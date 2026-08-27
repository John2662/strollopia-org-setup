# Setting Up wolfville.strollopia.com on Production — From Scratch

Reference steps for (re-)deploying the `wolfville.strollopia.com` org config and
data to the **production** Strollopia server (`https://prod.strollopia.com/`).

## 0. Prerequisites

- Repo cloned: `strollopia-org-setup`
- pCloud Drive installed and signed in, mounted at
  `/home/john/pCloudDrive/strollopia_org_data` (media files for this org live
  there, not in git — see `README_symlink.md`)
- A Django **super-admin** account on prod (different from the org's own admin
  account defined in `org-setup.yaml`)

## 1. Enter the repo and activate the virtualenv

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
```

## 2. Install/confirm dependencies

```bash
pip install -r requirements.txt
```

## 3. Restore the media symlink (if starting on a fresh checkout/machine)

The `downtown/media` folder for Wolfville is a symlink to pCloud, not a
tracked git folder.

```bash
python migrate_media_to_pcloud.py . /home/john/pCloudDrive/strollopia_org_data --relink-only

# verify it resolved
ls -la org-data/wolfville.strollopia.com/downtown/media
```

You should see it point (`->`) at:
`/home/john/pCloudDrive/strollopia_org_data/org-data/wolfville.strollopia.com/downtown/media`

## 4. Point the tools at production

The target server is controlled by env vars read in `tools/api_client.py`.

```bash
unset USE_LOCAL_HOST
export USE_PROD=1
```

(default with both unset is `https://dev.strollopia.com/`)

## 5. Confirm/edit the org config

`org-data/wolfville.strollopia.com/org-setup.yaml` already exists in this
repo. Review it, and edit if anything needs updating (domain, admin email,
categories, map defaults, etc.):

```bash
python tools/org_yaml_wizard.py --edit org-data/wolfville.strollopia.com/org-setup.yaml
```

**Important:** the checked-in file has a placeholder admin password
(`changeme123`). Replace it with a real password before posting to
production.

## 6. Post the org config to prod

This creates/updates the org and its main admin account on the server. You'll
be prompted for **super-admin** credentials (not the org admin from the
YAML).

```bash
python tools/post_org_setup.py wolfville.strollopia.com
```

## 7. Validate the map data before importing

```bash
python tools/strollopia_import.py org-data/wolfville.strollopia.com/downtown/ --validate-only
```

## 8. Dry-run the import (optional but recommended)

```bash
python tools/strollopia_import.py org-data/wolfville.strollopia.com/downtown/ --dry-run
```

## 9. Run the real import

Import just the `downtown` map:

```bash
python tools/strollopia_import.py org-data/wolfville.strollopia.com/downtown/
```

Or, if the org gains more maps later, import all of them at once:

```bash
python tools/strollopia_import.py org-data/wolfville.strollopia.com/ --all-maps
```

If you don't want the org's admin password stored in the YAML/on disk, pass
credentials on the command line instead:

```bash
python tools/strollopia_import.py org-data/wolfville.strollopia.com/downtown/ \
  --email admin@example.com --password 'secret'
```

## 10. Verify

- Visit the viewer URL: `https://wolfville.viewer.strollopia.com`
- Confirm points of interest, media, and categories loaded correctly.

## 11. When done

```bash
deactivate
```

---

### Quick reference — switching target servers

| Command | Target |
|---|---|
| `unset USE_LOCAL_HOST && unset USE_PROD` | dev (default) — `https://dev.strollopia.com/` |
| `export USE_LOCAL_HOST=1` | local — `http://127.0.0.1:8000/` |
| `unset USE_LOCAL_HOST && export USE_PROD=1` | **production** — `https://prod.strollopia.com/` |
