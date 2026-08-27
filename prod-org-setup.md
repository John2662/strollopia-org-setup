# Setting Up an Org on Production — From Scratch

Reference steps for deploying an org's config and map data to the
**production** Strollopia server (`https://prod.strollopia.com/`).

Replace `<org>` with the org domain (e.g. `wolfville.strollopia.com`) and
`<map>` with the map directory name (e.g. `downtown`) throughout.

## 0. Prerequisites

- Repo cloned: `strollopia-org-setup`
- pCloud Drive installed and signed in, mounted at
  `/home/john/pCloudDrive/strollopia_org_data` (media files live there, not
  in git — see `README_symlink.md`)
- A Django **super-admin** account on prod (different from the org's own
  admin account defined in `org-setup.yaml`)

## 1. Enter the repo and activate the virtualenv

```bash
cd /home/john/strollopia_git_hub/strollopia-org-setup
source env/bin/activate
```

## 2. Install/confirm dependencies

```bash
pip install -r requirements.txt
```

## 3. Restore media symlinks (if starting on a fresh checkout/machine)

Media folders are symlinks to pCloud, not tracked git folders.

```bash
python migrate_media_to_pcloud.py . /home/john/pCloudDrive/strollopia_org_data --relink-only

# verify — should show an arrow (->) pointing into pCloudDrive
ls -la org-data/<org>/<map>/media
```

If the path already exists as a **real directory** instead of a symlink (a
prior migration got undone somehow), `--relink-only` will silently skip it —
it only creates symlinks where nothing exists yet. Fix: confirm the pCloud
copy matches (`ls org-data/<org>/<map>/media | wc -l` vs. the pCloud
equivalent), then `rm -rf` the real local directory and re-run
`--relink-only`.

## 4. Point the tools at production

```bash
unset USE_LOCAL_HOST
export USE_PROD=1
```

(default with both unset is `https://dev.strollopia.com/`)

## 5. Confirm/edit the org config

Review `org-data/<org>/org-setup.yaml`, editing as needed:

```bash
python tools/org_yaml_wizard.py --edit org-data/<org>/org-setup.yaml
```

**Checklist before posting:**
- Replace any placeholder admin password (e.g. `changeme123`) with a real
  generated one.
- Make sure every entry under `org_maps:` has a matching directory with
  both `import-schema.yaml` and `map-data.tsv` already in place. Drop any
  map that isn't ready yet — `post_org_setup.py` will now warn about this
  automatically, but it's cheaper to catch by eye first.

## 6. Post the org config to prod

This creates/updates the org on the server. You'll be prompted for
**super-admin** credentials (not the org admin from the YAML).

```bash
python tools/post_org_setup.py <org>
```

`post_org_setup.py` now automatically re-attempts a login with the org
admin's email/password from the YAML right after posting, and warns loudly
if it fails. **Read that output carefully.**

### The most important gotcha here

`initialize_org_from_yaml` does **not** reset the password of an
already-existing user. If this org's `main_admin_email` was ever used
before under this same org domain — even with an old placeholder password
from an earlier setup attempt — posting again will report success
(`Organization created: {...}`), but the account silently keeps its
**original** password. The YAML's password is only what the account *will*
have on first creation, not necessarily what it *has now*.

If the post-creation login check warns of failure:
1. Don't guess blindly against the login endpoint. First confirm the
   account already exists by attempting `register_user()` with the same
   email/org — a `{'detail': 'email provided is currently registered'}`
   response confirms it (a real registration would succeed or fail
   differently).
2. Try whatever placeholder/earlier password this org's YAML used
   previously (check `git log -p -- org-data/<org>/org-setup.yaml`).
3. Once you find (or reset) the real working password, either update
   `org-setup.yaml` to match reality, or just pass `--email`/`--password`
   overrides to `strollopia_import.py` for this run without touching the
   file.
4. Separately, get that account's password changed to something secure
   through whatever real channel exists (Django admin backend, an actual
   password-reset flow) — this codebase currently has **no API endpoint**
   for changing a user's password, so it can't be done through these
   scripts.

## 7. Validate the map data before importing

```bash
python tools/strollopia_import.py org-data/<org>/<map>/ --validate-only
```

This only checks schema columns against data headers — no network call, no
login required.

## 8. Dry-run the import

```bash
python tools/strollopia_import.py org-data/<org>/<map>/ --dry-run
```

If step 6's login check failed and you're using a different real password
than what's in the YAML:

```bash
python tools/strollopia_import.py org-data/<org>/<map>/ --dry-run \
  --email admin@example.com --password 'the-real-password'
```

## 9. Run the real import

```bash
python tools/strollopia_import.py org-data/<org>/<map>/
```

Or all maps for the org at once:

```bash
python tools/strollopia_import.py org-data/<org>/ --all-maps
```

## 10. Verify

- Visit the org's viewer URL.
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
