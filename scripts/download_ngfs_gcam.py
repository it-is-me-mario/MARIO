"""Download the two public GCAM workbooks from the NGFS Phase V Scenario Explorer."""

import argparse
import hashlib
import json
from pathlib import Path

import requests

PORTAL = "https://data.ene.iiasa.ac.at/ngfs"
API = "https://db1.ene.iiasa.ac.at/ngfs-phase-5-api/rest/v2.1"
AUTH = "https://api.manager.ece.iiasa.ac.at/legacy/anonym/IXSE_NGFS_PHASE_5"
MODEL = "GCAM 6.0 NGFS"
SCENARIOS = ("Current Policies", "Net Zero 2050")


def download(destination):
    destination.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    guest = session.get(AUTH, params={"algorithm": "HS256"}, timeout=40)
    guest.raise_for_status()
    session.headers["Authorization"] = "Bearer " + guest.text.strip().strip('"')
    runs = session.get(API + "/runs", params={"getOnlyDefaultRuns": "true"}, timeout=90)
    runs.raise_for_status()
    manifest = []
    for scenario in SCENARIOS:
        (run,) = [
            r for r in runs.json() if r["model"] == MODEL and r["scenario"] == scenario
        ]
        url = f"{API}/runs/{run['run_id']}/ts"
        file = destination / (scenario.replace(" ", "_") + ".xlsx")
        response = session.get(
            url,
            headers={
                "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            },
            timeout=240,
        )
        response.raise_for_status()
        if not response.content.startswith(b"PK"):
            raise ValueError(
                f"Expected an XLSX from {url}: {response.headers.get('Content-Type')}"
            )
        tmp = file.with_suffix(".part")
        tmp.write_bytes(response.content)
        tmp.replace(file)
        manifest.append(
            dict(
                model=MODEL,
                scenario=scenario,
                run_id=run["run_id"],
                version=run.get("version"),
                file=file.name,
                sha256=hashlib.sha256(response.content).hexdigest(),
                url=url,
            )
        )
        print(scenario, run["run_id"], len(response.content), flush=True)
    (destination / "source.json").write_text(
        json.dumps({"source": PORTAL, "runs": manifest}, indent=2) + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "destination",
        type=Path,
        help="Directory for scenario workbooks and the source manifest",
    )
    download(parser.parse_args().destination)
