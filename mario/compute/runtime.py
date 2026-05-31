"""Runtime options and heuristics for MARIO compute backends."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from enum import Enum
import os

from mario.log_exc.exceptions import WrongInput
from mario.settings.settings import Compute

COMPUTE_METHODS = {"auto", "inverse", "solve"}
LINEAR_SOLVERS = {"scipy"}
LINEAR_STRATEGIES = {"auto", "direct", "iterative"}
SOLVE_PREFERRED_IOT_TARGETS = frozenset({"w", "X", "m", "M", "f", "F", "p"})
SOLVE_PREFERRED_SUT_TARGETS = frozenset({"wcc", "wca", "wac", "waa", "Xc", "ma", "mc", "fa", "fc", "pa", "pc"})
AUTO_ITERATIVE_RHS_THRESHOLD = 8


@dataclass(frozen=True)
class RuntimeComputeOptions:
    """Effective runtime options used by compute code."""

    compute_method: str
    linear_solver: str
    linear_strategy: str
    auto_w_memory_fraction: float
    auto_w_overhead_factor: float


def _normalize_selector_token(value) -> str | None:
    """Return one enum-or-string selector as a normalized lowercase token."""
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    return str(value).strip().lower()


def _derive_compute_method_override(public_options) -> str | None:
    """Translate high-level advanced options to the legacy runtime method."""
    if public_options is None:
        return None

    backend = _normalize_selector_token(getattr(public_options, "backend_override", None))
    if backend == "dense_inverse":
        return "inverse"
    if backend in {"sparse_direct", "sparse_iterative"}:
        return "solve"
    if backend == "dense_solve":
        raise WrongInput(
            "backend_override='dense_solve' is not supported by the current runtime yet."
        )

    planning = _normalize_selector_token(getattr(public_options, "planning_override", None))
    if planning == "prefer_explicit_intermediates":
        return "inverse"
    if planning == "prefer_direct_targets":
        return "solve"

    execution = _normalize_selector_token(getattr(public_options, "execution_mode", None))
    if execution == "prefer_speed":
        return "inverse"
    if execution == "prefer_memory":
        return "solve"
    return None


def _derive_linear_strategy_override(public_options) -> str | None:
    """Translate backend overrides to the current sparse strategy selector."""
    if public_options is None:
        return None
    backend = _normalize_selector_token(getattr(public_options, "backend_override", None))
    if backend == "sparse_direct":
        return "direct"
    if backend == "sparse_iterative":
        return "iterative"
    if backend == "dense_solve":
        raise WrongInput(
            "backend_override='dense_solve' is not supported by the current runtime yet."
        )
    return None


def normalize_compute_method(value: str | None) -> str:
    """Validate and normalize one runtime compute method selector."""
    normalized = "auto" if value is None else str(value).strip().lower()
    if normalized not in COMPUTE_METHODS:
        raise WrongInput(
            f"Unsupported compute method {value!r}. Acceptable values are {sorted(COMPUTE_METHODS)}."
        )
    return normalized


def normalize_linear_solver(value: str | None) -> str:
    """Validate and normalize one linear solver selector."""
    normalized = "scipy" if value is None else str(value).strip().lower()
    if normalized not in LINEAR_SOLVERS:
        raise WrongInput(
            f"Unsupported linear solver {value!r}. Acceptable values are {sorted(LINEAR_SOLVERS)}."
        )
    return normalized


def normalize_linear_strategy(value: str | None) -> str:
    """Validate and normalize one linear solve strategy selector."""
    normalized = "auto" if value is None else str(value).strip().lower()
    if normalized not in LINEAR_STRATEGIES:
        raise WrongInput(
            f"Unsupported linear strategy {value!r}. Acceptable values are {sorted(LINEAR_STRATEGIES)}."
        )
    return normalized


def effective_compute_options(context=None) -> RuntimeComputeOptions:
    """Return the effective compute options for one resolution request.

    Parameters
    ----------
    context:
        Optional :class:`mario.compute.types.ResolutionContext` carrying
        per-call overrides. Missing values fall back to the global MARIO
        settings stored under the ``compute`` section.

    Returns
    -------
    RuntimeComputeOptions
        Fully normalized runtime options used by planner and formula code.
    """
    configured = Compute()
    public_options = getattr(context, "compute", None)

    compute_method = getattr(context, "compute_method", None)
    if compute_method is None:
        compute_method = _derive_compute_method_override(public_options)

    linear_strategy = getattr(context, "linear_strategy", None)
    if linear_strategy is None:
        linear_strategy = _derive_linear_strategy_override(public_options)

    auto_w_memory_fraction = getattr(context, "auto_w_memory_fraction", None)
    if auto_w_memory_fraction is None and public_options is not None:
        auto_w_memory_fraction = getattr(public_options, "auto_memory_fraction", None)

    auto_w_overhead_factor = getattr(context, "auto_w_overhead_factor", None)
    if auto_w_overhead_factor is None and public_options is not None:
        auto_w_overhead_factor = getattr(public_options, "auto_inverse_overhead_factor", None)

    return RuntimeComputeOptions(
        compute_method=normalize_compute_method(compute_method or configured.compute_method),
        linear_solver=normalize_linear_solver(getattr(context, "linear_solver", None) or configured.linear_solver),
        linear_strategy=normalize_linear_strategy(linear_strategy or configured.linear_strategy),
        auto_w_memory_fraction=float(auto_w_memory_fraction or configured.auto_w_memory_fraction),
        auto_w_overhead_factor=float(auto_w_overhead_factor or configured.auto_w_overhead_factor),
    )


def _sysconf_physical_memory_bytes() -> int | None:
    """Return physical memory through POSIX sysconf when available."""
    try:
        return int(os.sysconf("SC_PHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, ValueError):
        return None


def _proc_meminfo_physical_memory_bytes() -> int | None:
    """Return physical memory from /proc/meminfo when available."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if not line.startswith("MemTotal:"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    return None

                value = int(parts[1])
                unit = parts[2].lower() if len(parts) > 2 else "b"
                multiplier = {
                    "b": 1,
                    "kb": 1024,
                    "mb": 1024**2,
                    "gb": 1024**3,
                }.get(unit)
                if multiplier is None:
                    return None
                return value * multiplier
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    return None


