"""Build the downloadable IOT examples used by the custom parser guide."""
from pathlib import Path
import argparse
import shutil
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import mario
from pandas.testing import assert_frame_equal


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    database = mario.load_test("IOT")
    with TemporaryDirectory(prefix="mario-parser-examples-") as temporary:
        root = Path(temporary)
        csv = root / "iot_export_csv"
        parquet = root / "iot_export_parquet"
        flat_csv = root / "flat_csv"
        database.to_txt(path=str(csv), flows=True, coefficients=False, _format="csv")
        database.to_txt(path=str(flat_csv), flows=False, coefficients=True, _format="csv", flat=True)
        database.to_parquet(path=str(parquet), flows=True, coefficients=True, flat=True)
        # The CSV guide uses matrix flows and flat coefficients in one archive.
        shutil.copytree(flat_csv / "coefficients", csv / "coefficients")
        readings = [
            mario.parse_from_txt(str(csv / "flows"), "IOT", "flows", _format="csv"),
            mario.parse_from_txt(str(csv), "IOT", "coefficients", _format="csv", flat=True),
            mario.parse_from_parquet(str(parquet), "IOT", "flows", flat=True),
        ]
        for reading in readings:
            for block in ["Z", "Y", "V", "E", "EY"]:
                assert_frame_equal(database.resolve(block), reading.resolve(block), atol=1e-10)
        for folder in [csv, parquet]:
            with ZipFile(output / (folder.name + ".zip"), "w", ZIP_DEFLATED) as archive:
                for source in sorted(folder.rglob("*")):
                    if source.is_file():
                        entry = ZipInfo(source.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                        entry.compress_type = ZIP_DEFLATED
                        archive.writestr(entry, source.read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    build(parser.parse_args().output)
