# -*- coding: utf-8 -*-
"""
contains the plot color and layout managers
"""


import random
from mario.model.conventions import _MASTER_INDEX
import plotly


_PALETTES = {
    "Vivid": plotly.colors.qualitative.Vivid,
    "Pastel": plotly.colors.qualitative.Pastel,
    "Alphabet": plotly.colors.qualitative.Alphabet,
    "Plotly": plotly.colors.qualitative.Plotly,
    "Safe": plotly.colors.qualitative.Safe,
    "McKinsey": [
        "#051c2c",
        "#00a9f4",
        "#2251ff",
        "#aae6f0",
        "#3c96b4",
        "#8c5ac8",
        "#e6a0c8",
        "#d0d0d0",
    ],
    "mario": [
        "#3F8EFC",
        "#BF9FC2",
        "#79C2D6",
        "#67BA6F",
        "#D96940",
        "#F8D35E",
        '#02429B'
        '#69456C'
        '#276D80'
        '#2D6332'
        '#753017'
        '#A47E07'
        '#8CBBFD'
        '#D9C5DA'
        '#AFDAE6'
        '#A4D6A9'
        '#E8A58C'
        '#FBE59E'
        '#D9E8FE'
        '#F2ECF3'
        '#E4F3F7'
        '#E1F1E2'
        '#F7E1D9'
        '#FEF6DF'
    ],
}


_PLOTS_LAYOUT = {
    "font_family": "Verdana",
    "font_size": 15,
    "template": "plotly_white",
    "palette": [],
}

_NON_ACCEPTABLE_FILTERS = {
    "X": {
        "IOT": [
            f"filter_{_MASTER_INDEX['a']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['r']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['r']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "Z": {
        "IOT": [
            f"filter_{_MASTER_INDEX['a']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "z": {
        "IOT": [
            f"filter_{_MASTER_INDEX['a']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "U": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['r']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['a']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "u": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['r']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['a']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "S": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['r']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['a']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "s": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['r']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['a']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['c']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "Y": {
        "IOT": [
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
        ],
    },
    "V": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
    },
    "v": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
    },
    "M": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['k']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
    },
    "E": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
    },
    "e": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
    },
    "F": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['n']}".replace(" ", "_"),
        ],
    },
    "EY": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ],
    },
    "VY": {
        "IOT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
        ],
        "SUT": [
            f"filter_{_MASTER_INDEX['r']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_from".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['s']}_to".replace(" ", "_"),
            f"filter_{_MASTER_INDEX['f']}".replace(" ", "_"),
        ],
    },
}


class Color(list):
    """Palette container that can extend itself with random colors on demand."""

    def __init__(self):
        """Initialize the palette from configured defaults."""
        palette = _PLOTS_LAYOUT["palette"]

        if palette:
            self.extend(palette)
        else:
            self.extend(_PALETTES["mario"])

    def __getitem__(self, i):
        """Return one color, growing the palette if the index is out of range."""
        try:
            return super().__getitem__(i)
        except IndexError:
            color = self.random_color()
            while color in self:
                color = self.random_color()

            self.append(color)

            return color

    def random_color(self):
        """Generate one random hex color."""
        return "#" + "".join([random.choice("0123456789ABCDEF") for j in range(6)])

    def has_enough_colors(self, check):
        """To check if enough colors exist

        Parameters
        ----------
        check : any object that hsa len

        """
        try:
            while len(self) < len(check):
                self.random_color()
        except:
            pass
