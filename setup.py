# -*- coding: utf-8 -*-

from pathlib import Path

from setuptools import find_packages, setup


def read_long_description():
    lines = Path(__file__).with_name("README.rst").read_text(encoding="utf8").splitlines()
    cleaned = []
    i = 0

    while i < len(lines):
        if lines[i].startswith(".. raw::"):
            i += 1

            while i < len(lines) and not lines[i].strip():
                i += 1

            while i < len(lines):
                line = lines[i]
                if line.startswith(("   ", "\t")) or not line.strip():
                    i += 1
                    continue
                break

            cleaned.append("")
            continue

        cleaned.append(lines[i])
        i += 1

    return "\n".join(cleaned)


exec(open("mario/version.py").read())
setup(
    name="mariopy",
    description=(
        "A python package for automating input-output (IO) calculations, models"
        ",visualization and scenario and supply-chain analysis"
    ),
    long_description=read_long_description(),
    long_description_content_type="text/x-rst",
    url="https://github.com/it-is-me-mario/MARIO",
    author="Lorenzo Rinaldi, Mohammad Amin Tahavori, Nicolo Golinucci",
    author_email="lorenzo.rinaldi@polimi.it",
    version=__version__,
    license="GNU General Public License v3.0",
    python_requires=">=3.11",
    include_package_data=True,
    packages=find_packages(include=("mario", "mario.*")),
    package_data={
        "mario.settings": ["*.yaml", "*.csv"],
        "mario.clusters": ["*.yaml", "*.xlsx"],
        "mario.parsers": ["*.csv", "*.yaml"],
        "mario.test":["*.xlsx"],
        "mario.ops.cvxlab_models": [
            "Split_sectors/*.xlsx",
            "Split_sectors/*.py",
        ],
        },
    install_requires=[
        "pandas == 3.0.2",
        "numpy == 2.1.1",
        "xlsxwriter == 3.2.9",
        "plotly",
        "tabulate",
        "openpyxl == 3.1.5",
        "pint == 0.25.3",
        "pyxlsb",
        "h5py",
        "scipy",
        "cvxlab>=1.0.0b1",
        "IPython >= 8.27.0",
        "pymrio",
        "pyyaml",
        "country_converter",
        "pyarrow>=17",

    ],
    extras_require={
        "dataset": [
            "scipy",
            "h5py",
            "pyxlsb",
            "cvxlab>=1.0.0b1",
        ],
        "parquet": [
            "pyarrow>=17",
        ],
        "storage": [
            "pyarrow>=17",
        ],
        "dev": [
            "pytest",
            "scipy",
            "h5py",
            "pyarrow>=17",
            "pyxlsb",
            "cvxlab>=1.0.0b1",
        ],
        "all": [
            "pytest",
            "scipy",
            "h5py",
            "pyarrow>=17",
            "pyxlsb",
            "cvxlab>=1.0.0b1",
        ],
    },
    # classifiers=[
    #     "Programming Language :: Python :: 3.7",
    #     "Programming Language :: Python :: 3.8",
    #     "Programming Language :: Python :: 3.9",
    #     "Intended Audience :: End Users/Desktop",
    #     "Intended Audience :: Developers",
    #     "Intended Audience :: Science/Research",
    #     "Operating System :: MacOS :: MacOS X",
    #     "Operating System :: Microsoft :: Windows",
    #     "Programming Language :: Python",
    #     "Topic :: Scientific/Engineering",
    #     "Topic :: Utilities",
    # ],
)
