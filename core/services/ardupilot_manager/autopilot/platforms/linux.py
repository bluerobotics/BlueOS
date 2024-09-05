from loguru import logger

from autopilot.platform import AutopilotPlatform

class LinuxPlatform(AutopilotPlatform):
    def start(self) -> None:
        print("Starting AutopiPlatformLinux")

    def stop(self) -> None:
        print("Stopping AutopiPlatformLinux")

    def restart(self) -> None:
        print("Restarting AutopiPlatformLinux")
