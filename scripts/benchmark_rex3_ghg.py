"""Benchmark the REX3 GHG coefficients against the published flow accounts.

The script deliberately runs before constructing a MARIO ``Database``.  It
streams the large yearly transaction matrix from MATLAB v7.3/HDF5, derives
total output, converts the six ``d_CC`` coefficient rows to flows, and compares
the result with the REX3 climate-change and supplemental LULUCF flow accounts.
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy.io import loadmat


GHG_SOURCE_LABELS = (
    "GHG source: coal",
    "GHG source: oil",
    "GHG source: gas",
    "GHG source: biogenic",
    "GHG source: calcination",
    "GHG source: LULUCF",
)


def _decode_hdf5_char(handle: h5py.File, reference) -> str:
    """Decode one MATLAB v7.3 char array referenced by a cell array."""
    values = handle[reference][()]
    return "".join(chr(int(value)) for value in values.ravel(order="F") if value)


def _read_hdf5_cellstr(path: Path, dataset_name: str) -> np.ndarray:
    """Read one MATLAB v7.3 cell-string dataset into an object array."""
    with h5py.File(path, "r") as handle:
        references = handle[dataset_name][()]
        strings = np.empty(references.shape, dtype=object)
        for index, reference in np.ndenumerate(references):
            strings[index] = _decode_hdf5_char(handle, reference)
    return strings


def _read_v73_numeric(path: Path, dataset_name: str) -> np.ndarray:
    """Read and orient one numeric MATLAB v7.3 array for Python use."""
    with h5py.File(path, "r") as handle:
        return np.asarray(handle[dataset_name][()]).T


def _read_rex3_labels(labels_dir: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return countries, sectors and ordered country-sector pairs."""
    countries = _read_hdf5_cellstr(
        labels_dir / "Labels_Countries_REX3.mat",
        "Labels_Countries_REX3",
    ).ravel(order="F")
    sectors_with_households = _read_hdf5_cellstr(
        labels_dir / "Labels_Sectors_REX3.mat",
        "Labels_Sectors_REX3",
    ).ravel(order="F")
    transaction_labels = _read_hdf5_cellstr(
        labels_dir / "Labels_T_REX3.mat",
        "Labels_T_REX3",
    )

    sectors = sectors_with_households[:-1]
    expected_countries = np.repeat(countries, len(sectors))
    expected_sectors = np.tile(sectors, len(countries))
    if not np.array_equal(transaction_labels[0], expected_countries):
        raise ValueError(
            "REX3 transaction country labels do not use country-major ordering."
        )
    if not np.array_equal(transaction_labels[1], expected_sectors):
        raise ValueError(
            "REX3 transaction sector labels do not use country-major ordering."
        )

    return countries, sectors, transaction_labels


def _matlab_cell_text(value) -> str:
    """Normalize one scipy-loaded MATLAB cell-string value."""
    while isinstance(value, np.ndarray):
        if value.size == 0:
            return ""
        if value.dtype.kind in "US":
            return "".join(value.ravel(order="F").tolist())
        value = value.ravel(order="F")[0]
    return str(value)


def _validate_ghg_labels(ghg_dir: Path, transaction_labels: np.ndarray) -> None:
    """Require the supplemental GHG rows to match the main REX3 ordering."""
    label_path = ghg_dir / "Labels" / "Labels_Countrysector_combinations.mat"
    raw_labels = loadmat(label_path)["Labels_Countrysector_combinations"]
    normalized = np.vectorize(_matlab_cell_text, otypes=[object])(raw_labels)
    if not np.array_equal(normalized[:, 0], transaction_labels[0]):
        raise ValueError("Supplemental GHG country labels do not match REX3.")
    if not np.array_equal(normalized[:, 1], transaction_labels[1]):
        raise ValueError("Supplemental GHG sector labels do not match REX3.")


