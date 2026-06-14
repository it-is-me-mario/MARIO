import ast

from tests._paths import REPO_ROOT


def _setup_keyword(name):
    tree = ast.parse((REPO_ROOT / "setup.py").read_text(encoding="utf8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "setup":
            for keyword in node.keywords:
                if keyword.arg == name:
                    return ast.literal_eval(keyword.value)
    raise AssertionError(f"setup.py does not define {name!r}")


def test_pyarrow_is_installed_by_default_for_parquet_support():
    install_requires = _setup_keyword("install_requires")

    assert "pyarrow>=17" in install_requires


def test_package_declares_supported_python_runtime():
    assert _setup_keyword("python_requires") == ">=3.11"
