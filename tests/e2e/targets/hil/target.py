from features.wifi import WifiAccessPoints, WifiScanner
from targets.hil.wifi import HilWifiAccessPointsDriver, HilWifiScannerDriver
from targets.target import Target


class HilTarget(Target):
    name = "hil"

    def __init__(self) -> None:
        super().__init__()
        self.features = {WifiAccessPoints: HilWifiAccessPointsDriver(), WifiScanner: HilWifiScannerDriver()}

    @property
    def base_url(self) -> str:
        raise NotImplementedError

    def up(self) -> None:
        raise NotImplementedError

    def down(self) -> None:
        raise NotImplementedError

    def shell(self, command: str) -> str:
        raise NotImplementedError
