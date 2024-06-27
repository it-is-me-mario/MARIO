# -*- coding: utf-8 -*-
"""
contains the plot color and layout managers
"""


import random
from mario.tools.constants import _MASTER_INDEX
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
        "#e0120f",
        "#08a936",
        "#f092be",
        "#17419a",
        "#f8be10",
        "#70b921",
        "#ee830a",
        "#f5da0f",
        "#5d2e8e",
        "#1dd4b7",
        "#f6ce09",
        "#95a4ae",
        "#742607",
        "#983106",
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
}


class Color(list):
    def __init__(self):
        palette = _PLOTS_LAYOUT["palette"]

        if palette:
            self.extend(palette)
        else:
            self.extend(_PALETTES["mario"])

    def __getitem__(self, i):
        try:
            return super().__getitem__(i)
        except IndexError:
            color = self.random_color()
            while color in self:
                color = self.random_color()

            self.append(color)

            return color

    def random_color(self):
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
