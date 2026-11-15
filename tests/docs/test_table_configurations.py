"""Format diagrams keep matrices whole and regions inside their axes."""

from bs4 import BeautifulSoup
import pytest

from tests._paths import REPO_ROOT


def diagram(kind, configuration):
    path = REPO_ROOT / "doc/source/get_started/_generated" / f"{kind}_structure.html"
    soup = BeautifulSoup(path.read_text(), "html.parser")
    return soup.select_one(f'template[data-config-grid="{configuration}"]')


@pytest.mark.parametrize("mode", ["flows", "coefficients"])
@pytest.mark.parametrize("trade,diagonal", [("isard", {"S"}), ("chenery-moses", {"U", "Yc"})])
def test_sut_regional_subheadings_and_whole_matrices(mode, trade, diagonal):
    grid = diagram("sut", f"multi-region/{trade}/factor-accounts/{mode}")
    assert [str(node.string) for node in grid.select('thead th[scope="colgroup"]')] == [
        "Commodities", "Activities", "Final demand",
    ]
    assert [str(node.string) for node in grid.select('th[scope="rowgroup"]')] == [
        "Commodities", "Activities",
    ]
    assert [str(node.string) for node in grid.select('thead th[scope="col"]')] == ["R1", "R2"] * 3
    assert [str(node.string) for node in grid.select('tbody .table-map__region-heading')] == ["R1", "R2"] * 2
    for flow_name in ("S", "U", "Yc", "Ya", "Va", "Vc", "VY", "Ea", "Ec", "EY"):
        name = flow_name.lower() if mode == "coefficients" and flow_name in {"S", "U", "Va", "Vc", "Ea", "Ec"} else flow_name
        blocks = grid.select(f'[data-matrix-link="matrix-{name}"]')
        assert len(blocks) == 1
        block = blocks[0]
        assert str(block.code.string) == name
        assert len(block.select("code")) == 1
        assert block.parent["colspan"] == "2"
        cells = block.select(".table-map__partition > span")
        assert len(cells) == (4 if flow_name in {"S", "U", "Yc", "Ya"} else 2)
        for cell in cells:
            zero = flow_name in diagonal and cell["data-region-from"] != cell["data-region-to"]
            assert ("is-zero" in cell["class"]) == zero


@pytest.mark.parametrize("mode", ["flows", "coefficients"])
def test_iot_keeps_each_matrix_whole_with_regional_subheadings(mode):
    grid = diagram("iot", f"multi-region/bilateral/factor-accounts/{mode}")
    assert [str(node.string) for node in grid.select('thead th[scope="colgroup"]')] == [
        "Sectors", "Final demand",
    ]
    assert [str(node.string) for node in grid.select('thead th[scope="col"]')] == ["R1", "R2"] * 2
    names = ("Z", "Y", "V", "VY", "E", "EY") if mode == "flows" else ("z", "Y", "v", "VY", "e", "EY")
    for name in names:
        assert len(grid.select(f'[data-matrix-link="matrix-{name}"]')) == 1
    assert not grid.select(".is-zero")


@pytest.mark.parametrize("kind,name", [("iot", "IMP"), ("sut", "IMP_a"), ("sut", "IMP_c"), ("sut", "IMP_Y")])
def test_single_region_blocks_use_the_compact_layout(kind, name):
    grid = diagram(kind, "single-region/external-trade/separate/flows/aggregate/total")
    block = grid.select_one(f'[data-matrix-link="matrix-{name}"]')
    assert block is not None
    assert not grid.select(".table-map__region-heading")
    assert not grid.select(".table-map__partition")
    assert not grid.select(".table-map__grid--regional")


@pytest.mark.parametrize("kind,detail", [("iot", "total"), ("iot", "sector"),
                                        ("sut", "total"), ("sut", "commodity"), ("sut", "activity")])
@pytest.mark.parametrize("resolution", ["aggregate", "by_region"])
@pytest.mark.parametrize("representation", ["factor-accounts", "separate"])
@pytest.mark.parametrize("mode", ["flows", "coefficients"])
def test_single_region_api_parameters_change_import_axes(kind, detail, resolution, representation, mode):
    grid = diagram(kind, f"single-region/external-trade/{representation}/{mode}/{resolution}/{detail}")
    assert grid is not None
    assert not grid.select(".table-map__region-heading")
    assert grid.select_one("[data-imports-by]")["data-imports-by"] == detail
    assert f"trade_resolution={resolution}" in grid.caption.get_text(types=None)
    assert f"import_representation={representation}" in grid.caption.get_text(types=None)
    item_count = 1 if detail == "total" else 2
    origin_count = 2 if resolution == "by_region" else 1
    row_count = item_count * origin_count + (representation == "factor-accounts")
    blocks = grid.select(".has-account-rows")
    assert len(blocks) == (2 if kind == "iot" else 3)
    for block in blocks:
        assert len(block.select("code")) == 1
        rows = block.select(".table-map__account-partition > span")
        assert len(rows) == row_count
        imported = [row for row in rows if row["data-account-kind"] == "import"]
        origins = [row.get("data-foreign-region") for row in imported]
        assert origins == (["F1", "F2"] * item_count if resolution == "by_region" else [None] * item_count)
        assert all(row.get("data-import-item") is None for row in imported) == (detail == "total")
    assert ("F1, F2" in grid.select_one(".table-map__export-partners").get_text(types=None)) == (resolution == "by_region")


@pytest.mark.parametrize("kind", ["iot", "sut"])
def test_diagram_controls_use_public_api_names(kind):
    path = REPO_ROOT / "doc/source/get_started/_generated" / f"{kind}_structure.html"
    soup = BeautifulSoup(path.read_text(), "html.parser")
    for field, parameter in (("imports", "import_representation"), ("resolution", "trade_resolution"),
                             ("detail", "imports_by")):
        select = soup.select_one(f'select[data-config="{field}"]')
        assert parameter in select.parent.get_text()
    assert [option["value"] for option in soup.select('select[data-config="resolution"] option')] == ["aggregate", "by_region"]
