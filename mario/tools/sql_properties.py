from mario.tools.constants import (
    _ENUM,
    SUT,
    IOT,
    _MASTER_INDEX
)


_COLUMNS = {
    'cases': {
        SUT: {
            _ENUM.S: {
                0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['a']}_from",],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['c']}_to"],
            },
            _ENUM.U: {
                0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['c']}_from",],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['a']}_to"],
            },
            _ENUM.Y: {
                0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['c']}_from",],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['n']}_to"],
            },
            _ENUM.V: {
                "V_a": {
                    0: [f"{_MASTER_INDEX['f']}_from"],
                    1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['a']}_to"],
                },
                "V_c": {
                    0: [f"{_MASTER_INDEX['f']}_from"],
                    1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['c']}_to"],
                },
                "correspondance": {
                    "v_a": "V_a",
                    "v_c": "V_c",
                }
            },
            _ENUM.E: {
                "E_c": {
                    0: [f"{_MASTER_INDEX['k']}_from"],
                    1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['c']}_to"],
                },
                "E_a": {
                    0: [f"{_MASTER_INDEX['k']}_from"],
                    1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['a']}_to"],
                },
                "correspondance": {
                    "e_a": "E_a",
                    "e_c": "E_c",
                },
            },
            _ENUM.X: {
                "X_c": {
                    0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['c']}_from",],
                },
                "X_a": {
                    0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['a']}_from",],
                },
            },
            _ENUM.p: {
                "p_c": {
                    0: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['c']}_to"],
                },
                "p_a": {
                    0: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['a']}_to",],
                },
            },
            _ENUM.EY: {
                0: [f"{_MASTER_INDEX['k']}_from"],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['n']}_to"],
            },
            _ENUM.F: {
                "F_c": {
                    0: [f"{_MASTER_INDEX['k']}_from"],
                    1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['c']}_to"],
                },
                "F_a": {
                    0: [f"{_MASTER_INDEX['k']}_from"],
                    1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['a']}_to"],
                },
                "correspondance": {
                    "f_a": "F_a",
                    "f_c": "F_c",
                }
            },
        },
        IOT: {
            _ENUM.Z: {
                0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['s']}_from",],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['s']}_to"],
            },
            _ENUM.Y: {
                0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['s']}_from",],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['n']}_to"],
            },
            _ENUM.V: {
                0: [f"{_MASTER_INDEX['f']}_from"],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['s']}_to"],
            },
            _ENUM.E: {
                0: [f"{_MASTER_INDEX['k']}_from"],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['s']}_to"],
            },
            _ENUM.X: {
                0: [f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['s']}_from"],
            },
            _ENUM.p: {
                0: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['s']}_to"],
            },
            _ENUM.EY: {
                0: [f"{_MASTER_INDEX['k']}_from"],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['n']}_to"],
            },
            _ENUM.f_dis: {
                0: [f"{_MASTER_INDEX['k']}_from",f"{_MASTER_INDEX['r']}_from",f"{_MASTER_INDEX['s']}_from"],
                1: [f"{_MASTER_INDEX['r']}_to",f"{_MASTER_INDEX['s']}_to"],
            },
        },
    },
    'correspondances': {
        SUT: {
            _ENUM.s: _ENUM.S,
            _ENUM.u: _ENUM.U,
            _ENUM.v: _ENUM.V,
            _ENUM.e: _ENUM.E,
            _ENUM.f: _ENUM.F,
        },
        IOT: {
            _ENUM.z: _ENUM.Z,
            _ENUM.v: _ENUM.V,
            _ENUM.e: _ENUM.E,
            _ENUM.f: _ENUM.E,
            _ENUM.F: _ENUM.E,
        },
    },
}

_MATRICES_LIST = {
    SUT: {
        'flows': ['S','U','Y','V','E','EY','F',"X"],
        'coefficients': ['s','u','v','e','f','p'],
    },
    IOT: {
        'flows': ['Z','Y','V','E','EY','F',"X"],
        'coefficients': ['z','v','e','f','p','f_dis'],
    }
}

_EXPORT_NAMES = {
    'Z': 'Z',
    'z': 'zz',
    'S': 'S',
    's': 'ss',
    'U': 'U',
    'u': 'uu',
    'Y': 'Y',
    'V': 'V',
    'V_a':'V_a',
    'V_c':'V_c',
    'v': 'vv',
    'v_a':'vv_a',
    'v_c':'vv_c',
    'E': 'E',
    'E_a': 'E_a',
    'E_c': 'E_c',
    'e': 'ee',
    'e_a': 'ee_a',
    'e_c': 'ee_c',
    'F': 'F',
    'F_a':'F_a',
    'F_c':'F_c',
    'f': 'ff',
    'f_a':'ff_a',
    'f_c':'ff_c',
    'p': 'p',
    'p_a':'p_a',
    'p_c':'p_c',
    'X':'X',
    'X_a':'X_a',
    'X_c':'X_c',
    'EY': 'EY',
    'f_dis': 'ff_dis',
}

