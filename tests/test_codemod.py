import pathlib
import shutil

from codemod_unittest_to_pytest_asserts import transform_file

DIRNAME = pathlib.Path(__file__).parent

UNITTEST_FILE = DIRNAME / "unittest_code.py"
PYTEST_FILE = DIRNAME / "pytest_code.py"


def test_codemod(tmp_path):
    victim = tmp_path / "victim.py"
    shutil.copy(UNITTEST_FILE, victim)
    transform_file(victim)
    assert victim.read_text() == PYTEST_FILE.read_text()
