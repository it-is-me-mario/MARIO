"""Generate the CVXLab settings workbook used by the export guide."""

from pathlib import Path

import pandas as pd


SET_MAPPING = {
    "Region_from": "region_from", "Region_to": "region_to",
    "Activity_from": "activity_from", "Activity_to": "activity_to",
    "Commodity_from": "commodity_from", "Commodity_to": "commodity_to",
    "Consumption category_to": "consumption",
    "Factor of production_from": "factor", "Satellite account_from": "extension",
}
MATRIX_MAPPING = {
    "S": "SUPPLY", "U": "USE", "Yc": "FINAL_DEMAND",
    "Va": "VALUE_ADDED", "VY": "VALUE_ADDED_FINAL_DEMAND",
    "IMP_a": "IMPORTS_USE", "IMP_c": "IMPORTS_SUPPLY", "IMP_Y": "IMPORTS_FINAL_DEMAND",
    "Ea": "EMISSIONS", "EY": "EMISSIONS_FINAL_DEMAND",
}
MATRIX_AXES = {
    "S": ["Region_from", "Activity_from", "Region_to", "Commodity_to"],
    "U": ["Region_from", "Commodity_from", "Region_to", "Activity_to"],
    "Yc": ["Region_from", "Commodity_from", "Region_to", "Consumption category_to"],
    "Va": ["Factor of production_from", "Region_to", "Activity_to"],
    "VY": ["Factor of production_from", "Region_to", "Consumption category_to"],
    "IMP_a": ["Commodity_from", "Region_to", "Activity_to"],
    "IMP_c": ["Commodity_from", "Region_to", "Commodity_to"],
    "IMP_Y": ["Commodity_from", "Region_to", "Consumption category_to"],
    "Ea": ["Satellite account_from", "Region_to", "Activity_to"],
    "EY": ["Satellite account_from", "Region_to", "Consumption category_to"],
}


def generate(path=None):
    """Write a complete settings example using the guide's mapped table names."""
    output = Path(path) if path else Path(__file__).resolve().parents[1] / (
        "source/_static/data/supporting_files/cvxlab_sut_settings.xlsx"
    )
    sets = []
    for source, target in SET_MAPPING.items():
        origin = source.removesuffix("_to") + "_from"
        sets.append({"set_key": target, "description": source,
                     "copy_from": SET_MAPPING.get(origin) if source.endswith("_to") else None})
    variables = []
    for matrix, fields in MATRIX_AXES.items():
        variables.append({
            "table_key": MATRIX_MAPPING[matrix], "description": f"MARIO {matrix}",
            "type": "exogenous", "coordinates": ", ".join(SET_MAPPING[field] for field in fields),
            "variables_info": f"input_{matrix}",
            SET_MAPPING[fields[0]]: "dim: rows", SET_MAPPING[fields[-1]]: "dim: cols",
        })
    variables.append({"table_key": "OUTPUT", "description": "Feasibility variable",
                      "type": "endogenous", "coordinates": "activity_to",
                      "variables_info": "output", "activity_to": "dim: rows"})
    problem = pd.DataFrame([{"objective": "Minimize(sum(output))", "expressions": "output >= 0",
                             "description": "Workbook loading example"}])
    output.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output) as writer:
        pd.DataFrame(sets).to_excel(writer, sheet_name="structure_sets", index=False)
        pd.DataFrame(variables).to_excel(writer, sheet_name="structure_variables", index=False)
        problem.to_excel(writer, sheet_name="problem", index=False)
    return output


if __name__ == "__main__":
    print(generate())
