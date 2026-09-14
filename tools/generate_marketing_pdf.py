#!/usr/bin/env python3
"""Generate a one-page marketing PDF for a provisioned town: a pitch page
with a QR code to the live site, and a getting-started page with login
instructions.

Standalone and rerunnable -- reads already-captured org data (org-setup.yaml,
main-map/map-data.en.tsv, main-map/media/, org-setup.secrets.yaml), makes no
Google/OSM/API calls, so the visual design can be iterated on (run, tweak
the template below, run again) without re-touching discovery or import.

Usage:
    python tools/generate_marketing_pdf.py ca-nova-scotia-new-minas
    python tools/generate_marketing_pdf.py ca-nova-scotia-new-minas --output-dir org-data
"""
import argparse
import base64
import csv
import io
import os
import sys

import qrcode
from weasyprint import HTML

from post_org_setup import load_org_config

CATEGORY_LABELS = {
    "Business": "businesses",
    "Landmark": "landmarks",
    "Art": "public art",
    "Nature": "parks & nature",
}

# A single shared illustrative screenshot (not per-org - no town has GA data
# of its own yet, since it's opt-in and none has set it up) showing what a
# Google Analytics dashboard looks like, for the "Want to see who's
# visiting?" callout on the Getting Started page. Optional by design: the
# callout still renders (as text only) if this file isn't present, so the
# tool keeps working before/without this asset - drop a PNG/JPG here and
# regenerate to pick it up, no code change needed.
GA_SCREENSHOT_PATH = os.path.join(
    os.path.dirname(__file__), "assets", "ga-dashboard-example.png"
)


def load_poi_counts(tsv_path):
    """Return {category: count}, sorted most-common first."""
    counts = {}
    with open(tsv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            cat = row.get("category") or "Other"
            counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def pick_sample_pois(tsv_path, media_dir, limit=3):
    """Pick up to `limit` POIs to showcase.

    Prefers rows with both a photo and a description, and tries to cover
    distinct categories before repeating one, so the sample doesn't end up
    as 3 cafes.
    """
    with open(tsv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))

    def has_photo(row):
        image_file = row.get("image_file")
        return bool(image_file) and os.path.exists(os.path.join(media_dir, image_file))

    candidates = [r for r in rows if has_photo(r) and r.get("description")]

    picked = []
    seen_categories = set()
    for row in candidates:
        if row["category"] not in seen_categories:
            picked.append(row)
            seen_categories.add(row["category"])
        if len(picked) == limit:
            break
    for row in candidates:
        if len(picked) == limit:
            break
        if row not in picked:
            picked.append(row)

    return picked[:limit]