_RELATIONSHIPS = {
    SUT: {
        f"_set_{_MASTER_INDEX['a']}_from": {
            "set_list": _MASTER_INDEX['a']+"_from",
            "tables": {
                'S': f"{_MASTER_INDEX['a']}_from",
                'X_a': f"{_MASTER_INDEX['a']}_from",
                'ss': f"{_MASTER_INDEX['a']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['a']}_to": {
            "set_list": _MASTER_INDEX['a']+"_to",
            "tables": {
                'U': f"{_MASTER_INDEX['a']}_to",
                'V_a': f"{_MASTER_INDEX['a']}_to",
                'E_a': f"{_MASTER_INDEX['a']}_to",
                'ee_a': f"{_MASTER_INDEX['a']}_to",
                'F_a': f"{_MASTER_INDEX['a']}_to",
                'uu': f"{_MASTER_INDEX['a']}_to",
                'vv_a': f"{_MASTER_INDEX['a']}_to",
                'p_a': f"{_MASTER_INDEX['a']}_to",
                'ff_a': f"{_MASTER_INDEX['a']}_to",
            },
        },
        f"_set_{_MASTER_INDEX['c']}_from": {
            "set_list": _MASTER_INDEX['c']+"_from",
            "tables": {
                'U': f"{_MASTER_INDEX['c']}_from",
                'Y': f"{_MASTER_INDEX['c']}_from",
                'X_c': f"{_MASTER_INDEX['c']}_from",
                'uu': f"{_MASTER_INDEX['c']}_from",

            },
        },
        f"_set_{_MASTER_INDEX['c']}_to": {
            "set_list": _MASTER_INDEX['c']+"_to",
            "tables": {
                'S': f"{_MASTER_INDEX['c']}_to",
                'V_c': f"{_MASTER_INDEX['c']}_to",
                'E_c': f"{_MASTER_INDEX['c']}_to",
                'ee_c': f"{_MASTER_INDEX['c']}_to",
                'F_c': f"{_MASTER_INDEX['c']}_to",
                'ss': f"{_MASTER_INDEX['c']}_to",
                'vv_c': f"{_MASTER_INDEX['c']}_to",
                'p_c': f"{_MASTER_INDEX['c']}_to",
                'ff_c': f"{_MASTER_INDEX['c']}_to",
            },
        },
        f"_set_{_MASTER_INDEX['n']}_to": {
            "set_list": _MASTER_INDEX['n']+"_to",
            "tables": {
                'Y': f"{_MASTER_INDEX['n']}_to",
                'EY': f"{_MASTER_INDEX['n']}_to",
            },
        },
        f"_set_{_MASTER_INDEX['f']}_from": {
            "set_list": _MASTER_INDEX['f']+"_from",
            "tables": {
                'V_a': f"{_MASTER_INDEX['f']}_from",
                'V_c': f"{_MASTER_INDEX['f']}_from",
                'vv_a': f"{_MASTER_INDEX['f']}_from",
                'vv_c': f"{_MASTER_INDEX['f']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['k']}_from": {
            "set_list": _MASTER_INDEX['k']+"_from",
            "tables": {
                'E_a': f"{_MASTER_INDEX['k']}_from",
                'ee_a': f"{_MASTER_INDEX['k']}_from",
                'E_c': f"{_MASTER_INDEX['k']}_from",
                'ee_c': f"{_MASTER_INDEX['k']}_from",
                'EY': f"{_MASTER_INDEX['k']}_from",
                'ff_c': f"{_MASTER_INDEX['k']}_from",
                'ff_a': f"{_MASTER_INDEX['k']}_from",
                'F_a': f"{_MASTER_INDEX['k']}_from",
                'F_c': f"{_MASTER_INDEX['k']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['r']}_from": {
            "set_list": _MASTER_INDEX['r']+"_from",
            "tables": {
                'U': f"{_MASTER_INDEX['r']}_from",
                'S': f"{_MASTER_INDEX['r']}_from",
                'uu': f"{_MASTER_INDEX['r']}_from",
                'ss': f"{_MASTER_INDEX['r']}_from",
                'Y': f"{_MASTER_INDEX['r']}_from",
                'X_a': f"{_MASTER_INDEX['r']}_from",
                'X_c': f"{_MASTER_INDEX['r']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['r']}_to": {
            "set_list": _MASTER_INDEX['r']+"_to",
            "tables": {
                'U': f"{_MASTER_INDEX['r']}_to",
                'S': f"{_MASTER_INDEX['r']}_to",
                'p_a': f"{_MASTER_INDEX['r']}_to",
                'p_c': f"{_MASTER_INDEX['r']}_to",
                'uu': f"{_MASTER_INDEX['r']}_to",
                'ss': f"{_MASTER_INDEX['r']}_to",
                'Y': f"{_MASTER_INDEX['r']}_to",
                'EY': f"{_MASTER_INDEX['r']}_to",
                'V_a': f"{_MASTER_INDEX['r']}_to",
                'V_c': f"{_MASTER_INDEX['r']}_to",
                'vv_a': f"{_MASTER_INDEX['r']}_to",
                'vv_c': f"{_MASTER_INDEX['r']}_to",
                'E_a': f"{_MASTER_INDEX['r']}_to",
                'ee_a': f"{_MASTER_INDEX['r']}_to",
                'E_c': f"{_MASTER_INDEX['r']}_to",
                'ee_c': f"{_MASTER_INDEX['r']}_to",
                'F_a': f"{_MASTER_INDEX['r']}_to",
                'F_c': f"{_MASTER_INDEX['r']}_to",
                'ff_a': f"{_MASTER_INDEX['r']}_to",
                'ff_c': f"{_MASTER_INDEX['r']}_to",
            },
        },
    },
    IOT: {
        f"_set_{_MASTER_INDEX['s']}_from": {
            "set_list": _MASTER_INDEX['s']+"_from",
            "tables": {
                'Z': f"{_MASTER_INDEX['s']}_from",
                'zz': f"{_MASTER_INDEX['s']}_from",
                'Y': f"{_MASTER_INDEX['s']}_from",
                'X': f"{_MASTER_INDEX['s']}_from",
                'ff_dis': f"{_MASTER_INDEX['s']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['s']}_to": {
            "set_list": _MASTER_INDEX['s']+"_to",
            "tables": {
                'Z': f"{_MASTER_INDEX['s']}_to",
                'zz': f"{_MASTER_INDEX['s']}_to",
                'V': f"{_MASTER_INDEX['s']}_to",
                'vv': f"{_MASTER_INDEX['s']}_to",
                'E': f"{_MASTER_INDEX['s']}_to",
                'ee': f"{_MASTER_INDEX['s']}_to",
                'p': f"{_MASTER_INDEX['s']}_to",
                'F': f"{_MASTER_INDEX['s']}_to",
                'ff': f"{_MASTER_INDEX['s']}_to",
                'ff_dis': f"{_MASTER_INDEX['s']}_to",
            },
        },
        f"_set_{_MASTER_INDEX['n']}_to": {
            "set_list": _MASTER_INDEX['n']+"_to",
            'tables': {
                'Y': f"{_MASTER_INDEX['n']}_to",
                'EY': f"{_MASTER_INDEX['n']}_to",
            },
        },
        f"_set_{_MASTER_INDEX['f']}_from": {
            "set_list": _MASTER_INDEX['f']+"_from",
            "tables": {
                'V': f"{_MASTER_INDEX['f']}_from",
                'vv': f"{_MASTER_INDEX['f']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['k']}_from": {
            "set_list": _MASTER_INDEX['k']+"_from",
            "tables": {
                'E': f"{_MASTER_INDEX['k']}_from",
                'ee': f"{_MASTER_INDEX['k']}_from",
                'EY': f"{_MASTER_INDEX['k']}_from",
                'F': f"{_MASTER_INDEX['k']}_from",
                'ff': f"{_MASTER_INDEX['k']}_from",
                'ff_dis': f"{_MASTER_INDEX['k']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['r']}_from": {
            'set_list': _MASTER_INDEX['r']+"_from",
            "tables": {
                'Z': f"{_MASTER_INDEX['r']}_from",
                'X': f"{_MASTER_INDEX['r']}_from",
                'zz': f"{_MASTER_INDEX['r']}_from",
                'Y': f"{_MASTER_INDEX['r']}_from",
                'ff_dis': f"{_MASTER_INDEX['r']}_from",
            },
        },
        f"_set_{_MASTER_INDEX['r']}_to": {
            "set_list": _MASTER_INDEX['r']+"_to",
            "tables": {
                'Z': f"{_MASTER_INDEX['r']}_to",
                'zz': f"{_MASTER_INDEX['r']}_to",
                'p': f"{_MASTER_INDEX['r']}_to",
                'Y': f"{_MASTER_INDEX['r']}_to",
                'EY': f"{_MASTER_INDEX['r']}_to",
                'V': f"{_MASTER_INDEX['r']}_to",
                'vv': f"{_MASTER_INDEX['r']}_to",
                'E': f"{_MASTER_INDEX['r']}_to",
                'ee': f"{_MASTER_INDEX['r']}_to",
                'F': f"{_MASTER_INDEX['r']}_to",
                'ff': f"{_MASTER_INDEX['r']}_to",
                'ff_dis': f"{_MASTER_INDEX['r']}_to",
            },
        },
    }
}

