#!/usr/bin/env python3
"""
Strollopia unified data import tool.

Imports POI data from TSV/CSV files into an already-configured Strollopia org
using the existing REST API. Driven by a schema YAML that maps column headers
to POI fields — replaces all per-org import scripts with one reusable tool.

The tool uses a directory convention where the directory name IS the org map
name, and paths are resolved automatically:

    <map-dir>/import-schema.yaml   → schema
    <map-dir>/map-data.tsv|.csv    → data file
    <map-dir>/media/               → media files
    <map-dir>/../org-setup.yaml    → org credentials + config

Admin credentials (main_admin_email / main_admin_password) can live in
org-setup.yaml, but for real API imports it's safer to pass them on the
command line with --email/--password instead of storing them on disk —
those values override whatever is in the YAML.

Usage:
    # Import a single map
    python strollopia_import.py org-data/kentville.strollopia.com/main-map/

    # Import without storing credentials in org-setup.yaml
    python strollopia_import.py org-data/kentville.strollopia.com/main-map/ \\
        --email admin@example.com --password 'secret'

    # Dry run
    python strollopia_import.py org-data/kentville.strollopia.com/main-map/ --dry-run

    # Validate only
    python strollopia_import.py org-data/kentville.strollopia.com/main-map/ --validate-only

    # Import all maps for an org
    python strollopia_import.py org-data/kentville.strollopia.com/ --all-maps
"""

import argparse
import csv
import getpass
import glob
import logging
import os
import re
import sys
from time import sleep

import yaml

from api_client import (
    ADMIN_ORG_DOMAIN,
    get_api_base_url,
    get_map_pois,
    get_org_categories,
    get_org_layout_fields,
    get_org_policy,
    login,
    logout,
    post_poi,
    print_api_base_url,
    register_user,
    upload_media_file,
    user_list,
)

logger = logging.getLogger('strollopia_import')

DEFAULT_PASSWORD = 'changeme123'
DEFAULT_USER_NAME = 'Imported User'


# ── Directory convention helpers ─────────────────────────────────

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


# ── Schema + data loading ─────────────────────────────────────────

def load_schema(path):
    """Load and return a schema YAML file."""
    with open(path, 'r') as f:
        schema = yaml.safe_load(f)
    return schema


def load_org_credentials(path, email_override=None, password_override=None):
    """Load org credentials YAML (org_domain_name, main_admin_email, main_admin_password).

    email_override / password_override take precedence over whatever is in the
    YAML, so credentials can be supplied on the command line instead of being
    stored in org-setup.yaml.
    """
    with open(path, 'r') as f:
        creds = yaml.safe_load(f)

    if email_override:
        creds['main_admin_email'] = email_override
    if password_override:
        creds['main_admin_password'] = password_override

    required = ['org_domain_name', 'main_admin_email', 'main_admin_password']
    for key in required:
        if not creds.get(key):
            raise ValueError(
                f'Missing required key "{key}" in org credentials: {path} '
                f'(supply --email/--password to avoid storing it in the YAML)')
    return creds


