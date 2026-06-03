#!/usr/bin/env python3
"""CLI wizard to build org-setup.yaml for Strollopia organizations."""

import argparse
import getpass
import os
import re
import sys

import yaml


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def ask(prompt, default=None, validator=None, secret=False):
    """Base input function with default display and validation retry."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        if secret:
            value = getpass.getpass(f"{prompt}{suffix}: ")
        else:
            value = input(f"{prompt}{suffix}: ")
        value = value.strip()
        if not value and default is not None:
            value = str(default)
        if not value:
            print("  A value is required.")
            continue
        if validator:
            err = validator(value)
            if err:
                print(f"  {err}")
                continue
        return value


def ask_optional(prompt, default=None):
    """Ask for an optional value (empty string accepted)."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ")
    value = value.strip()
    if not value and default:
        return default
    return value or None


def ask_yes_no(prompt, default=True):
    """y/n helper."""
    hint = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{hint}]: ").strip().lower()
        if not value:
            return default
        if value in ("y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("  Please enter y or n.")


def ask_choice(prompt, options):
    """Numbered list selection, returns the chosen option."""
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        value = input("Choice: ").strip()
        try:
            idx = int(value)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print(f"  Enter a number 1-{len(options)}.")


def ask_multi(prompt, options):
    """Multi-select with comma-separated indices, returns list of chosen options."""
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        value = input("Select (comma-separated numbers, or 'all'): ").strip()
        if value.lower() == "all":
            return list(options)
        try:
            indices = [int(x.strip()) for x in value.split(",")]
            if all(1 <= i <= len(options) for i in indices) and indices:
                return [options[i - 1] for i in indices]
        except ValueError:
            pass
        print(f"  Enter comma-separated numbers 1-{len(options)}, or 'all'.")


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

def validate_domain(value):
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*\.)+[a-zA-Z]{2,}$', value):
        return "Invalid domain format. Example: myorg.strollopia.com"
    return None


def validate_email(value):
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', value):
        return "Invalid email format."
    return None


def validate_lat(value):
    try:
        f = float(value)
        if not (-90 <= f <= 90):
            return "Latitude must be between -90 and 90."
    except ValueError:
        return "Must be a number."
    return None


def validate_lng(value):
    try:
        f = float(value)
        if not (-180 <= f <= 180):
            return "Longitude must be between -180 and 180."
    except ValueError:
        return "Must be a number."
    return None


def validate_slug(value):
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', value):
        return "Must be lowercase, alphanumeric with hyphens (e.g. main-map)."
    return None


# ---------------------------------------------------------------------------
# Wizard steps
# ---------------------------------------------------------------------------

def step_org_identity(defaults, existing, org_domain_name=None):
    """Step 1: Org Identity."""
    print("\n=== Step 1: Org Identity ===\n")

    org_domain_name = ask(
        "Org domain name",
        default=org_domain_name or existing.get("org_domain_name"),
        validator=validate_domain,
    )

    display_name = ask(
        "Display name",
        default=existing.get("display_name", ""),
    )

    tag_line = ask_optional(
        "Tag line (optional)",
        default=existing.get("tag_line"),
    )

    viewer_template = defaults.get("org_identity", {}).get(
        "viewer_template", "https://{name}.viewer.strollopia.com"
    )
    # Derive default viewer from domain name
    name_part = org_domain_name.split(".")[0]
    default_viewer = existing.get("viewer") or viewer_template.format(name=name_part)
    viewer = ask("Viewer URL", default=default_viewer)

    result = {
        "org_domain_name": org_domain_name,
        "display_name": display_name,
        "viewer": viewer,
    }
    if tag_line:
        result["tag_line"] = tag_line
    return result


def step_admin(defaults, existing):
    """Step 2: Admin Account."""
    print("\n=== Step 2: Admin Account ===\n")

    main_admin_email = ask(
        "Admin email",
        default=existing.get("main_admin_email"),
        validator=validate_email,
    )

    main_admin_name = ask(
        "Admin name",
        default=existing.get("main_admin_name", "Admin"),
    )

    default_pw = defaults.get("admin", {}).get("password", "changeme123")
    print(f"Admin password (leave blank for default '{default_pw}'):")
    pw = ask("Password", default=default_pw, secret=True)
    pw2 = ask("Confirm password", default=default_pw, secret=True)
    while pw != pw2:
        print("  Passwords do not match. Try again.")
        pw = ask("Password", default=default_pw, secret=True)
        pw2 = ask("Confirm password", default=default_pw, secret=True)

    return {
        "main_admin_email": main_admin_email,
        "main_admin_name": main_admin_name,
        "main_admin_password": pw,
    }


