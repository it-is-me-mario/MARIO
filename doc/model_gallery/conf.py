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
    site["home_hero"] = {
        "title": "Model Gallery",
        "text": "Research models built with MARIO.",
    }
    sections = {section["key"]: section for section in site["sections"]}
    setup = config["_gallery_root"] + "user_guide/configuration/model_setups.html"
    sections["get_started"]["tabs"].extend([
        {"label": "Install a model", "doc": setup + "#install-a-model"},
        {"label": "Open a project", "doc": setup + "#open-a-project"},
    ])
    docs = sections["docs"]
    docs["prefixes"].append("models/")
    docs["tabs"].append({
        "key": "models",
        "label": "Model guides",
        "doc": "index",
        "prefixes": ["models/"],
        "toc": {"doc": "index", "caption": "Models", "max_depth": 1},
        "summary": "Browse research models, their data and published studies.",
    })
    resources = sections["resources"]
    resources["landing"] = "resources/index"
    resources["tabs"].insert(1, {"label": "Model Gallery", "doc": "index"})
    site["redirects"].pop("user_guide/configuration/model_setups", None)

    for section in sections.values():
        section["landing"] = gallery_link(section["landing"])
        for tab in section["tabs"]:
            tab["doc"] = gallery_link(tab["doc"])
    for key in ("external_pages", "tutorial_redirects"):
        site[key] = {name: gallery_link(url) for name, url in site.get(key, {}).items()}
