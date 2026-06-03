"""
API client helpers for the Strollopia data import tool.

Provides functions for authentication, org metadata retrieval,
media file upload, and POI creation via the existing REST API.
"""

import os
import mimetypes
import requests


# ── Server targeting ──────────────────────────────────────────────

LOCAL_URL = 'http://127.0.0.1:8000/'
DEV_URL = 'https://dev.strollopia.com/'
PROD_URL = 'https://prod.strollopia.com/'


def get_api_base_url():
    """Return API base URL based on environment variables.

    - USE_LOCAL_HOST=1  → http://127.0.0.1:8000/
    - USE_PROD=1        → https://prod.strollopia.com/
    - default           → https://dev.strollopia.com/
    """
    if os.environ.get('USE_LOCAL_HOST'):
        return LOCAL_URL
    if os.environ.get('USE_PROD'):
        return PROD_URL
    return DEV_URL


def print_api_base_url():
    """Print which server is targeted and how to switch."""
    url = get_api_base_url()
    print(f'API target: {url}')
    print('  To switch:')
    print(f'    local → export USE_LOCAL_HOST=1')
    print(f'    dev   → unset USE_LOCAL_HOST && unset USE_PROD')
    print(f'    prod  → unset USE_LOCAL_HOST && export USE_PROD=1')
    print()


# ── Authentication ────────────────────────────────────────────────

def login(email, password, org_domain_name):
    """Log in and return (token, user_pk) or raise on failure."""
    payload = {
        'email': email,
        'password': password,
        'org_domain_name': org_domain_name,
    }
    resp = requests.post(f'{get_api_base_url()}api/user/login/', json=payload)
    data = resp.json()
    if 'token_key' not in data:
        raise RuntimeError(f'Login failed for {email}: {data}')
    return data['token_key']


def register_user(email, name, password, org_domain_name):
    """Register a user and return (user_pk, token) or (user_pk, None).

    If the user already exists, the API typically returns the user_pk
    without a new token.
    """
    payload = {
        'email': email,
        'name': name,
        'password': password,
        'org_domain_name': org_domain_name,
    }
    resp = requests.post(f'{get_api_base_url()}api/user/register/', json=payload)
    data = resp.json()
    user_pk = data.get('user_pk')
    token = data.get('token_key')
    return user_pk, token


def user_list(token):
    """Return dict mapping email → user_pk for all users in the org."""
    headers = {'Authorization': f'Token {token}'}
    resp = requests.get(f'{get_api_base_url()}api/user/list/', headers=headers)
    if resp.status_code != 200:
        return {}
    result = {}
    for item in resp.json():
        if 'email' in item and 'id' in item:
            result[item['email']] = item['id']
    return result


def logout(token, email, org_domain_name):
    """Clear the API token (logout)."""
    headers = {'Authorization': f'Token {token}'}
    payload = {'email': email, 'org_domain_name': org_domain_name}
    requests.post(f'{get_api_base_url()}api/user/logout/', headers=headers, json=payload)


# ── Org metadata ──────────────────────────────────────────────────

def get_org_policy(org_domain_name):
    """Fetch org policy (maps, settings) from the API."""
    endpoint = f'{get_api_base_url()}api/org/org-policy/?org_domain_name={org_domain_name}'
    resp = requests.get(endpoint)
    resp.raise_for_status()
    return resp.json()


def get_org_categories(org_domain_name):
    """Fetch org categories as nested dict: {cat_name: {subcat_name: pk}}.

    Returns the 'categories' key from the API response.
    """
    endpoint = f'{get_api_base_url()}api/org/categories/?org_domain_name={org_domain_name}&min'
    resp = requests.get(endpoint)
    resp.raise_for_status()
    data = resp.json()
    if 'categories' in data:
        return data['categories']
    raise RuntimeError(f'Unexpected categories response: {data}')


def get_org_layout_fields(org_domain_name):
    """Fetch org layout cards with full field info.

    Returns dict like:
        {'layouts': {'image': [card_pk, {'rt1': ['richtext', 268], 'i1': ['image', 269]}], ...}}

    Each layout name maps to [card_pk, {field_key: [media_type_name, media_type_pk]}].
    """
    endpoint = f'{get_api_base_url()}api/org/layouts/?org_domain_name={org_domain_name}&min&full'
    resp = requests.get(endpoint)
    resp.raise_for_status()
    return resp.json()


# ── Media upload ──────────────────────────────────────────────────

def upload_media_file(file_path, token, is_public=True):
    """Upload a media file (image or audio) and return the MediaFileWrapper PK.

    Uses the single-step POST /api/media/upload/ endpoint.
    """
    filename = os.path.basename(file_path)

    # Strip legacy prefix convention (e.g. "001__002__actual_name.jpg")
    parts = filename.split('__', 2)
    upload_filename = parts[-1] if len(parts) == 3 else filename

    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'

    if content_type.startswith('image/'):
        media_type = 'image'
    elif content_type.startswith('audio/'):
        media_type = 'audio'
    else:
        raise ValueError(f'Unsupported content type for upload: {content_type} ({file_path})')

    headers = {'Authorization': f'Token {token}'}

    with open(file_path, 'rb') as f:
        resp = requests.post(
            f'{get_api_base_url()}api/media/upload/',
            headers=headers,
            data={
                'is_public': 'true' if is_public else 'false',
                'media_type': media_type,
            },
            files={
                'file': (upload_filename, f, content_type),
            },
        )

    resp.raise_for_status()
    data = resp.json()
    if 'id' in data:
        return data['id']
    return data


# ── POI creation ──────────────────────────────────────────────────

def post_poi(poi_geojson, token, org_domain_name):
    """POST a POI GeoJSON feature to the API.

    Returns (success: bool, response_data: dict or str).
    """
    endpoint = f'{get_api_base_url()}api/content/pois/?org_domain_name={org_domain_name}'
    headers = {
        'Authorization': f'Token {token}',
        'Content-Type': 'application/json',
    }
    resp = requests.post(endpoint, json=poi_geojson, headers=headers)
    if resp.status_code == 201:
        return True, resp.json()
    else:
        try:
            error_data = resp.json()
        except Exception:
            error_data = resp.text[:500]
        return False, f'HTTP {resp.status_code}: {error_data}'


def get_map_pois(map_pk, token, org_domain_name):
    """Fetch existing POIs for a map. Used for skip_existing checks."""
    endpoint = f'{get_api_base_url()}api/content/maps/{map_pk}/?org_domain_name={org_domain_name}'
    headers = {'Authorization': f'Token {token}'}
    resp = requests.get(endpoint, headers=headers)
    if resp.status_code != 200:
        return []
    data = resp.json()
    # The map detail endpoint returns pois in the map_json.pois array
    pois = data.get('map_json', {}).get('pois', [])
    return pois
