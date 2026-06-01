from pathlib import Path

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

    assert "../concepts/_generated/matrices_table.html" in page
    assert 'db.resolve("Xa")' in page
    assert "Xc" in page
    assert "Cx" in page
