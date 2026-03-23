def parse_exiobase_3_9_4(path):
    """Compatibility wrapper for the EXIOBASE 3.9.4 monetary IOT parser."""
    from mario.parsers.entrypoints import parse_exiobase_3

    return parse_exiobase_3(path=path, version="3.9.4")
