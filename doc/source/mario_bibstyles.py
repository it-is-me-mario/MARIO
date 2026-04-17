"""Local pybtex styles used by the MARIO documentation."""

from pybtex.plugin import register_plugin
from pybtex.style.formatting.unsrt import Style as UnsrtStyle


class MarioAbbreviatedStyle(UnsrtStyle):
    """Unsrt-like style with author names rendered as surname + initials."""

    def __init__(self, **kwargs):
        kwargs.setdefault("name_style", "lastfirst")
        kwargs.setdefault("abbreviate_names", True)
        kwargs.setdefault("label_style", "number")
        kwargs.setdefault("sorting_style", "none")
        super().__init__(**kwargs)


register_plugin("pybtex.style.formatting", "mario_abbr", MarioAbbreviatedStyle)
