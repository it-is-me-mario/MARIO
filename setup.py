# -*- coding: utf-8 -*-

from setuptools import find_packages, setup
exec(open("mario/version.py").read())
setup(
    name="mariopy",
    description=(
        "A python package for automating input-output (IO) calculations, models"
        ",visualization and scenario analysis"
    ),
    long_description = open("README.rst",encoding="utf8").read(),
    url="https://github.com/it-is-me-mario/MARIO",
    author="Mohammad Amin Tahavori, Lorenzo Rinaldi, Nicolo Golinucci",
    author_email="amin.tahavori@enextgen.it",
    version=__version__,
    license="GNU General Public License v3.0",
    #python_requires=">.3.7.0",
    include_package_data=True,
    packages=[
        "mario",
        'mario/core',
        'mario/log_exc',
        'mario/test',
        'mario/tools',
        "mario/settings"
    ],
    package_data={
        "mario/settings": ["*.yaml"],
        'mario/tools': ["*.csv"],
        "mario/test":["*.xlsx"],
        },
    install_requires=[
        "pandas == 2.2.3",
        "numpy == 2.1.1",
        "xlsxwriter == 3.2.0",
        "plotly",
        "tabulate",
        "openpyxl == 3.1.0",
        "IPython >= 8.27.0",
        "pymrio",
        "pyyaml"

    ],
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
