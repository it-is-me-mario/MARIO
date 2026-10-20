from pathlib import Path
import re

import mario

from mario.api.core_model import CoreModel
from mario.api.database import Database
from tests._paths import REPO_ROOT


DOC_ROOT = REPO_ROOT / "doc" / "source"
API_DOC_ROOT = DOC_ROOT / "api_document"


def _documented_api_pages() -> set[str]:
    return {path.stem for path in API_DOC_ROOT.glob("*.rst")}


def _public_direct_symbols(cls):
    for name, obj in cls.__dict__.items():
        if name.startswith("_"):
            continue
        if isinstance(obj, property):
            yield name
        elif callable(obj):
            yield name


def test_all_public_coremodel_symbols_have_api_document_pages():
    documented = _documented_api_pages()

    missing = []
    for name in _public_direct_symbols(CoreModel):
        if f"mario.CoreModel.{name}" not in documented and f"mario.Database.{name}" not in documented:
            missing.append(name)

    assert not missing, f"Missing API reference pages for CoreModel symbols: {missing}"


def test_all_public_database_symbols_have_api_document_pages():
    documented = _documented_api_pages()

    missing = []
    for name in _public_direct_symbols(Database):
        if f"mario.Database.{name}" not in documented and f"mario.CoreModel.{name}" not in documented:
            missing.append(name)

    assert not missing, f"Missing API reference pages for Database symbols: {missing}"


def test_api_reference_exposes_resolvable_matrix_catalog():
    page = (DOC_ROOT / "reference" / "api_resolvable_matrices.rst").read_text(encoding="utf-8")

    assert "../get_started/_generated/matrices_table.html" in page
    assert 'db.resolve("Xa")' in page
    assert "Xc" in page
    assert "Cx" in page


def test_public_parser_entrypoints_have_reachable_api_pages():
    documented = _documented_api_pages()
    reference = (DOC_ROOT / "reference" / "api_parsing_methods.rst").read_text()
    config = (DOC_ROOT / "conf.py").read_text()
    for name, obj in vars(mario).items():
        if not name.startswith("parse_") or not callable(obj):
            continue
        if obj.__module__ != "mario.parsers.entrypoints":
            continue
        assert f"mario.{name}" in documented, name
        assert f"../api_document/mario.{name}" in reference, name
        assert f'"api_document/mario.{name}.rst"' not in config, name


def test_all_public_calculation_helpers_have_reachable_function_pages():
    reference = (DOC_ROOT / "reference" / "api_calculation_methods.rst").read_text()
    documented = {}
    for page in API_DOC_ROOT.glob("mario.calc*.rst"):
        for name in re.findall(r"^\.\. autofunction::\s+(?:mario\.)?(calc_\w+)\s*$",
                               page.read_text(), re.MULTILINE):
            documented[name] = page.stem

    for name, function in vars(mario).items():
        if not name.startswith("calc_") or not callable(function):
            continue
        assert name in documented, f"Missing function page for mario.{name}"
        assert f"../api_document/{documented[name]}" in reference, name
        assert ".. math::" in function.__doc__, f"Missing formula for mario.{name}"
