import os
from pathlib import Path
from typing import Optional


class SerialById:
    BY_ID_DIR = Path("/dev/serial/by-id")

    def __init__(self, path: str) -> None:
        # udev re-points the by-id link to the new device node when the device re-enumerates
        device = Path(path).resolve()
        self.link: Optional[str] = next(
            (str(link) for link in self.BY_ID_DIR.glob("*") if link.resolve() == device), None
        )

    def current_path(self) -> Optional[str]:
        if self.link is None:
            return None
        # Not strict: a node that is gone is the signal, not an error
        path = os.path.realpath(self.link)
        return path if os.path.exists(path) else None