def step_map_defaults(existing):
    """Step 3: Map Defaults."""
    print("\n=== Step 3: Map Defaults ===\n")

    address = ask_optional("Enter a city/address for context (not stored in YAML)")
    if address:
        print(f"  Note: '{address}' is for your reference only.")

    lat = ask(
        "Default latitude",
        default=existing.get("map_default_lat"),
        validator=validate_lat,
    )
    lng = ask(
        "Default longitude",
        default=existing.get("map_default_lng"),
        validator=validate_lng,
    )

    return {
        "map_default_lat": float(lat),
        "map_default_lng": float(lng),
    }


def step_access(defaults, existing):
    """Step 4: Access & Anonymous Settings."""
    print("\n=== Step 4: Access & Anonymous Settings ===\n")

    default_anon = defaults.get("org_identity", {}).get("allows_anonymous", False)
    allows_anonymous = ask_yes_no(
        "Allow anonymous access?",
        default=existing.get("allows_anonymous", default_anon),
    )

    result = {"allows_anonymous": allows_anonymous}

    if allows_anonymous:
        anon_defaults = defaults.get("anonymous_settings", {})
        existing_anon = existing.get("anonymous_settings", {})
        print("\n  Anonymous settings:")
        period = ask(
            "  Session period (seconds)",
            default=existing_anon.get("period", anon_defaults.get("period", 3600)),
        )
        max_anon = ask(
            "  Max anonymous users",
            default=existing_anon.get("max_anon", anon_defaults.get("max_anon", 10)),
        )
        org_key = ask(
            "  Org key (unique string for anonymous tokens)",
            default=existing_anon.get("org_key"),
        )
        result["anonymous_settings"] = {
            "period": int(period),
            "max_anon": int(max_anon),
            "org_key": org_key,
        }

    default_restrict = defaults.get("org_identity", {}).get("restrict_public_map", True)
    restrict = ask_yes_no(
        "Restrict public map access?",
        default=existing.get("restrict_public_map", default_restrict),
    )
    result["restrict_public_map"] = restrict

    return result


def step_categories(existing):
    """Step 5: Categories."""
    print("\n=== Step 5: Categories ===\n")

    existing_cats = existing.get("categories", {})
    if existing_cats:
        print("Existing categories:")
        for cat, subs in existing_cats.items():
            if cat != "other":
                print(f"  {cat}: {', '.join(s for s in subs if s != 'other')}")
        if not ask_yes_no("Replace existing categories?", default=False):
            return {"categories": existing_cats}

    categories = {}
    print("Add categories (at least one required). Enter blank name to finish.\n")
    while True:
        name = ask_optional("Category name (blank to finish)")
        if not name:
            if not categories:
                print("  At least one category is required.")
                continue
            break
        subs_input = ask(
            f"  Subcategories for '{name}' (comma-separated)",
            default="other",
        )
        subs = [s.strip() for s in subs_input.split(",") if s.strip()]
        if "other" not in [s.lower() for s in subs]:
            subs.append("other")
        categories[name] = subs

    # Always append the catch-all other category
    categories["other"] = ["other"]

    return {"categories": categories}