def qr_data_uri(url):
    """Render a QR code for `url` as an inline base64 PNG data URI."""
    img = qrcode.make(url, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _render_ga_screenshot():
    """
    An <img> tag for GA_SCREENSHOT_PATH, base64-embedded (not a relative
    <img src>) so it works regardless of org_dir - the shared asset lives
    outside any org's directory, unlike the per-org sample-card photos,
    which is exactly the path-resolution mistake that made those silently
    fail to render before (see build_html's media_dir_rel comment).
    Returns "" if the screenshot doesn't exist yet, so this callout still
    renders as text-only rather than breaking the whole page.
    """
    if not os.path.exists(GA_SCREENSHOT_PATH):
        return ""
    with open(GA_SCREENSHOT_PATH, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    ext = os.path.splitext(GA_SCREENSHOT_PATH)[1].lstrip(".").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    return f'<img src="data:image/{mime};base64,{b64}" alt="Example Google Analytics dashboard">'


def _render_stat_strip(counts):
    if not counts:
        return ""
    cells = []
    for cat, count in counts.items():
        label = CATEGORY_LABELS.get(cat, cat.lower())
        cells.append(
            f'<div class="stat"><div class="stat-num">{count}</div>'
            f'<div class="stat-label">{label}</div></div>'
        )
    return '<div class="stat-strip">' + "".join(cells) + "</div>"


def _summary_only(description):
    """Extract just the "name — summary" opening line from
    city_discover.build_description's HTML, dropping the address/phone/
    website lines below it -- those are operational detail, not pitch copy.
    """
    first_line = description.split("<br>")[0]
    if " — " in first_line:
        return first_line.split(" — ", 1)[1]
    return ""


def _render_sample_cards(samples, media_dir):
    if not samples:
        return ""
    cards = []
    for row in samples:
        image_path = os.path.join(media_dir, row["image_file"])
        summary = _summary_only(row["description"])
        summary_html = f'<div class="poi-card-desc">{summary}</div>' if summary else ""
        cards.append(f"""
          <div class="poi-card">
            <img src="{image_path}" alt="{row['name']}">
            <div class="poi-card-body">
              <h3>{row['name']}</h3>
              {summary_html}
            </div>
          </div>
        """)
    return '<div class="poi-cards">' + "".join(cards) + "</div>"


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{ size: Letter; margin: 0.75in; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "DejaVu Sans", Helvetica, Arial, sans-serif;
    color: #26332f;
    margin: 0;
  }}
  h1, h2, h3 {{
    font-family: "DejaVu Serif", Georgia, serif;
    margin: 0 0 0.15em 0;
    color: #163634;
  }}
  .brand {{
    font-size: 11pt;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #4f8f89;
    font-weight: bold;
    margin-bottom: 0.6em;
  }}
  .hero h1 {{ font-size: 30pt; }}
  .hero .tagline {{ font-size: 13pt; color: #4a5a56; margin-bottom: 1.1em; }}

  .stat-strip {{
    display: flex;
    gap: 0.4in;
    margin: 0.3in 0 0.4in 0;
    padding: 0.2in 0;
    border-top: 1px solid #d8e3e0;
    border-bottom: 1px solid #d8e3e0;
  }}
  .stat-num {{ font-family: "DejaVu Serif", Georgia, serif; font-size: 22pt; color: #163634; }}
  .stat-label {{ font-size: 9.5pt; color: #5b6d68; text-transform: uppercase; letter-spacing: 0.05em; }}

  .section-heading {{
    font-size: 13pt;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #4f8f89;
    margin: 0.3in 0 0.15in 0;
  }}

  .poi-cards {{ display: flex; gap: 0.25in; }}
  .poi-card {{
    flex: 1;
    border: 1px solid #d8e3e0;
    border-radius: 6px;
    overflow: hidden;
  }}
  .poi-card img {{ width: 100%; height: 1.3in; object-fit: cover; display: block; }}
  .poi-card-body {{ padding: 0.12in; }}
  .poi-card-body h3 {{ font-size: 11pt; }}
  .poi-card-desc {{ font-size: 8.5pt; color: #4a5a56; line-height: 1.35; }}

  .cta {{
    margin-top: 0.45in;
    padding: 0.3in;
    background: #eef4f3;
    border-radius: 8px;
    display: flex;
    align-items: center;
    gap: 0.3in;
  }}
  .cta img {{ width: 1.4in; height: 1.4in; }}
  .cta-text h2 {{ font-size: 15pt; margin-bottom: 0.08in; }}
  .cta-text .url {{ font-size: 10.5pt; color: #4f8f89; font-weight: bold; }}
  .cta-text p {{ font-size: 9.5pt; color: #4a5a56; margin: 0.08in 0 0 0; }}

  .page-break {{ page-break-before: always; }}
  .credentials {{
    margin-top: 0.3in;
    padding: 0.3in;
    background: #eef4f3;
    border-radius: 8px;
    font-size: 11pt;
  }}
  .credentials .row {{ margin: 0.1in 0; }}
  .credentials .label {{ color: #5b6d68; font-size: 9pt; text-transform: uppercase; letter-spacing: 0.05em; }}
  .credentials .value {{ font-family: "DejaVu Sans Mono", monospace; font-size: 12pt; color: #163634; }}
  .instructions {{ margin-top: 0.35in; font-size: 10.5pt; color: #3a4643; line-height: 1.5; }}

  .analytics-callout {{
    margin-top: 0.35in;
    padding: 0.3in;
    background: #eef4f3;
    border-radius: 8px;
    page-break-inside: avoid;
    break-inside: avoid;
  }}
  .analytics-callout h2 {{ font-size: 13pt; margin-bottom: 0.1in; }}
  .analytics-callout p {{ font-size: 10pt; color: #3a4643; line-height: 1.5; margin: 0 0 0.15in 0; }}
  .analytics-callout img {{
    display: block;
    max-width: 100%;
    max-height: 2.4in;
    border-radius: 6px;
    border: 1px solid #d8e3e0;
    margin-top: 0.1in;
  }}
</style>
</head>
<body>

  <div class="brand">Strollopia</div>
  <div class="hero">
    <h1>{display_name}</h1>
    <div class="tagline">{tag_line}</div>
  </div>

  {stat_strip}

  <div class="section-heading">Already live and ready to explore</div>
  {sample_cards}

  <div class="cta">
    <img src="{qr_data_uri}" alt="QR code">
    <div class="cta-text">
      <h2>See it for yourself</h2>
      <div class="url">{site_url}</div>
      <p>Scan the code or visit the link above to explore {display_name}'s
      interactive map -- no app to install, works on any phone.</p>
    </div>
  </div>

  <div class="page-break"></div>

  <div class="brand">Strollopia</div>
  <h1>Getting Started</h1>
  <p class="tagline">Your {display_name} admin account is ready.</p>

  <div class="credentials">
    <div class="row"><div class="label">Admin login</div>
      <div class="value">{site_url}/admin.html</div></div>
    <div class="row"><div class="label">Email</div>
      <div class="value">{admin_email}</div></div>
    <div class="row"><div class="label">Password</div>
      <div class="value">{admin_password}</div></div>
  </div>

  <div class="instructions">
    <p><b>Please log in and set a new password right away</b> -- from your
    admin panel you can edit any of this content, add or update listings,
    change photos, and invite others to help manage the site.</p>
  </div>

  <div class="analytics-callout">
    <h2>Want to see who's visiting?</h2>
    <p>Every point on your map already tracks views right in your admin
    panel's Stats view -- no setup required. Want richer reporting (traffic
    sources, device types, time on page)? Add your own free Google
    Analytics ID under Organization settings, and Strollopia sends your
    visitor data there automatically.</p>
    {ga_screenshot_html}
  </div>

</body>
</html>
"""


def build_html(org_dir, config):
    """Build the marketing page's HTML from an org's already-captured data."""
    map_dir = os.path.join(org_dir, "main-map")
    tsv_path = os.path.join(map_dir, "map-data.en.tsv")
    media_dir = os.path.join(map_dir, "media")
    # generate_marketing_pdf() renders with base_url=org_dir, so an <img src>
    # needs to be relative to org_dir - NOT the same media_dir used above,
    # which already has org_dir baked in (it's built from org_dir + "main-map"
    # + "media" so pick_sample_pois' has_photo() check can open the file
    # directly from the CWD). Using media_dir for the src too double-prefixes
    # org_dir when weasyprint resolves the relative URL against base_url,
    # so every image silently 404s (write_pdf() doesn't raise on a missing
    # image - it just renders a blank box, which is why this went unnoticed).
    media_dir_rel = os.path.join("main-map", "media")

    counts = load_poi_counts(tsv_path)
    samples = pick_sample_pois(tsv_path, media_dir)
    site_url = f"https://{config['org_domain_name']}"
    # /qr-map/ is a strollopia-sites _redirects rule (302 to the site root)
    # that exists purely so Cloudflare Pages' own per-path analytics can
    # report QR-driven scans separately from organic visits - the printed
    # QR code encodes this path, but the human-readable URL text below it
    # stays the clean root address, since nobody should have to type
    # "/qr-map/" by hand.
    qr_url = f"{site_url}/qr-map/"

    return HTML_TEMPLATE.format(
        display_name=config.get("display_name", config["org_domain_name"]),
        tag_line=config.get("tag_line", ""),
        stat_strip=_render_stat_strip(counts),
        sample_cards=_render_sample_cards(samples, media_dir_rel),
        qr_data_uri=qr_data_uri(qr_url),
        site_url=site_url,
        admin_email=config.get("main_admin_email", ""),
        admin_password=config.get("main_admin_password", ""),
        ga_screenshot_html=_render_ga_screenshot(),
    )


def generate_marketing_pdf(org_dir, output_path=None):
    """Generate the marketing PDF for one org. Returns the output path."""
    yaml_path = os.path.join(org_dir, "org-setup.yaml")
    config = load_org_config(yaml_path)

    html = build_html(org_dir, config)

    if output_path is None:
        output_path = os.path.join(org_dir, "marketing.pdf")
    HTML(string=html, base_url=org_dir).write_pdf(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a marketing PDF for a provisioned town."
    )
    parser.add_argument("org_slug", help="Directory label for this org (e.g. 'ca-nova-scotia-new-minas')")
    parser.add_argument("--output-dir", default="org-data",
                        help="Base directory for org data (default: org-data)")
    args = parser.parse_args()

    org_dir = os.path.join(args.output_dir, args.org_slug)
    if not os.path.isdir(org_dir):
        print(f"Error: directory not found: {org_dir}")
        sys.exit(1)

    output_path = generate_marketing_pdf(org_dir)
    print(f"Written: {output_path}")


if __name__ == "__main__":
    main()
