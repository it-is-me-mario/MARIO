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
    author_email="mohammadamin.tahavori@polimi.it",
    version=__version__,
    packages=find_packages(),
    license="GNU General Public License v3.0",
    #python_requires=">.3.7.0",
    package_data={"": ["*.txt", "*.dat", "*.doc", "*.rst","*.xlsx"]},
    install_requires=[
        "pandas >= 1.3.3",
        "numpy >= 1.21.2",
        "xlsxwriter <= 1.3.7",
        "plotly >= 4.12.0",
        "tabulate >= 0.8.9",
        "openpyxl >= 3.0.6",
        "IPython >= 7.22.0",
        "pymrio >= 0.4.6",

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