def step_media_layouts(defaults, existing):
    """Step 6: Media Types & Layouts."""
    print("\n=== Step 6: Media Types & Layouts ===\n")

    all_types = defaults.get("mediatypes", ["richtext", "image", "audio", "video"])
    existing_types = existing.get("mediatypes", all_types)

    mediatypes = ask_multi(
        "Select media types to enable:",
        all_types,
    )

    # Layouts
    presets = defaults.get("layout_presets", {})
    existing_layouts = existing.get("layouts", {})

    print("\nAvailable layout presets:")
    preset_names = list(presets.keys())
    for name in preset_names:
        print(f"  {name}: {presets[name]}")

    layouts = {}
    if existing_layouts and not ask_yes_no("Replace existing layouts?", default=False):
        layouts = existing_layouts
    else:
        use_presets = ask_yes_no("Use preset layouts?", default=True)
        if use_presets:
            selected = ask_multi(
                "Select presets to include:",
                preset_names,
            )
            for name in selected:
                layouts[name] = presets[name]

        if ask_yes_no("Add a custom layout?", default=False):
            while True:
                lname = ask("Layout name", validator=validate_slug)
                fields = []
                counters = {}
                print(f"  Add fields to '{lname}'. Available types: {', '.join(mediatypes)}")
                print("  Enter blank to finish this layout.")
                while True:
                    ftype = ask_optional(f"  Field type ({'/'.join(mediatypes)}, blank to finish)")
                    if not ftype:
                        break
                    if ftype not in mediatypes:
                        print(f"    Unknown type. Choose from: {', '.join(mediatypes)}")
                        continue
                    prefix = {"richtext": "rt", "image": "i", "audio": "a", "video": "v"}.get(ftype, ftype[:2])
                    counters[prefix] = counters.get(prefix, 0) + 1
                    key = f"{prefix}{counters[prefix]}"
                    fields.append(f"{key}:{ftype}")
                    print(f"    Added {key}:{ftype}")
                if fields:
                    layouts[lname] = fields
                if not ask_yes_no("Add another custom layout?", default=False):
                    break

    return {"mediatypes": mediatypes, "layouts": layouts}


def step_maps(defaults, existing):
    """Step 7: Maps."""
    print("\n=== Step 7: Maps ===\n")

    map_defs = defaults.get("map_defaults", {})
    existing_maps = existing.get("org_maps", {})

    if existing_maps:
        print("Existing maps:")
        for name, cfg in existing_maps.items():
            print(f"  {name}: is_public={cfg.get('is_public', False)}")
        if not ask_yes_no("Replace existing maps?", default=False):
            return {"org_maps": existing_maps}

    org_maps = {}
    print("Add maps (at least one required). Enter blank name to finish.\n")
    while True:
        name = ask_optional("Map name/slug (blank to finish)")
        if not name:
            if not org_maps:
                print("  At least one map is required.")
                continue
            break
        err = validate_slug(name)
        if err:
            print(f"  {err}")
            continue
        is_pub = ask_yes_no(
            f"  Is '{name}' public?",
            default=map_defs.get("is_public", True),
        )
        default_langs = map_defs.get("languages", ["en"])
        langs_input = ask(
            f"  Languages (comma-separated)",
            default=",".join(default_langs),
        )
        langs = [l.strip() for l in langs_input.split(",") if l.strip()]

        map_cfg = {"is_public": is_pub}
        # languages stored at org level in ui_support, but we track per-map
        # for directory creation; not a serializer field on OrgMapSerializer
        org_maps[name] = map_cfg

    return {"org_maps": org_maps}


def step_ui_support(defaults, existing):
    """Step 8: UI Support (optional)."""
    print("\n=== Step 8: UI Support (optional) ===\n")

    ui_defaults = defaults.get("ui_support", {})
    existing_ui = existing.get("ui_support", {})

    if not ask_yes_no("Configure UI support settings?", default=bool(existing_ui)):
        return {}

    ui = {}

    if ask_yes_no("Enable editor?", default=bool(existing_ui.get("editor"))):
        ui["editor"] = existing_ui.get("editor", ui_defaults.get("editor", "ED"))

    if ask_yes_no("Enable builder?", default=bool(existing_ui.get("builder"))):
        ui["builder"] = existing_ui.get("builder", ui_defaults.get("builder", "BL"))

    if ask_yes_no("Enable datalogger?", default=bool(existing_ui.get("datalogger"))):
        ui["datalogger"] = existing_ui.get("datalogger", ui_defaults.get("datalogger", "DL"))

    default_lang = existing_ui.get(
        "default_language", ui_defaults.get("default_language", "en")
    )
    ui["default_language"] = ask("Default language", default=default_lang)

    return {"ui_support": ui}


# ---------------------------------------------------------------------------
# Draft save/load helpers
# ---------------------------------------------------------------------------

DRAFT_FILENAME = ".org-setup-draft.yaml"

