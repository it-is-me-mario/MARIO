"""The introductory NAM diagram must preserve the runtime accounting domains."""

from copy import deepcopy
from html.parser import HTMLParser
import importlib.util
import json

from tests._paths import REPO_ROOT


spec = importlib.util.spec_from_file_location(
    "nomenclature_generator", REPO_ROOT / "doc/scripts/generate_nomenclature_tables.py"
)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class Diagram(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.links = []
        self.definitions = []
        self.axes = {"row": [], "col": []}
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "data-matrix-link" in attrs:
            self.links.append(attrs)
        if tag == "th" and "data-set-id" in attrs:
            self.axes[attrs["scope"]].append(attrs["data-set-id"])
        if "data-matrix-definition" in attrs:
            self.definitions.append(attrs["id"])

    def handle_data(self, data):
        self.text.append(data)


def schema():
    return json.loads((REPO_ROOT / "mario/model/nam_schema.json").read_text())


def test_nam_diagram_links_exact_domains_without_double_counting_imports():
    contract = schema()
    diagram = Diagram(generator.render_nam_structure(contract))
    matrices = {m["name"]: m for m in contract["matrices"]}
    names = {link["data-matrix-link"].removeprefix("matrix-") for link in diagram.links}
    assert {"U", "S", "RI_d", "RS_dd", "IK_d", "AF_d", "LF_d", "MU", "MY", "Minv", "M_o", "O_o"} <= names
    assert not {"T", "t", "X", "B9_d", "B9_f", "MS", "ms"} & names
    assert diagram.axes["row"] == diagram.axes["col"] == list(contract["sets"]) * 2
    assert len(diagram.definitions) == len(set(diagram.definitions)) == len(diagram.links)
    for link in diagram.links:
        target = link["data-matrix-link"]
        block = matrices[target.removeprefix("matrix-")]
        assert link["href"] == f"#{target}"
        assert target in diagram.definitions
        assert block["role"] in {"flow", "coefficient"}
        assert (link["data-row-domain"], link["data-column-domain"]) == (
            block["rows"], block["columns"]
        )


def test_nam_diagram_reads_symbols_definitions_and_sets_from_contract():
    contract = deepcopy(schema())
    use = next(m for m in contract["matrices"] if m["name"] == "U")
    use.update(name="UseFlow", description="Products <used> & paid for.")
    coefficient = next(m for m in contract["matrices"] if m.get("source") == "U")
    coefficient.update(source="UseFlow", name="useflow")
    contract["sets"]["commodity"]["label"] = "Updated product set"
    diagram = Diagram(generator.render_nam_structure(contract))
    assert "matrix-UseFlow" in diagram.definitions
    assert "matrix-U" not in diagram.definitions
    text = " ".join(diagram.text)
    assert use["description"] in text
    assert "Updated product set" in text
