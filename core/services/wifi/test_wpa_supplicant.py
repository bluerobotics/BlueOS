import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from wifi_handlers.wpa_supplicant import wpa_supplicant as wpa_module
from wifi_handlers.wpa_supplicant.wpa_supplicant import WPASupplicant

# Other test files swap the exceptions module in and out, the one the code under test raises is what counts
WPAOperationFail = vars(wpa_module)["WPAOperationFail"]

pytestmark = pytest.mark.asyncio


class _FakeSocket:
    def __init__(self, reply: bytes) -> None:
        self.reply = reply

    def send(self, _data: bytes) -> None:
        pass

    def recvfrom(self, _size: int) -> tuple[bytes, Any]:
        return self.reply, None


async def test_a_fail_reply_raises_even_with_the_trailing_newline(monkeypatch: pytest.MonkeyPatch) -> None:
    wpa = WPASupplicant()
    monkeypatch.setattr(wpa, "sock", _FakeSocket(b"FAIL\n"))

    with pytest.raises(WPAOperationFail):
        await wpa.send_command("SAVE_CONFIG", 1)


async def test_an_ok_reply_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    wpa = WPASupplicant()
    monkeypatch.setattr(wpa, "sock", _FakeSocket(b"OK\n"))

    assert await wpa.send_command("SAVE_CONFIG", 1) == b"OK\n"
