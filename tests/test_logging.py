import logging
import importlib

import mario

from mario.log_exc.logger import set_log_verbosity


def test_set_log_verbosity_uses_minimal_format_and_suppresses_dependency_logs(capsys):
    set_log_verbosity("info", capture_warnings=False, include_dependency_logs=False)

    logging.getLogger("mario.test").info("internal message")
    logging.getLogger("openpyxl").error("external message")

    captured = capsys.readouterr()

    assert "INFO internal message" in captured.out
    assert "external message" not in captured.out
    assert "[" not in captured.out

    set_log_verbosity("critical", capture_warnings=False, include_dependency_logs=False)


def test_importing_mario_sets_info_logging_by_default():
    set_log_verbosity("critical", capture_warnings=False, include_dependency_logs=False)

    importlib.reload(mario)

    assert logging.getLogger("mario").level == logging.INFO