def _stream_transaction_output(
    path: Path,
    *,
    expected_size: int,
    block_columns: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Sum rows and columns of the oriented transaction matrix by blocks.

    MATLAB v7.3 stores the 2-D array transposed when accessed through h5py.
    Consequently, REX3 production-row totals are column totals of the raw HDF5
    dataset.
    """
    started = time.perf_counter()
    with h5py.File(path, "r") as handle:
        dataset = handle["T_REX3"]
        if dataset.shape != (expected_size, expected_size):
            raise ValueError(
                f"Unexpected T_REX3 shape {dataset.shape}; "
                f"expected {(expected_size, expected_size)}."
            )

        hdf5_chunks = list(dataset.chunks) if dataset.chunks is not None else None
        output_totals = np.zeros(expected_size, dtype=np.float64)
        input_totals = np.zeros(expected_size, dtype=np.float64)
        nonzero_count = 0
        next_progress = 10
        for start in range(0, dataset.shape[1], block_columns):
            stop = min(start + block_columns, dataset.shape[1])
            block = np.asarray(dataset[:, start:stop], dtype=np.float64)
            nonzero_count += int(np.count_nonzero(block))
            output_totals[start:stop] = block.sum(axis=0, dtype=np.float64)
            input_totals += block.sum(axis=1, dtype=np.float64)
            progress = int(stop * 100 / dataset.shape[1])
            if progress >= next_progress:
                print(
                    f"T_REX3 scan: {progress}% "
                    f"({time.perf_counter() - started:.1f} s)",
                    flush=True,
                )
                next_progress += 10

    elapsed = time.perf_counter() - started
    matrix_entries = expected_size * expected_size
    return (
        output_totals,
        input_totals,
        {
            "elapsed_seconds": elapsed,
            "block_columns": block_columns,
            "hdf5_chunks": hdf5_chunks,
            "matrix_shape": [expected_size, expected_size],
            "nonzero_entries": nonzero_count,
            "density": nonzero_count / matrix_entries,
            "estimated_scipy_csr_gib": (
                nonzero_count
                * (np.dtype(np.float64).itemsize + np.dtype(np.int32).itemsize)
                + (expected_size + 1) * np.dtype(np.int32).itemsize
            )
            / (1024**3),
        },
    )


def _year_position(ghg_dir: Path, year: int) -> int:
    """Resolve one requested year in the supplemental timeline."""
    years = np.asarray(
        loadmat(ghg_dir / "Labels" / "Labels_years.mat")["Labels_years"]
    ).reshape(-1)
    matches = np.flatnonzero(years.astype(int) == int(year))
    if matches.size != 1:
        raise ValueError(f"Year {year} was not found exactly once in GHG labels.")
    return int(matches[0])


def _relative_error(candidate: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Return element-wise relative error using reference magnitude as scale."""
    scale = np.maximum(np.abs(reference), np.finfo(np.float64).tiny)
    return np.abs(candidate - reference) / scale


def _comparison(candidate: np.ndarray, reference: np.ndarray) -> dict[str, object]:
    """Build robust scalar and distribution diagnostics for two vectors."""
    candidate = np.asarray(candidate, dtype=np.float64).reshape(-1)
    reference = np.asarray(reference, dtype=np.float64).reshape(-1)
    if candidate.shape != reference.shape:
        raise ValueError(
            f"Comparison shapes differ: {candidate.shape} != {reference.shape}."
        )

    nonzero_reference = reference != 0
    relative = _relative_error(
        candidate[nonzero_reference], reference[nonzero_reference]
    )
    candidate_total = float(candidate.sum(dtype=np.float64))
    reference_total = float(reference.sum(dtype=np.float64))
    total_scale = max(abs(reference_total), np.finfo(np.float64).tiny)

    return {
        "candidate_total": candidate_total,
        "reference_total": reference_total,
        "total_absolute_difference": candidate_total - reference_total,
        "total_relative_difference": (candidate_total - reference_total) / total_scale,
        "max_absolute_cell_difference": float(np.max(np.abs(candidate - reference))),
        "median_relative_cell_error_nonzero_reference": (
            float(np.median(relative)) if relative.size else None
        ),
        "p95_relative_cell_error_nonzero_reference": (
            float(np.quantile(relative, 0.95)) if relative.size else None
        ),
        "max_relative_cell_error_nonzero_reference": (
            float(np.max(relative)) if relative.size else None
        ),
        "candidate_nonzero_reference_zero": int(
            np.count_nonzero((candidate != 0) & ~nonzero_reference)
        ),
        "candidate_zero_reference_nonzero": int(
            np.count_nonzero((candidate == 0) & nonzero_reference)
        ),
    }


def _comparison_levels(
    candidate: np.ndarray,
    reference: np.ndarray,
    *,
    country_count: int,
    sector_count: int,
) -> dict[str, object]:
    """Compare country-sector vectors at cell and aggregate levels."""
    candidate_2d = np.asarray(candidate).reshape(country_count, sector_count)
    reference_2d = np.asarray(reference).reshape(country_count, sector_count)
    return {
        "country_sector": _comparison(candidate_2d, reference_2d),
        "country": _comparison(candidate_2d.sum(axis=1), reference_2d.sum(axis=1)),
        "global_sector": _comparison(
            candidate_2d.sum(axis=0),
            reference_2d.sum(axis=0),
        ),
        "global": _comparison(
            np.array([candidate_2d.sum(dtype=np.float64)]),
            np.array([reference_2d.sum(dtype=np.float64)]),
        ),
    }


def _peak_rss_gib() -> float:
    """Return approximate peak resident memory in GiB on Linux or macOS."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    bytes_used = raw if platform.system() == "Darwin" else raw * 1024
    return float(bytes_used / (1024**3))


def run_benchmark(
    *,
    year_dir: Path,
    labels_dir: Path,
    ghg_dir: Path,
    output_dir: Path,
    year: int,
    block_columns: int,
) -> dict[str, object]:
    """Run the pre-MARIO REX3 GHG benchmark and write its result artifacts."""
    countries, sectors, transaction_labels = _read_rex3_labels(labels_dir)
    _validate_ghg_labels(ghg_dir, transaction_labels)
    country_count = len(countries)
    sector_count = len(sectors)
    entity_count = country_count * sector_count

    transaction_output, transaction_input, timing = _stream_transaction_output(
        year_dir / "T_REX3.mat",
        expected_size=entity_count,
        block_columns=block_columns,
    )
    final_demand = _read_v73_numeric(year_dir / "Y_REX3.mat", "Y_REX3")
    if final_demand.shape != (entity_count, country_count):
        raise ValueError(f"Unexpected oriented Y_REX3 shape: {final_demand.shape}.")
    output = transaction_output + final_demand.sum(axis=1, dtype=np.float64)

    q = _read_v73_numeric(year_dir / "Q_REX3.mat", "Q_REX3")
    q_labels = _read_hdf5_cellstr(
        labels_dir / "Labels_Q_REX3.mat",
        "Labels_Q_REX3",
    ).ravel(order="F")
    climate_positions = [
        index
        for index, label in enumerate(q_labels)
        if str(label).startswith("Climate change impacts")
    ]
    if len(climate_positions) != 1:
        raise ValueError(f"Expected one climate-change row, found {climate_positions}.")
    climate_flow = q[climate_positions[0], :]
    value_added_positions = [
        index
        for index, label in enumerate(q_labels)
        if str(label).startswith("Value added")
    ]
    if len(value_added_positions) != 1:
        raise ValueError(
            f"Expected one value-added row, found {value_added_positions}."
        )
    output_from_uses = transaction_input + q[value_added_positions[0], :]

    year_position = _year_position(ghg_dir, year)
    d_cc = np.asarray(
        loadmat(ghg_dir / "d_CC_REX3_timeline.mat")["d_CC_REX3_timeline"][
            :, :, year_position
        ],
        dtype=np.float64,
    )
    lulucf_flow = np.asarray(
        loadmat(ghg_dir / "Q_LULUCF_REX3_timeline.mat")["Q_LULUCF_REX3_timeline"][
            :, year_position
        ],
        dtype=np.float64,
    )
    qy_lulucf = np.asarray(
        loadmat(ghg_dir / "Q_Y_LULUCF_REX3_timeline.mat")["Q_Y_LULUCF_REX3_timeline"][
            :, year_position
        ],
        dtype=np.float64,
    )
    if d_cc.shape != (len(GHG_SOURCE_LABELS), entity_count):
        raise ValueError(f"Unexpected d_CC shape: {d_cc.shape}.")

    ghg_flows = d_cc * output[np.newaxis, :]
    five_source_flow = ghg_flows[:5].sum(axis=0, dtype=np.float64)
    six_source_flow = ghg_flows.sum(axis=0, dtype=np.float64)
    climate_plus_lulucf = climate_flow + lulucf_flow
    recommended_six_source_flow = five_source_flow + lulucf_flow

    comparisons = {
        "economic_output_from_supply_vs_uses": _comparison_levels(
            output,
            output_from_uses,
            country_count=country_count,
            sector_count=sector_count,
        ),
        "lulucf_from_coefficient_vs_published_flow": _comparison_levels(
            ghg_flows[5],
            lulucf_flow,
            country_count=country_count,
            sector_count=sector_count,
        ),
        "five_sources_vs_base_climate_flow": _comparison_levels(
            five_source_flow,
            climate_flow,
            country_count=country_count,
            sector_count=sector_count,
        ),
        "six_sources_vs_base_climate_plus_published_lulucf": _comparison_levels(
            six_source_flow,
            climate_plus_lulucf,
            country_count=country_count,
            sector_count=sector_count,
        ),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    entity_frame = pd.DataFrame(
        {
            "Country": transaction_labels[0],
            "Sector": transaction_labels[1],
            "Output": output,
            "Base climate flow": climate_flow,
            **{
                label: ghg_flows[position]
                for position, label in enumerate(GHG_SOURCE_LABELS)
            },
            "Five-source sum": five_source_flow,
            "Five-source difference from base climate": five_source_flow - climate_flow,
            "Published LULUCF flow": lulucf_flow,
            "LULUCF difference": ghg_flows[5] - lulucf_flow,
            "Recommended six-source sum": recommended_six_source_flow,
        }
    )
    entity_frame.to_csv(output_dir / f"rex3_{year}_country_sector_ghg.csv", index=False)

    numeric_columns = entity_frame.columns.difference(["Country", "Sector"])
    country_frame = entity_frame.groupby("Country", sort=False)[numeric_columns].sum()
    sector_frame = entity_frame.groupby("Sector", sort=False)[numeric_columns].sum()
    country_frame.to_csv(output_dir / f"rex3_{year}_country_ghg.csv")
    sector_frame.to_csv(output_dir / f"rex3_{year}_sector_ghg.csv")

    result = {
        "year": year,
        "dimensions": {
            "countries": country_count,
            "sectors": sector_count,
            "country_sector_combinations": entity_count,
            "final_demand_columns": int(final_demand.shape[1]),
            "base_q_rows": int(q.shape[0]),
            "ghg_source_rows": int(ghg_flows.shape[0]),
        },
        "label_alignment": "passed",
        "transaction_scan": timing,
        "peak_rss_gib": _peak_rss_gib(),
        "total_output": float(output.sum(dtype=np.float64)),
        "published_final_demand_lulucf_total": float(qy_lulucf.sum(dtype=np.float64)),
        "comparisons": comparisons,
        "artifacts": {
            "country_sector": str(output_dir / f"rex3_{year}_country_sector_ghg.csv"),
            "country": str(output_dir / f"rex3_{year}_country_ghg.csv"),
            "sector": str(output_dir / f"rex3_{year}_sector_ghg.csv"),
        },
    }
    json_path = output_dir / f"rex3_{year}_ghg_benchmark.json"
    result["artifacts"]["json"] = str(json_path)
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    """Parse CLI arguments and run the benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year-dir", type=Path, required=True)
    parser.add_argument("--labels-dir", type=Path, required=True)
    parser.add_argument("--ghg-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--block-columns",
        type=int,
        default=64,
        help="Raw HDF5 columns read per transaction-matrix block.",
    )
    args = parser.parse_args()
    if args.block_columns <= 0:
        parser.error("--block-columns must be positive")

    result = run_benchmark(
        year_dir=args.year_dir,
        labels_dir=args.labels_dir,
        ghg_dir=args.ghg_dir,
        output_dir=args.output_dir,
        year=args.year,
        block_columns=args.block_columns,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