def _windows_physical_memory_bytes() -> int | None:
    """Return physical memory using the Windows kernel API when available."""

    class _MemoryStatusEx(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys)
    except (AttributeError, OSError, ValueError):
        return None


def physical_memory_bytes() -> int | None:
    """Return physical memory size in bytes when it can be detected."""
    if os.name == "nt":
        total = _windows_physical_memory_bytes()
        if total is not None:
            return total

    total = _sysconf_physical_memory_bytes()
    if total is not None:
        return total

    return _proc_meminfo_physical_memory_bytes()


def estimate_explicit_inverse_bytes(size: int, *, overhead_factor: float) -> float:
    """Estimate the in-memory cost of one dense square inverse."""
    return float(size) * float(size) * 8.0 * float(overhead_factor)


def choose_linear_strategy(
    *,
    size: int | None,
    rhs_count: int | None,
    context=None,
) -> str:
    """Choose the actual sparse linear strategy for one solve request.

    ``auto`` prefers the iterative path only when:
    - the system is large enough to trip the same memory heuristic used for
      inverse-vs-solve selection, and
    - the number of right-hand sides is still small enough that repeated
      iterative solves are likely cheaper than one sparse direct factorization.
    """
    options = effective_compute_options(context)
    if options.linear_strategy == "direct":
        return "direct"
    if options.linear_strategy == "iterative":
        return "iterative"

    if rhs_count is not None and rhs_count > AUTO_ITERATIVE_RHS_THRESHOLD:
        return "direct"

    if size is None:
        return "direct"

    total_memory = physical_memory_bytes()
    if total_memory is None:
        return "direct"

    estimated = estimate_explicit_inverse_bytes(
        int(size),
        overhead_factor=options.auto_w_overhead_factor,
    )
    if estimated > total_memory * options.auto_w_memory_fraction:
        return "iterative"
    return "direct"


def should_prefer_solve_for_iot_target(
    target: str,
    *,
    size: int | None,
    context=None,
) -> bool:
    """Return whether the solve-based path should be preferred for one IOT target.

    This helper is only relevant for targets that can be computed either from
    the explicit Leontief inverse ``w`` or by solving linear systems directly.
    Under ``compute_method="auto"``, MARIO prefers the solve path when the
    estimated in-memory cost of materializing a dense inverse exceeds the
    configured fraction of physical RAM.
    """
    options = effective_compute_options(context)
    if target not in SOLVE_PREFERRED_IOT_TARGETS:
        return False

    if options.compute_method == "solve":
        return True
    if options.compute_method == "inverse":
        return False

    if size is None:
        return False

    total_memory = physical_memory_bytes()
    if total_memory is None:
        return False

    estimated = estimate_explicit_inverse_bytes(
        int(size),
        overhead_factor=options.auto_w_overhead_factor,
    )
    return estimated > total_memory * options.auto_w_memory_fraction


def should_prefer_solve_for_sut_target(
    target: str,
    *,
    size: int | None,
    context=None,
) -> bool:
    """Return whether solve-based formulas should be preferred for one SUT target.

    The same runtime selector used for IOT demand-driven formulas is currently
    reused for the SUT split system. Under ``compute_method="auto"``, MARIO
    prefers the solve path when materializing the corresponding commodity-side
    or activity-side inverse would likely exceed the configured memory budget.
    """
    options = effective_compute_options(context)
    if target not in SOLVE_PREFERRED_SUT_TARGETS:
        return False

    if options.compute_method == "solve":
        return True
    if options.compute_method == "inverse":
        return False

    if size is None:
        return False

    total_memory = physical_memory_bytes()
    if total_memory is None:
        return False

    estimated = estimate_explicit_inverse_bytes(
        int(size),
        overhead_factor=options.auto_w_overhead_factor,
    )
    return estimated > total_memory * options.auto_w_memory_fraction
