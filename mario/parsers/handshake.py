def parse_exiobase_3_9_4(
    path,
    calc_all: bool = False,
    year: int = None,
    name: str = None,
    model: str = "Database",
    **kwargs,
):
    """Compatibility wrapper for the EXIOBASE 3.9.4 monetary IOT parser."""
    from mario.parsers.entrypoints import parse_exiobase_3

    return parse_exiobase_3(
        path=path,
        version="3.9.4",
        calc_all=calc_all,
        year=year,
        name=name,
        model=model,
        **kwargs,
    )
