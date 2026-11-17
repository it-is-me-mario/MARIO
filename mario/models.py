"""Load model setups maintained outside the MARIO repository."""

from importlib import metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory

from mario.version import __version__

_GROUP = "mario.models"
_CATALOG = {
    "pv-hlca": (
        "mario-pv-hlca",
        "https://github.com/it-is-me-mario/pv-hlca-model.git",
        "6b458e1a0927f15c285ed9db88814c870621115d",
    ),
}


def model_setup(model: str, *, workspace: str | Path | None = None, **options):
    """Open a workspace for an installed model.

    Parameters
    ----------
    model : str
        Name registered by a model package in the mario.models entry point group.
    workspace : str or pathlib.Path, optional
        Project directory. Defaults to a directory named after the model.
    **options
        Keyword arguments passed to the model's workspace factory.

    Returns
    -------
    object
        The model's project object. Its workflow and inputs are defined by the
        installed model release.
    """
    entries = list(metadata.entry_points(group=_GROUP, name=model))
    if not entries:
        hint = (
            f"Run mario.models.install({model!r}) and start a new Python session."
            if model in _CATALOG else "Install the model from its repository."
        )
        raise LookupError(f"No installed MARIO model named {model!r}. {hint}")
    if len(entries) != 1:
        raise LookupError(f"More than one installed model registers {model!r}.")
    return entries[0].load()(workspace=workspace if workspace is not None else Path(model), **options)


def _commit_for_ref(repository, ref):
    if re.fullmatch(r"[a-fA-F0-9]{40}", ref):
        return ref.lower()
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", ref) or ".." in ref or ref.startswith("-"):
        raise ValueError("Use a Git branch, tag or full commit SHA.")
    if ref.startswith("refs/"):
        names = [ref]
    else:
        names = [f"refs/heads/{ref}", f"refs/tags/{ref}"]
    result = subprocess.run(
        ["git", "ls-remote", repository, *names, *(f"{name}^{{}}" for name in names)],
        check=True, capture_output=True, text=True,
    )
    refs = {name: commit for commit, name in (line.split() for line in result.stdout.splitlines())}
    matches = [name for name in names if name in refs]
    if len(matches) != 1:
        raise ValueError(f"Ref {ref!r} must identify one branch or tag in {repository}.")
    name = matches[0]
    return refs.get(f"{name}^{{}}", refs[name])


def install(model: str, *, ref: str | None = None) -> str:
    """Install a catalogued model into the current Python environment with pip.

    Parameters
    ----------
    model : str
        Name of a model in the MARIO catalogue.
    ref : str, optional
        Branch, tag or full commit SHA in the listed repository. The default
        selects a pinned source revision. The command requires Git and pip.

    Returns
    -------
    str
        The full commit SHA selected for installation.

    Start a new Python session after switching a model revision. pip resolves
    dependencies with the installed version of MARIO held fixed.
    """
    try:
        package, repository, default_commit = _CATALOG[model]
    except KeyError as exc:
        raise LookupError(f"No MARIO catalogue entry for {model!r}. Install it from its repository.") from exc

    installed_mario = metadata.version("mariopy")
    if installed_mario != __version__:
        raise RuntimeError("Install the current MARIO checkout into this environment first.")

    commit = default_commit if ref is None else _commit_for_ref(repository, ref)
    try:
        recorded = metadata.distribution(package).read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        recorded = None
    if recorded and json.loads(recorded).get("vcs_info", {}).get("commit_id") == commit:
        return commit
    requirement = f"{package} @ git+{repository}@{commit}"
    pip = [sys.executable, "-m", "pip", "install"]
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
    with TemporaryDirectory() as directory:
        constraints = Path(directory) / "constraints.txt"
        constraints.write_text(f"mariopy=={installed_mario}\n", encoding="utf-8")
        report = Path(directory) / "install.json"
        subprocess.run(
            [*pip, "--upgrade", "--constraint", str(constraints), "--report", str(report), requirement],
            check=True, env=env,
        )
        changes = json.loads(report.read_text(encoding="utf-8"))["install"]
        if not any(item["metadata"]["name"].lower().replace("_", "-") == package for item in changes):
            # pip can retain an installed package when two source commits have the same version.
            subprocess.run([*pip, "--force-reinstall", "--no-deps", requirement], check=True, env=env)
    return commit
