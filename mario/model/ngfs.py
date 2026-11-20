"""Public default runs from the NGFS Phase V Scenario Explorer."""

from collections.abc import Sequence
from io import BytesIO

import pandas as pd
import requests

from mario.model.iamc import IamData, read_iamc


PORTAL = "https://data.ene.iiasa.ac.at/ngfs"
_API = "https://db1.ene.iiasa.ac.at/ngfs-phase-5-api/rest/v2.1"
_AUTH = "https://api.manager.ece.iiasa.ac.at/legacy/anonym/IXSE_NGFS_PHASE_5"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_COLUMNS = ["model", "scenario", "run_id", "version"]


def _catalog(session, model):
    guest = session.get(_AUTH, params={"algorithm": "HS256"}, timeout=40)
    guest.raise_for_status()
    session.headers["Authorization"] = "Bearer " + guest.text.strip().strip('"')
    response = session.get(
        f"{_API}/runs", params={"getOnlyDefaultRuns": "true"}, timeout=90
    )
    response.raise_for_status()
    catalog = pd.DataFrame.from_records(response.json(), columns=_COLUMNS)
    if model is None:
        return catalog
    matches = catalog.loc[catalog["model"] == model]
    if matches.empty:
        available = sorted(catalog["model"].unique())
        raise ValueError(
            f"Unknown NGFS Phase V model {model!r}. Available: {available}"
        )
    return matches.reset_index(drop=True)


def list_ngfs_runs(model=None):
    """List the current public default runs in the NGFS Phase V catalogue.

    Pass an exact model name to list its scenarios, or omit it to list all
    models. Returns a DataFrame with model, scenario, run_id and version.
    """
    with requests.Session() as session:
        return _catalog(session, model)


def _workbooks(model, scenarios):
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Provide one NGFS model name.")
    if isinstance(scenarios, str):
        scenarios = [scenarios]
    if (
        not isinstance(scenarios, (Sequence, pd.Series, pd.Index))
        or len(scenarios) == 0
        or any(not isinstance(name, str) or not name.strip() for name in scenarios)
    ):
        raise ValueError("Provide a scenario name or a non-empty sequence of names.")
    if len(set(scenarios)) != len(scenarios):
        raise ValueError("Each requested NGFS scenario must be distinct.")
    with requests.Session() as session:
        catalog = _catalog(session, model).set_index("scenario", drop=False)
        missing = [name for name in scenarios if name not in catalog.index]
        if missing:
            raise ValueError(
                f"Unknown scenarios for {model!r}: {missing}. Available: {sorted(catalog.index)}"
            )
        selected = catalog.loc[list(scenarios)]
        if selected.index.has_duplicates:
            raise ValueError(
                f"Multiple default NGFS runs for a requested scenario of {model!r}."
            )
        for run in selected.to_dict(orient="records"):
            run["url"] = f"{_API}/runs/{run['run_id']}/ts"
            response = session.get(run["url"], headers={"Accept": _XLSX}, timeout=240)
            response.raise_for_status()
            if not response.content.startswith(b"PK"):
                raise ValueError(f"Expected an XLSX workbook from {run['url']}.")
            yield run, response.content


def download_ngfs(model, scenarios) -> IamData:
    """Download annual IAMC series for one model from the NGFS Phase V Explorer.

    Use exact catalogue names. Pass one scenario string or a sequence of
    distinct scenarios in the desired order. Each call retrieves the current
    public default version of each run and reads the workbooks in memory.

    Returns one IamData containing every reported region, variable, unit and
    year. Its frame.attrs["ngfs_runs"] records the model, scenario, run ID,
    version and source URL for each workbook.
    """
    frames = []
    runs = []
    for run, content in _workbooks(model, scenarios):
        with pd.ExcelFile(BytesIO(content)) as workbook:
            frame = read_iamc(workbook).frame
        if not (frame.Model.eq(model) & frame.Scenario.eq(run["scenario"])).all():
            raise ValueError(f"IAMC labels disagree with NGFS run {run['run_id']}.")
        frames.append(frame)
        runs.append(run)
    combined = pd.concat(frames, ignore_index=True)
    combined.attrs["ngfs_runs"] = runs
    return IamData(combined)
