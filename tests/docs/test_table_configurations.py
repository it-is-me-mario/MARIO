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
    for name in ("S", "U", "Yc", "Ya"):
        block = grid.select_one(f'[data-matrix-link="matrix-{name}"]')
        assert [str(node.string) for node in block.select(".table-map__region-axis")] == ["R1", "R2", "R1", "R2"]
        assert len(block.select(".is-zero")) == (2 if name in diagonal else 0)
    for name in ("Va", "Vc", "VY", "Ea", "Ec", "EY"):
        block = grid.select_one(f'[data-matrix-link="matrix-{name}"]')
        assert [str(node.string) for node in block.select(".table-map__region-axis")] == ["R1", "R2"]


@pytest.mark.parametrize("kind,name", [("iot", "IMP"), ("sut", "IMP_a"), ("sut", "IMP_c"), ("sut", "IMP_Y")])
def test_single_region_blocks_use_the_compact_layout(kind, name):
    grid = diagram(kind, "single-region/external-trade/separate/flows")
    block = grid.select_one(f'[data-matrix-link="matrix-{name}"]')
    assert block is not None
    assert not grid.select(".table-map__regions")
