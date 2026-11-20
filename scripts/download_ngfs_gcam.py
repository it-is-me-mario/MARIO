"""Download the two public GCAM workbooks from the NGFS Phase V Scenario Explorer."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Support direct execution from a source checkout.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mario.model.ngfs import PORTAL, _workbooks

MODEL = "GCAM 6.0 NGFS"
SCENARIOS = ("Current Policies", "Net Zero 2050")


def download(destination):
    destination.mkdir(parents=True, exist_ok=True)
    manifest = []
    for run, content in _workbooks(MODEL, SCENARIOS):
        scenario = run["scenario"]
        file = destination / (scenario.replace(" ", "_") + ".xlsx")
        tmp = file.with_suffix(".part")
        tmp.write_bytes(content)
        tmp.replace(file)
        manifest.append(
            dict(run, file=file.name, sha256=hashlib.sha256(content).hexdigest())
        )
        print(scenario, run["run_id"], len(content), flush=True)
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
