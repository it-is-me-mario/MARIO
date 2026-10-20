# -*- coding: utf-8 -*-
"""
This module will contain a set of functions useful for tables transformation
such as SUT-to-IOT transformation

Methods A,B,C,D refer to the Eurostat manual of nomenclature for SUT-to-IOT 
transformation models.
For further information check 
'Eurostat Manual of Supply, Use and Input-Output Tables, 2008'
"""

from mario.model.conventions import _MASTER_INDEX

SUT_TO_IOT_METHODS = ["A", "B", "C", "D"]


def SUT_to_IOT(instance, method):
    """Convert native SUT flows using Eurostat methods ``A`` to ``D``."""
    from mario.ops.sut_to_iot import convert

    return convert(instance, method)


def ISARD_TO_CHENERY_MOSES(instance, scenario):
    """Return compatibility Z/Y views of the sparse-native transformation.

    The public wrapper stores split flow blocks directly, including transported
    commodity accounts. This adapter retains the historical two-frame return
    for callers of the old engine helper.
    """
    from mario.ops.chenery_moses import as_csr, as_frame, convert_flows, read_flows
    from mario.compute.helpers import _is_sparse_backed_dataframe
    from mario.compute.views import concat_sut_Z, concat_sut_Y
    from mario.compute.ordering import SUTUnifiedOrderingPolicy
    from scipy import sparse

    blocks = convert_flows(
        read_flows(instance, scenario),
        instance.get_index(_MASTER_INDEX["r"]),
        scenario=scenario,
    )
    ordering = SUTUnifiedOrderingPolicy.from_blocks(
        **{key: blocks[key] for key in ("U", "S", "Ya", "Yc")}
    )
    if _is_sparse_backed_dataframe(blocks["U"]) or _is_sparse_backed_dataframe(
        blocks["S"]
    ):
        like = blocks["U"] if _is_sparse_backed_dataframe(blocks["U"]) else blocks["S"]
        z = as_frame(
            sparse.bmat(
                [[None, as_csr(blocks["S"])], [as_csr(blocks["U"]), None]], format="csr"
            ),
            index=ordering.unified_index,
            columns=ordering.unified_index,
            like=like,
        )
        return z, concat_sut_Y(blocks["Ya"], blocks["Yc"], ordering)
    return concat_sut_Z(blocks["U"], blocks["S"], ordering), concat_sut_Y(
        blocks["Ya"], blocks["Yc"], ordering
    )
