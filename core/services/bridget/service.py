from typing import Any, Dict, Union

from commands import AddBridge, RemoveBridge
from commonwealth.service.service import EventHandler, ReadModelUpdated, ServiceState
from loguru import logger
from ports import BridgeRuntime, BridgeSettingsStore, LiveBridge
from pydantic import BaseModel
from views import BridgeSummary, BridgesView


class BridgeIdentity(BaseModel):
    """Write-model identity for a live bridge (map key)."""

    serial_path: str
    baud: int
    ip: str
    udp_target_port: int
    udp_listen_port: int

    def __str__(self) -> str:
        if self.ip == "0.0.0.0":
            return f"{self.serial_path}:{self.baud}//{self.ip}:{self.udp_listen_port}"
        return f"{self.serial_path}:{self.baud}//{self.ip}:{self.udp_target_port}:{self.udp_listen_port}"

    def __hash__(self) -> int:
        return hash(str(self))

    @staticmethod
    def from_command(cmd: Union[AddBridge, RemoveBridge]) -> "BridgeIdentity":
        return BridgeIdentity(
            serial_path=cmd.serial_path,
            baud=cmd.baud,
            ip=cmd.ip,
            udp_target_port=cmd.udp_target_port,
            udp_listen_port=cmd.udp_listen_port,
        )

    def to_summary(self) -> BridgeSummary:
        return BridgeSummary(
            serial_path=self.serial_path,
            baud=self.baud,
            ip=self.ip,
            udp_target_port=self.udp_target_port,
            udp_listen_port=self.udp_listen_port,
        )


class BridgetState(ServiceState):
    """Write model: live bridges. Settings persist via ReadModelUpdated subscriber."""

    def __init__(self, runtime: BridgeRuntime, settings: BridgeSettingsStore) -> None:
        super().__init__()
        self._runtime = runtime
        self._settings = settings
        self._bridges: Dict[BridgeIdentity, LiveBridge] = {}
        for cmd in self._settings.load():
            try:
                logger.debug(f"Adding following bridge from persistency '{cmd}'.")
                self.apply_add(cmd, emit=False)
            except Exception as error:
                logger.exception(f"Could not add bridge '{cmd}'. {error}")

    def subscribers(self) -> list[EventHandler]:
        return [self._persist_settings]

    def snapshot(self) -> BridgesView:
        return BridgesView(bridges=tuple(spec.to_summary() for spec in self._bridges))

    def _persist_settings(self, event: Any) -> None:
        if isinstance(event, ReadModelUpdated) and isinstance(event.model, BridgesView):
            self._settings.save(event.model)

    def apply_add(self, cmd: AddBridge, *, emit: bool = True) -> None:
        bridge_spec = BridgeIdentity.from_command(cmd)
        if bridge_spec in self._bridges:
            raise RuntimeError("Bridge already exist.")
        self._bridges[bridge_spec] = self._runtime.open(
            bridge_spec.serial_path,
            bridge_spec.baud,
            bridge_spec.ip,
            bridge_spec.udp_target_port,
            bridge_spec.udp_listen_port,
        )
        if emit:
            self.publish_read_model()

    def apply_remove(self, cmd: RemoveBridge, *, emit: bool = True) -> None:
        bridge_spec = BridgeIdentity.from_command(cmd)
        bridge = self._bridges.pop(bridge_spec, None)
        if bridge is None:
            raise RuntimeError("Bridge doesn't exist.")
        bridge.stop()
        if emit:
            self.publish_read_model()

    def stop(self) -> None:
        logger.debug("Stopping Bridget and removing all bridges.")
        for bridge_spec in list(self._bridges):
            self.apply_remove(
                RemoveBridge(
                    serial_path=bridge_spec.serial_path,
                    baud=bridge_spec.baud,
                    ip=bridge_spec.ip,
                    udp_target_port=bridge_spec.udp_target_port,
                    udp_listen_port=bridge_spec.udp_listen_port,
                ),
                emit=False,
            )

    def __del__(self) -> None:
        self.stop()