def load_data(path, delimiter='\t'):
    """Load a TSV/CSV file and return (headers, rows) where rows is a list of dicts."""
    with open(path, 'r', newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


# ── Validation ────────────────────────────────────────────────────

def collect_schema_columns(schema):
    """Collect all column header names referenced in the schema."""
    columns = set()

    # card_layout_column
    if 'card_layout_column' in schema:
        columns.add(schema['card_layout_column'])

    # poi_fields
    for field_name, col in schema.get('poi_fields', {}).items():
        if col is not None:
            columns.add(col)

    # user_fields
    for field_name, col in schema.get('user_fields', {}).items():
        if col is not None:
            columns.add(col)

    # schedule
    for day, col in schema.get('schedule', {}).items():
        if col is not None:
            columns.add(col)

    # categories
    for field_name, col in schema.get('categories', {}).items():
        if col is not None:
            columns.add(col)

    # content_columns
    for field_key, mapping in schema.get('content_columns', {}).items():
        if isinstance(mapping, dict) and 'column' in mapping:
            columns.add(mapping['column'])

    return columns


def validate_schema_vs_data(schema, headers):
    """Check that all schema-referenced columns exist in the data headers.

    Returns a list of error strings (empty means valid).
    """
    errors = []
    schema_columns = collect_schema_columns(schema)
    header_set = set(headers)

    for col in sorted(schema_columns):
        if col not in header_set:
            errors.append(f'Schema references column "{col}" but it is not in the data headers.')

    return errors


# ── Org metadata helpers ──────────────────────────────────────────

def get_map_pk_from_policy(org_policy, org_map_name):
    """Look up a map PK from org policy by org_map_name."""
    for m in org_policy.get('public_org_maps', []):
        if m.get('org_map_name') == org_map_name:
            return m.get('map_obj')
    return None


def get_layout_card_info(org_layouts, layout_name):
    """Look up layout card [pk, field_dict] from org layouts by name.

    Returns (card_pk, layout_field_dict) or (None, None).
    layout_field_dict is like: {'rt1': ['richtext', 268], 'i1': ['image', 269]}
    """
    layouts = org_layouts.get('layouts', {})
    card_info = layouts.get(layout_name)
    if card_info is None:
        return None, None
    # card_info is [card_pk, {field_key: [media_type_name, media_type_pk]}]
    return card_info[0], card_info[1]


def resolve_subcat_ids(row, schema, org_categories):
    """Resolve subcategory PKs for a row from the org categories dict."""
    cats_schema = schema.get('categories')
    if not cats_schema:
        return []

    cat_col = cats_schema.get('category')
    subcat_col = cats_schema.get('subcategory')
    if not cat_col or not subcat_col:
        return []

    cat_name = row.get(cat_col, '').strip()
    subcat_name = row.get(subcat_col, '').strip()
    if not cat_name or not subcat_name:
        return []

    subcat_pk = org_categories.get(cat_name, {}).get(subcat_name)
    if subcat_pk is not None:
        return [subcat_pk]

    logger.warning(f'No subcategory PK found for category="{cat_name}", subcategory="{subcat_name}"')
    return []


# ── Open hours ────────────────────────────────────────────────────

def parse_open_hours(row, schema):
    """Parse schedule columns into open_hours array.

    Expects format like "F: 09:00 T: 17:00" or "closed".
    """
    schedule_schema = schema.get('schedule')
    if not schedule_schema:
        return None

    open_hours = []
    for day_key, col in schedule_schema.items():
        if col is None:
            continue
        value = row.get(col, '').strip()
        if not value or value.lower() == 'closed':
            continue

        # Parse "F: HH:MM T: HH:MM" format
        components = value.split()
        if len(components) >= 4:
            day_payload = {
                'day_of_week': day_key.capitalize(),
                'open_time': components[1],
                'close_time': components[3],
            }
            open_hours.append(day_payload)
        else:
            logger.warning(f'Invalid open hours format for {day_key}: "{value}"')

    return open_hours if open_hours else None


# ── Slug generation ───────────────────────────────────────────────

def generate_slug(name):
    """Generate a URL-safe slug from a POI name."""
    slug = name.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug[:200]


# ── User handling ─────────────────────────────────────────────────

def find_or_create_user(row, schema, org_domain_name, email_to_pk, token):
    """Create or look up a user for this row. Returns (email, user_pk) or (None, None)."""
    user_schema = schema.get('user_fields')
    if not user_schema:
        return None, None

    email_col = user_schema.get('email')
    if not email_col:
        return None, None

    email = row.get(email_col, '').strip()
    if not email:
        return None, None

    # Already known?
    if email in email_to_pk:
        return email, email_to_pk[email]

    # Build name
    name_first = row.get(user_schema.get('name_first', ''), '').strip()
    name_last = row.get(user_schema.get('name_last', ''), '').strip()
    name = f'{name_first} {name_last}'.strip() or DEFAULT_USER_NAME

    password = DEFAULT_PASSWORD

    user_pk, user_token = register_user(
        email=email,
        name=name,
        password=password,
        org_domain_name=org_domain_name,
    )

    # Logout the newly created user token so it doesn't stay active
    if user_token:
        logout(user_token, email, org_domain_name)

    if user_pk:
        email_to_pk[email] = user_pk

    return email, user_pk


# ── Content block building ────────────────────────────────────────

def build_content_wrapper(field_key, media_type_name, media_type_pk, value,
                          base_path=None, token=None, schema_mapping=None):
    """Build a single PoiContentWrapper dict for a layout field.

    Dispatches based on media_type_name (richtext, simple_richtext, image, audio, chat).
    """
    wrapper = {
        'reactive': 0,
        'media_type': media_type_pk,
        'media_file': None,
        'field_key': field_key,
        'file_key': '',
        'caption': '',
        'rich_text_content': '',
    }

    if media_type_name in ('richtext', 'rich_text'):
        wrapper['rich_text_content'] = value if value else ''

    elif media_type_name == 'simple_richtext':
        wrapper['rich_text_content'] = value if value else ''

    elif media_type_name == 'chat':
        wrapper['rich_text_content'] = value if value else ''

    elif media_type_name == 'image':
        if value and value.strip():
            file_path = os.path.join(base_path, value.strip()) if base_path else value.strip()
            if os.path.isfile(file_path):
                media_pk = upload_media_file(file_path, token, is_public=True)
                wrapper['media_file_w'] = media_pk
                wrapper['is_public'] = True
                logger.info(f'  Uploaded image: {file_path} -> PK {media_pk}')
            else:
                logger.warning(f'  Image file not found: {file_path}')

    elif media_type_name == 'audio':
        if value and value.strip():
            file_path = os.path.join(base_path, value.strip()) if base_path else value.strip()
            if os.path.isfile(file_path):
                media_pk = upload_media_file(file_path, token, is_public=True)
                wrapper['media_file_w'] = media_pk
                wrapper['is_public'] = True
                logger.info(f'  Uploaded audio: {file_path} -> PK {media_pk}')
            else:
                logger.warning(f'  Audio file not found: {file_path}')

    else:
        logger.warning(f'  Unsupported media type: {media_type_name} for field_key: {field_key}')

    return wrapper


def build_richtext_from_schema(row, schema_mapping):
    """Build rich text HTML from a content_columns mapping that has sub-fields.

    Supports mappings with 'blurb_column' and 'condition_column' for simple_richtext,
    or mappings with address/phone/url sub-fields for full richtext.
    """
    parts = []

    # Simple richtext: blurb + condition
    if 'blurb_column' in schema_mapping:
        blurb = row.get(schema_mapping.get('blurb_column', ''), '').strip()
        condition = row.get(schema_mapping.get('condition_column', ''), '').strip()
        if condition:
            parts.append(f'<p><b>Item Condition:</b> {condition}</p>')
        if blurb:
            blurb_html = blurb.replace('\n', '<br>')
            parts.append(f'<p>{blurb_html}</p>')
        return ''.join(parts) if parts else '<p></p>'

    # Full richtext with address, phone, url, blurb
    blurb_col = schema_mapping.get('blurb_column')
    if blurb_col:
        blurb = row.get(blurb_col, '').strip()
        if blurb:
            parts.append(f'<p>{blurb}</p>')

    phone_col = schema_mapping.get('phone_column')
    if phone_col:
        phone = row.get(phone_col, '').strip()
        if phone:
            parts.append(f'<p>Phone: {phone}</p>')

    url_col = schema_mapping.get('url_column')
    if url_col:
        url = row.get(url_col, '').strip()
        if url:
            parts.append(f'<p>URL: {url}</p>')

    street_col = schema_mapping.get('address_street_column')
    community_col = schema_mapping.get('address_community_column')
    if street_col or community_col:
        street = row.get(street_col, '').strip() if street_col else ''
        community = row.get(community_col, '').strip() if community_col else ''
        addr_parts = [p for p in [street, community] if p]
        if addr_parts:
            parts.append(f'<p>Address: {", ".join(addr_parts)}</p>')

    return ''.join(parts) if parts else '<p></p>'


def build_content_block(row, schema, layout_card_pk, layout_fields, media_dir, token):
    """Build the full content_block array for a POI.

    layout_fields is {field_key: [media_type_name, media_type_pk]}.
    media_dir is the resolved media directory path for this map.
    """
    content_columns = schema.get('content_columns', {})
    options = schema.get('options', {})
    language = options.get('language', 'en')

    content_array = []

    for field_key, (media_type_name, media_type_pk) in layout_fields.items():
        mapping = content_columns.get(field_key)
        if mapping is None:
            logger.debug(f'  No content_columns mapping for field_key "{field_key}", skipping.')
            continue

        if isinstance(mapping, dict):
            column = mapping.get('column', '')
            # base_path is always the map's media/ directory
            base_path = media_dir

            # Handle simple_richtext with blurb+condition columns
            if 'blurb_column' in mapping or 'condition_column' in mapping:
                value = build_richtext_from_schema(row, mapping)
            else:
                value = row.get(column, '').strip() if column else ''

            # For richtext media types, wrap plain text in <p> if needed
            if media_type_name in ('richtext', 'rich_text') and value and not value.startswith('<'):
                value = f'<p>{value}</p>'

            wrapper = build_content_wrapper(
                field_key=field_key,
                media_type_name=media_type_name,
                media_type_pk=media_type_pk,
                value=value,
                base_path=base_path,
                token=token,
                schema_mapping=mapping,
            )
            content_array.append(wrapper)
        else:
            # Simple string — just a column name
            value = row.get(mapping, '').strip() if mapping else ''
            if media_type_name in ('richtext', 'rich_text') and value and not value.startswith('<'):
                value = f'<p>{value}</p>'
            wrapper = build_content_wrapper(
                field_key=field_key,
                media_type_name=media_type_name,
                media_type_pk=media_type_pk,
                value=value,
                base_path=media_dir,
                token=token,
            )
            content_array.append(wrapper)

    content_block = [{
        'language': language,
        'layout_card': layout_card_pk,
        'user_layout_card': None,
        'social_media_blurb': '',
        'content_array': content_array,
    }]

    return content_block


# ── POI GeoJSON assembly ─────────────────────────────────────────

def build_poi_geojson(row, schema, map_pk, layout_card_pk, layout_fields,
                      subcat_ids, open_hours, user_pk, media_dir, token):
    """Assemble a complete POI GeoJSON Feature dict ready for POST."""
    poi_fields = schema.get('poi_fields', {})

    name = row.get(poi_fields.get('name', ''), '').strip()
    lat = row.get(poi_fields.get('lat', ''), '')
    lng = row.get(poi_fields.get('lng', ''), '')

    slug_col = poi_fields.get('slug')
    if slug_col:
        slug = row.get(slug_col, '').strip()
    else:
        slug = ''
    if not slug:
        slug = generate_slug(name)

    geometry = {
        'type': 'Point',
        'coordinates': [float(lng), float(lat)],
    }

    properties = {
        'owning_map': int(map_pk),
        'map_content': False,
        'name': name,
        'slug': slug,
        'allowed_viewers': [],
        'allowed_editors': [int(user_pk)] if user_pk else [],
        'allowed_admins': [],
        'generic_bool_00': False,
        'generic_int_00': 0,
        'generic_int_01': 0,
        'generic_int_02': 0,
        'sub_categories': subcat_ids,
    }

    if open_hours:
        properties['open_hours'] = open_hours

    properties['content_block'] = build_content_block(
        row=row,
        schema=schema,
        layout_card_pk=layout_card_pk,
        layout_fields=layout_fields,
        media_dir=media_dir,
        token=token,
    )

    return {
        'type': 'Feature',
        'geometry': geometry,
        'properties': properties,
    }


# ── Main import loop ─────────────────────────────────────────────

def resolve_layout_card(row, schema, org_layouts):
    """Resolve the layout card PK and field dict for a row."""
    if 'card_layout' in schema:
        layout_name = schema['card_layout']
    elif 'card_layout_column' in schema:
        layout_name = row.get(schema['card_layout_column'], '').strip()
    else:
        raise ValueError('Schema must define card_layout or card_layout_column')

    card_pk, layout_fields = get_layout_card_info(org_layouts, layout_name)
    if card_pk is None:
        raise ValueError(f'No layout card found for name="{layout_name}"')
    return card_pk, layout_fields


def get_existing_poi_names(map_pk, token, org_domain_name):
    """Fetch existing POI names for a map (for skip_existing)."""
    pois = get_map_pois(map_pk, token, org_domain_name)
    names = set()
    for poi in pois:
        props = poi.get('properties', {})
        name = props.get('name', '')
        if name:
            names.add(name.strip().lower())
    return names


def run_import(org_creds, schema, headers, rows, map_name, media_dir,
               dry_run=False, super_admin=False):
    """Execute the import process for a single map.

    Login's org_domain_name must identify the org the acting user belongs
    to, not the org being written to. For a normal org-level admin those
    are the same org, so no override is needed. For a Django superuser
    (super_admin=True) the user's org is always ADMIN_ORG_DOMAIN, so the
    login call uses that while every other API call (maps, categories,
    layouts, POIs) still targets the org actually being imported into.
    """
    org_domain_name = org_creds['org_domain_name']
    login_org_domain = ADMIN_ORG_DOMAIN if super_admin else org_domain_name
    options = schema.get('options', {})
    skip_existing = options.get('skip_existing', True)
    sleep_between = options.get('sleep_between_rows', 2)

    # Authenticate
    logger.info(f'Logging in as {org_creds["main_admin_email"]} '
                f'(org_domain_name={login_org_domain})...')
    token = login(
        email=org_creds['main_admin_email'],
        password=org_creds['main_admin_password'],
        org_domain_name=login_org_domain,
    )
    logger.info('Login successful.')

    # Fetch org metadata
    logger.info('Fetching org metadata...')
    org_policy = get_org_policy(org_domain_name)
    org_categories = get_org_categories(org_domain_name)
    org_layouts = get_org_layout_fields(org_domain_name)
    email_to_pk = user_list(token)

    logger.info(f'  Maps: {[m["org_map_name"] for m in org_policy.get("public_org_maps", [])]}')
    logger.info(f'  Categories: {list(org_categories.keys())}')
    logger.info(f'  Layout cards: {list(org_layouts.get("layouts", {}).keys())}')
    logger.info(f'  Known users: {len(email_to_pk)}')

    # Resolve map PK from directory name
    map_pk = get_map_pk_from_policy(org_policy, map_name)
    if map_pk is None:
        raise ValueError(
            f'No map found for org_map_name="{map_name}" in org policy. '
            f'Available maps: {[m["org_map_name"] for m in org_policy.get("public_org_maps", [])]}')
    logger.info(f'  Target map: {map_name} (PK {map_pk})')

    # Build cache of existing POI names (for skip_existing)
    existing_names = set()
    if skip_existing:
        existing_names = get_existing_poi_names(map_pk, token, org_domain_name)

    # Process rows
    total = len(rows)
    success_count = 0
    skip_count = 0
    error_count = 0
    errors = []

    for i, row in enumerate(rows):
        row_num = i + 2  # 1-indexed, accounting for header
        poi_name = row.get(schema.get('poi_fields', {}).get('name', ''), '').strip()
        logger.info(f'Row {row_num}/{total + 1}: "{poi_name}"')

        try:
            # Skip existing check
            if skip_existing:
                if poi_name.strip().lower() in existing_names:
                    logger.info(f'  SKIP: POI "{poi_name}" already exists on map {map_pk}')
                    skip_count += 1
                    continue

            # Resolve layout card
            card_pk, layout_fields = resolve_layout_card(row, schema, org_layouts)

            # Resolve categories
            subcat_ids = resolve_subcat_ids(row, schema, org_categories)

            # Handle user creation
            user_email, user_pk = find_or_create_user(
                row, schema, org_domain_name, email_to_pk, token)

            # Parse open hours
            open_hours = parse_open_hours(row, schema)

            # Build POI GeoJSON
            poi_geojson = build_poi_geojson(
                row=row,
                schema=schema,
                map_pk=map_pk,
                layout_card_pk=card_pk,
                layout_fields=layout_fields,
                subcat_ids=subcat_ids,
                open_hours=open_hours,
                user_pk=user_pk,
                media_dir=media_dir,
                token=token,
            )

            if dry_run:
                import json
                logger.info(f'  DRY RUN — would POST:')
                print(json.dumps(poi_geojson, indent=2))
                success_count += 1
                continue

            # POST to API
            ok, resp_data = post_poi(poi_geojson, token, org_domain_name)
            if ok:
                logger.info(f'  SUCCESS: POI "{poi_name}" created.')
                success_count += 1
                # Add to existing names cache
                existing_names.add(poi_name.strip().lower())
            else:
                logger.error(f'  FAILED: {resp_data}')
                error_count += 1
                errors.append((row_num, poi_name, resp_data))

            if sleep_between and i < total - 1:
                sleep(sleep_between)

        except Exception as e:
            logger.error(f'  ERROR at row {row_num}: {e}')
            error_count += 1
            errors.append((row_num, poi_name, str(e)))
            continue

    # Summary
    logger.info('')
    logger.info('=' * 60)
    logger.info('IMPORT SUMMARY')
    logger.info(f'  Map:         {map_name}')
    logger.info(f'  Total rows:  {total}')
    logger.info(f'  Succeeded:   {success_count}')
    logger.info(f'  Skipped:     {skip_count}')
    logger.info(f'  Errors:      {error_count}')
    if errors:
        logger.info('')
        logger.info('ERRORS:')
        for row_num, name, err in errors:
            logger.info(f'  Row {row_num} ("{name}"): {err}')
    logger.info('=' * 60)

    return error_count == 0


# ── CLI ──────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Strollopia unified data import tool.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import a single map (directory convention)
  python strollopia_import.py org-data/kentville.strollopia.com/main-map/

  # Import all maps for an org
  python strollopia_import.py org-data/kentville.strollopia.com/ --all-maps

  # Dry run (build payloads without posting)
  python strollopia_import.py org-data/kentville.strollopia.com/main-map/ --dry-run

  # Validate schema against data file columns
  python strollopia_import.py org-data/kentville.strollopia.com/main-map/ --validate-only

  # Explicit paths (override directory convention)
  python strollopia_import.py org-data/kentville.strollopia.com/main-map/ \\
      --schema custom-schema.yaml --data custom-data.tsv

  # Pass admin credentials on the command line instead of org-setup.yaml
  python strollopia_import.py org-data/kentville.strollopia.com/main-map/ \\
      --email admin@example.com --password 'secret'

  # Same, but get prompted for the password instead of typing it inline
  python strollopia_import.py org-data/kentville.strollopia.com/main-map/ \\
      --email admin@example.com

Environment variables:
  USE_LOCAL_HOST=1   Target local dev server (http://127.0.0.1:8000/)
  USE_PROD=1         Target production (https://prod.strollopia.com/)
  (default)          Target dev (https://dev.strollopia.com/)
""",
    )

    parser.add_argument(
        'map_dir',
        help='Map directory (or org directory with --all-maps). '
             'Convention: <map-dir>/import-schema.yaml, map-data.tsv, media/',
    )
    parser.add_argument(
        '--all-maps', action='store_true',
        help='Treat map_dir as an org directory and import all maps within it',
    )
    parser.add_argument(
        '--schema',
        help='Override: path to schema YAML (default: <map-dir>/import-schema.yaml)',
    )
    parser.add_argument(
        '--data',
        help='Override: path to data file (default: <map-dir>/map-data.tsv|.csv)',
    )
    parser.add_argument(
        '--org-credentials',
        help='Override: path to org-setup YAML (default: <map-dir>/../org-setup.yaml)',
    )
    parser.add_argument(
        '--email',
        help='Admin email to log in with. Overrides main_admin_email in org-setup.yaml '
             '(use this instead of storing credentials in the YAML).',
    )
    parser.add_argument(
        '--password',
        help='Admin password to log in with. Overrides main_admin_password in '
             'org-setup.yaml. If omitted and --email is given without this flag, '
             'you will be prompted (avoids leaking the password via shell history).',
    )
    parser.add_argument(
        '--super-admin', action='store_true',
        help="Log in as a Django superuser instead of an org-level admin. "
             "The org_domain_name on login must always be the org the "
             f"acting user belongs to — for a superuser that's the default "
             f"org ('{ADMIN_ORG_DOMAIN}'), never the org being imported "
             "into. This flag makes the login call use that instead of the "
             "target org's domain. Only affects login — map/category/POI "
             "calls still target the org from org-setup.yaml, since that's "
             "the org actually being written to.",
    )
    parser.add_argument(
        '--delimiter', default=None,
        choices=['tab', 'comma'],
        help='Override data file delimiter (default: auto-detect from extension)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Build payloads and print them without posting to the API',
    )
    parser.add_argument(
        '--validate-only', action='store_true',
        help='Only validate that schema columns match data headers, then exit',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Enable debug logging',
    )

    return parser.parse_args(argv)


def import_single_map(map_dir, args, schema_override=None):
    """Run import for a single map directory. Returns 0 on success, 1 on error."""
    paths = resolve_map_dir_paths(map_dir, schema_path=schema_override)
    map_name = paths['map_name']

    # Apply overrides
    schema_path = args.schema or paths['schema']
    data_path = args.data or paths['data']
    org_creds_path = args.org_credentials or paths['org_credentials']
    media_dir = paths['media_dir']

    if args.delimiter:
        delimiter = '\t' if args.delimiter == 'tab' else ','
    else:
        delimiter = paths['delimiter']

    logger.info(f'Map directory: {map_dir}')
    logger.info(f'Map name:      {map_name}')
    logger.info(f'Schema:        {schema_path}')
    logger.info(f'Data:          {data_path}')
    logger.info(f'Media:         {media_dir}')
    logger.info(f'Org setup:     {org_creds_path}')
    logger.info('')

    # Load schema and data
    schema = load_schema(schema_path)
    headers, rows = load_data(data_path, delimiter=delimiter)
    logger.info(f'  {len(headers)} columns, {len(rows)} data rows')

    # Validate
    validation_errors = validate_schema_vs_data(schema, headers)
    if validation_errors:
        logger.error('Schema validation errors:')
        for err in validation_errors:
            logger.error(f'  {err}')
        logger.error('')
        logger.error(f'Data columns: {headers}')
        return 1

    logger.info('Schema validation passed.')

    if args.validate_only:
        logger.info('--validate-only: schema columns all found in data headers.')
        logger.info(f'Schema columns: {sorted(collect_schema_columns(schema))}')
        logger.info(f'Data columns:   {headers}')
        return 0

    # Load org credentials — CLI-supplied email/password take precedence over
    # the YAML so admin credentials don't need to be stored on disk.
    password = args.password
    if args.email and not password and not args.dry_run:
        password = getpass.getpass(f'Password for {args.email}: ')

    org_creds = load_org_credentials(
        org_creds_path,
        email_override=args.email,
        password_override=password,
    )
    logger.info(f'Org: {org_creds["org_domain_name"]}')

    success = run_import(
        org_creds=org_creds,
        schema=schema,
        headers=headers,
        rows=rows,
        map_name=map_name,
        media_dir=media_dir,
        dry_run=args.dry_run,
        super_admin=args.super_admin,
    )

    return 0 if success else 1


def main(argv=None):
    args = parse_args(argv)

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%H:%M:%S',
    )

    print_api_base_url()

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


if __name__ == '__main__':
    sys.exit(main())
