from features.wifi import AccessPoint, WifiAccessPoints, WifiScanner


class HilWifiAccessPointsDriver(WifiAccessPoints):
    def create_access_point(self, ssid: str, channel: int, passphrase: str | None = None) -> AccessPoint:
        raise NotImplementedError


class HilWifiScannerDriver(WifiScanner):
    def scan(self) -> list[str]:
        raise NotImplementedError
