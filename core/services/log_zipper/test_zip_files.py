import gzip
import importlib.util
import sys
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SERVICE_DIR.parents[1] / "libs" / "commonwealth"))

_SPEC = importlib.util.spec_from_file_location("log_zipper_main", _SERVICE_DIR / "main.py")
assert _SPEC is not None and _SPEC.loader is not None
_LOG_ZIPPER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_LOG_ZIPPER)


def test_zip_files_archives_every_input(tmp_path: Path) -> None:
    first = tmp_path / "a.log"
    second = tmp_path / "b.log"
    first.write_bytes(b"alpha\n")
    second.write_bytes(b"bravo\n")
    archive = tmp_path / "bundle.gz"

    _LOG_ZIPPER.zip_files([str(first), str(second)], str(archive))

    with gzip.open(archive, "rb") as compressed:
        assert compressed.read() == b"alpha\nbravo\n"
