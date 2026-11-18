"""Model Gallery additions to the approved documentation configuration."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def gallery_link(url):
    parts = urlsplit(url)
    if parts.hostname not in {"tutorials.marioproject.com", "explorer.marioproject.com"}:
        return url
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["mario_channel"] = "model_gallery"
    return urlunsplit(parts._replace(query=urlencode(query)))


def configure(config):
    site = config["mario_site"]
    config["html_css_files"].append("model-gallery.css")
    for action in site["home_hero"].get("actions", []):
        if "url" in action:
            action["url"] = gallery_link(action["url"])
    sections = {section["key"]: section for section in site["sections"]}
    site["sections"].append({
        "key": "models",
        "label": "Model Gallery",
        "landing": "models/index",
        "prefixes": ["models/"],
        "navigation": False,
        "navigation_style": "sidebar",
        "sidebar_label": "Model Gallery",
        "breadcrumb_label": "Model Gallery",
        "tabs": [{"key": "pv-hlca", "label": "PV-HLCA", "doc": "models/pv-hlca"}],
    })
    resources = sections["resources"]
    resources["landing"] = "resources/index"
    resources["tabs"].insert(1, {
        "label": "Model Gallery", "doc": "models/index", "prefixes": ["models/"],
    })
    site["redirects"].pop("user_guide/configuration/model_setups", None)

    for section in sections.values():
        section["landing"] = gallery_link(section["landing"])
        for tab in section["tabs"]:
            tab["doc"] = gallery_link(tab["doc"])
    for key in ("external_pages", "tutorial_redirects"):
        site[key] = {name: gallery_link(url) for name, url in site.get(key, {}).items()}
