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


def test_calculation_format_labels_follow_distinct_table_conventions():
    from mario.compute.format_support import calculation_formats

    assert calculation_formats('mario.calc_z') == ('IOT',)
    assert calculation_formats('mario.calc_s') == ('SUT',)
    assert calculation_formats('mario.CoreModel.lower_s') == ('SUT', 'NAM')
    assert calculation_formats('mario.CoreModel.Xa') == ('SUT', 'NAM')
    assert calculation_formats('mario.CoreModel.resolve') == ('IOT', 'SUT', 'NAM')
    assert calculation_formats('mario.Database.calc_spa') == ('IOT',)
    assert calculation_formats('mario.CoreModel.fc_ex_all') == ('SUT',)
    reference = (DOC_ROOT / 'reference/api_calculation_methods.rst').read_text()
    assert 'api_nam_calculations' in reference
    assert 'api_nam_calculations' in (DOC_ROOT / 'get_started/table_formats/nam.rst').read_text()


def test_nam_api_labels_include_supported_entrypoints_and_exclude_guarded_methods():
    from mario.compute.format_support import api_formats

    for symbol in ('mario.parse_figaro', 'mario.parse_from_excel', 'mario.write_parse_template',
                   'mario.CoreModel.get_index', 'mario.CoreModel.set_block',
                   'mario.Database.clone_scenario', 'mario.Database.to_excel'):
        assert 'NAM' in api_formats(symbol), symbol
    for symbol in ('mario.Database.query', 'mario.Database.aggregate',
                   'mario.Database.to_parquet', 'mario.CoreModel.search',
                   'mario.CoreModel.database_profile', 'mario.calc_s'):
        assert 'NAM' not in api_formats(symbol), symbol


def test_nam_interface_documents_its_actual_methods_and_is_reachable():
    from mario.api.nam import NAMDatabase

    page = (DOC_ROOT / 'reference/api_nam_database.rst').read_text()
    for name in _public_direct_symbols(NAMDatabase):
        assert re.search(rf'\b{re.escape(name)}\b', page), name
    inspection = (DOC_ROOT / 'reference/api_inspection_methods.rst').read_text()
    assert '   api_nam_database' in inspection
    assert 'api_nam_database' in (DOC_ROOT / 'get_started/table_formats/nam.rst').read_text()
