import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "libs" / "commonwealth"))
# Root pytest also collects the other services, whose top-level `config`, `settings` and `utils` modules would
# otherwise be the ones kraken imports. Kraken's modules are imported once, here, and the tests reuse them.
_saved = {name: sys.modules.pop(name, None) for name in ("config", "settings", "utils")}
_saved_xdg = os.environ.get("XDG_CONFIG_HOME")
# The settings managers are created at import, keep them away from the real configuration folder
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()

import kraken  # noqa: E402,F401  # pylint: disable=wrong-import-position,unused-import

for _name, _module in _saved.items():
    if _module is not None:
        sys.modules[_name] = _module
    else:
        sys.modules.pop(_name, None)
if _saved_xdg is None:
    os.environ.pop("XDG_CONFIG_HOME", None)
else:
    os.environ["XDG_CONFIG_HOME"] = _saved_xdg
