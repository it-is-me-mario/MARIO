"""Format diagrams keep regional coordinates and structural zeros visible."""

from bs4 import BeautifulSoup
import pytest

from tests._paths import REPO_ROOT


def diagram(kind, configuration):
    path = REPO_ROOT / "doc/source/get_started/_generated" / f"{kind}_structure.html"
    soup = BeautifulSoup(path.read_text(), "html.parser")
    return soup.select_one(f'template[data-config-grid="{configuration}"]')


@pytest.mark.parametrize("trade,diagonal", [("isard", {"S"}), ("chenery-moses", {"U", "Yc"})])
def test_sut_regional_headers_and_structural_zeros(trade, diagonal):
    grid = diagram("sut", f"multi-region/{trade}/factor-accounts/flows")
    assert [str(node.string) for node in grid.select('thead th[scope="colgroup"]')] == ["R1", "R2"]
    assert [str(node.string) for node in grid.select('th[scope="rowgroup"]')] == ["R1", "R2"]
    assert [str(node.string) for node in grid.select('thead th[scope="col"]')] == [
        "Commodities", "Activities", "Final demand",
        "Commodities", "Activities", "Final demand",
    ]
    for name in ("S", "U", "Yc", "Ya"):
        blocks = grid.select(f'[data-matrix-link="matrix-{name}"]')
        assert len(blocks) == 4
        for block in blocks:
            cell = block.parent
            zero = name in diagonal and cell["data-region-from"] != cell["data-region-to"]
            assert ("is-zero" in cell["class"]) == zero
            assert str(block.code.string) == ("0" if zero else name)
    for name in ("Va", "Vc", "VY", "Ea", "Ec", "EY"):
        blocks = grid.select(f'[data-matrix-link="matrix-{name}"]')
        assert [block.parent["data-region-to"] for block in blocks] == ["R1", "R2"]
        assert all("data-region-from" not in block.parent.attrs for block in blocks)


@pytest.mark.parametrize("mode,name", [("flows", "Z"), ("coefficients", "z")])
def test_iot_groups_productive_and_final_demand_columns_by_region(mode, name):
    grid = diagram("iot", f"multi-region/bilateral/factor-accounts/{mode}")
    assert [str(node.string) for node in grid.select('thead th[scope="colgroup"]')] == ["R1", "R2"]
    assert [str(node.string) for node in grid.select('thead th[scope="col"]')] == [
        "Sectors", "Final demand", "Sectors", "Final demand",
    ]
    assert len(grid.select(f'[data-matrix-link="matrix-{name}"]')) == 4
    assert not grid.select(".is-zero")


@pytest.mark.parametrize("kind,name", [("iot", "IMP"), ("sut", "IMP_a"), ("sut", "IMP_c"), ("sut", "IMP_Y")])
def test_single_region_blocks_use_the_compact_layout(kind, name):
    grid = diagram(kind, "single-region/external-trade/separate/flows")
    block = grid.select_one(f'[data-matrix-link="matrix-{name}"]')
    assert block is not None
    assert not grid.select(".table-map__region-heading")
    assert not grid.select(".table-map__grid--regional")
