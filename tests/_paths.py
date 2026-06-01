from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TESTS_ROOT.parent
MOCKS_ROOT = TESTS_ROOT / "mocks"
FIXTURES_ROOT = TESTS_ROOT / "fixtures"
REALDATA_ROOT = FIXTURES_ROOT / "realdata"
HYBRID_EXIOBASE_MOCK_ROOT = MOCKS_ROOT / "temp_files"
