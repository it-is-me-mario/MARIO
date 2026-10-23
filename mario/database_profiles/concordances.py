"""Supported classification editions and lazy packaged catalogue metadata."""
from functools import lru_cache
from importlib.resources import files
import json

CLASSIFICATIONS = {
    "NACE2.1": ("NACE Rev. 2.1", "activity", ("nace", "nace21", "nacerev21")),
    "NACE2": ("NACE Rev. 2", "activity", ("nace2", "nacerev2")),
    "NACE1.1": ("NACE Rev. 1.1", "activity", ("nace11", "nacerev11")),
    "ISIC4": ("ISIC Rev. 4", "activity", ("isic", "isic4", "isicrev4")),
    "ISIC3.1": ("ISIC Rev. 3.1", "activity", ("isic31", "isicrev31")),
    "CPA2.2": ("CPA 2.2", "commodity", ("cpa", "cpa22", "cpaver22")),
    "CPA2.1": ("CPA 2.1", "commodity", ("cpa21", "cpaver21")),
    "CPA2008": ("CPA 2008", "commodity", ("cpa2008", "cpa08")),
    "CPA2002": ("CPA 2002", "commodity", ("cpa2002", "cpa02")),
    "CPC2.1": ("CPC 2.1", "commodity", ("cpc", "cpc21", "cpcver21")),
    "HS2007": ("HS 2007", "commodity", ("hs", "hs2007", "hs07", "hs3")),
}

# Levels require a packaged official hierarchy, not digit truncation or a
# classification-to-classification correspondence inferred to be a hierarchy.
AGGREGATION_LEVELS = {
    "NACE2.1": {"section": 1, "division": 2, "group": 3, "class": 4},
    "CPA2.2": {"section": 1, "division": 2, "group": 3, "class": 4,
               "category": 5, "subcategory": 6},
}


@lru_cache(maxsize=1)
def load_manifest():
    resource = files("mario.database_profiles").joinpath("data/concordances/manifest.json")
    return json.loads(resource.read_text(encoding="utf-8"))