STEP_NAMES = {
    1: "Org Identity",
    2: "Admin Account",
    3: "Map Defaults",
    4: "Access & Anonymous Settings",
    5: "Categories",
    6: "Media Types & Layouts",
    7: "Maps",
    8: "UI Support",
}


def _draft_path(output_dir, org_domain_name):
    """Return path to the draft file for an org."""
    return os.path.join(output_dir, org_domain_name, DRAFT_FILENAME)


def _save_draft(config, output_dir, org_domain_name):
    """Save current wizard state to draft file."""
    draft = _draft_path(output_dir, org_domain_name)
    os.makedirs(os.path.dirname(draft), exist_ok=True)
    with open(draft, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _load_draft(output_dir, org_domain_name):
    """Load draft file if it exists, return (config, last_completed_step) or (None, 0)."""
    draft = _draft_path(output_dir, org_domain_name)
    if not os.path.exists(draft):
        return None, 0
    with open(draft) as f:
        config = yaml.safe_load(f) or {}
    step = config.pop("_wizard_step", 0)
    return config, step


def _delete_draft(output_dir, org_domain_name):
    """Remove draft file if it exists."""
    draft = _draft_path(output_dir, org_domain_name)
    if os.path.exists(draft):
        os.remove(draft)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_wizard(defaults, existing=None, org_domain_name=None, output_dir="org-data/", start_step=1):
    """Run wizard steps and return the complete org config dict.

    Parameters
    ----------
    defaults : dict
        Wizard default values loaded from wizard_defaults.yaml.
    existing : dict | None
        Previously saved config (for --edit mode).
    org_domain_name : str | None
        Pre-fill for Step 1's domain prompt.
    output_dir : str
        Base directory for org data (used for draft saving).
    start_step : int
        Step number to start from (1-8). Steps before this are skipped.
    """
    if existing is None:
        existing = {}

    print("=" * 50)
    print("  Strollopia Org Setup Wizard")
    print("=" * 50)

    config = dict(existing)

    # Resolve the domain for draft saving — needed even when resuming
    draft_domain = org_domain_name or config.get("org_domain_name")

    if start_step > 1:
        print(f"\nResuming from step {start_step}. Completed steps:")
        for s in range(1, start_step):
            print(f"  Step {s}: {STEP_NAMES.get(s, '?')} - done")
        print()

    step_funcs = {
        1: lambda: step_org_identity(defaults, existing, org_domain_name=org_domain_name),
        2: lambda: step_admin(defaults, existing),
        3: lambda: step_map_defaults(existing),
        4: lambda: step_access(defaults, existing),
        5: lambda: step_categories(existing),
        6: lambda: step_media_layouts(defaults, existing),
        7: lambda: step_maps(defaults, existing),
        8: lambda: step_ui_support(defaults, existing),
    }

    try:
        for step_num in range(start_step, 9):
            result = step_funcs[step_num]()
            config.update(result)

            # After step 1, we know the domain name for draft saving
            if step_num == 1:
                draft_domain = config.get("org_domain_name", draft_domain)

            # Save draft after each completed step
            if draft_domain:
                draft_config = dict(config)
                draft_config["_wizard_step"] = step_num
                _save_draft(draft_config, output_dir, draft_domain)

    except (KeyboardInterrupt, EOFError):
        print("\n\nInterrupted.")
        if draft_domain:
            # Save whatever we have so far
            if config.get("org_domain_name") or org_domain_name:
                draft_config = dict(config)
                # _wizard_step tracks last *completed* step; current step was not completed
                # so we keep whatever was saved by the last successful step
                draft = _draft_path(output_dir, draft_domain)
                if os.path.exists(draft):
                    print(f"Draft saved to: {draft}")
                else:
                    # No step completed yet — nothing to save
                    print("No steps were completed. Nothing saved.")
            print(
                f"Resume with: python tools/org_yaml_wizard.py {draft_domain} --resume"
            )
        sys.exit(1)

    return config


def write_org_setup(config, output_dir):
    """Write org-setup.yaml and create directory structure."""
    org_name = config["org_domain_name"]
    org_dir = os.path.join(output_dir, org_name)

    # Create org directory
    os.makedirs(org_dir, exist_ok=True)

    # Create map directories with media subdirs
    for map_name in config.get("org_maps", {}):
        media_dir = os.path.join(org_dir, map_name, "media")
        os.makedirs(media_dir, exist_ok=True)

    # Write YAML
    yaml_path = os.path.join(org_dir, "org-setup.yaml")

    # Strip internal keys
    clean = {k: v for k, v in config.items() if not k.startswith("_")}

    # Order the keys for readability
    ordered = {}
    key_order = [
        "org_domain_name", "viewer", "display_name", "tag_line",
        "main_admin_email", "main_admin_name", "main_admin_password",
        "allows_anonymous", "anonymous_settings", "restrict_public_map",
        "map_default_lat", "map_default_lng",
        "categories", "mediatypes", "layouts", "org_maps", "ui_support",
    ]
    for key in key_order:
        if key in clean:
            ordered[key] = clean[key]
    # Add any remaining keys
    for key in clean:
        if key not in ordered:
            ordered[key] = clean[key]

    with open(yaml_path, "w") as f:
        f.write("---\n")
        yaml.dump(
            ordered,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    return yaml_path


def main():
    parser = argparse.ArgumentParser(
        description="CLI wizard to build org-setup.yaml for Strollopia organizations."
    )
    parser.add_argument(
        "org_domain_name",
        nargs="?",
        help="Org domain name (e.g. myorg.strollopia.com). Required unless --edit is used.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume a previously interrupted wizard run from the draft file",
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
    if not args.edit and not args.org_domain_name:
        parser.error("org_domain_name is required unless --edit is provided")

    if args.resume and not args.org_domain_name:
        parser.error("org_domain_name is required with --resume")

    if args.resume and args.edit:
        parser.error("--resume and --edit cannot be used together")

    # Load defaults
    defaults_path = args.defaults
    if os.path.exists(defaults_path):
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
    else:
        print(f"Warning: defaults file not found at {defaults_path}, using built-in defaults.")
        defaults = {}

    # Determine org_domain_name and existing config
    existing = {}
    org_domain_name = args.org_domain_name
    start_step = 1

    if args.edit:
        # --edit mode: derive domain from existing YAML
        if not os.path.exists(args.edit):
            print(f"Error: file not found: {args.edit}")
            sys.exit(1)
        with open(args.edit) as f:
            existing = yaml.safe_load(f) or {}
        org_domain_name = existing.get("org_domain_name")
        print(f"Loaded existing config from {args.edit}")

    elif args.resume:
        # --resume mode: load draft
        draft_config, last_step = _load_draft(args.output_dir, org_domain_name)
        if draft_config is None or last_step == 0:
            print(f"Error: no draft found for {org_domain_name}")
            print(f"  Expected: {_draft_path(args.output_dir, org_domain_name)}")
            sys.exit(1)
        existing = draft_config
        start_step = last_step + 1
        if start_step > 8:
            print("All steps already completed. Running review step.")
            start_step = 8  # re-run last step to be safe
        print(f"Resuming {org_domain_name} from step {start_step} ({STEP_NAMES.get(start_step, '?')})")

    else:
        # New org: check if directory already exists
        org_dir = os.path.join(args.output_dir, org_domain_name)
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
        org_domain_name=org_domain_name,
        output_dir=args.output_dir,
        start_step=start_step,
    )

    # Step 9: Review & Write
    print("\n=== Step 9: Review & Write ===\n")
    # Show clean config without internal keys
    display = {k: v for k, v in config.items() if not k.startswith("_")}
    print("Generated org-setup.yaml:\n")
    print("---")
    print(yaml.dump(display, default_flow_style=False, sort_keys=False))

    if ask_yes_no("Write this config to disk?", default=True):
        path = write_org_setup(config, args.output_dir)
        print(f"\nWritten to: {path}")

        # Delete draft file on successful write
        _delete_draft(args.output_dir, config["org_domain_name"])

        # List created directories
        org_dir = os.path.join(args.output_dir, config["org_domain_name"])
        print(f"Org directory: {org_dir}")
        for map_name in config.get("org_maps", {}):
            print(f"  Map directory: {os.path.join(org_dir, map_name)}/")
            print(f"    Media: {os.path.join(org_dir, map_name, 'media')}/")

        print("\nDone!")
    else:
        print("Aborted. No files written.")


if __name__ == "__main__":
    main()
