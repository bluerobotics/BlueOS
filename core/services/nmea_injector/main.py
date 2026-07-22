import argparse
from collections.abc import Awaitable, Callable

from commonwealth.service.runtime import Runtime
from commonwealth.service.service import Service
from nmea_injector.adapters import (
    AsyncioSockListener,
    MavlinkMessengerSink,
    PydanticSockSettingsStore,
)
from nmea_injector.commands import AddSock, SocketKind
from nmea_injector.routes import build_nmea_router
from nmea_injector.TrafficController import NMEASocket, TrafficController

SERVICE_NAME = "nmea-injector"


def _make_on_start(
    controller: TrafficController, *, udp: int | None = None, tcp: int | None = None
) -> Callable[[Service[TrafficController]], Awaitable[None]]:
    async def _on_start(service: Service[TrafficController]) -> None:
        with service.write() as state:
            pending = state.settings_socks()

        for sock in pending:
            cmd = AddSock(kind=sock.kind, port=sock.port, component_id=sock.component_id)
            server = await controller.listen(sock)
            with service.write() as state:
                if state.has_sock(sock):
                    server.close()
                else:
                    state.apply_add(cmd, server, emit=False)

        if udp:
            cmd = AddSock(kind=SocketKind.UDP, port=udp, component_id=220)
            server = await controller.listen(NMEASocket.from_command(cmd))
            with service.write() as state:
                state.apply_add(cmd, server)
        if tcp:
            cmd = AddSock(kind=SocketKind.TCP, port=tcp, component_id=221)
            server = await controller.listen(NMEASocket.from_command(cmd))
            with service.write() as state:
                state.apply_add(cmd, server)

    return _on_start


def build_service(*, udp: int | None = None, tcp: int | None = None) -> Service[TrafficController]:
    controller = TrafficController(PydanticSockSettingsStore(), AsyncioSockListener(MavlinkMessengerSink()))
    return (
        Service.builder(SERVICE_NAME)
        .state(controller)
        .routes(lambda service: build_nmea_router(service, controller))
        .on_start(_make_on_start(controller, udp=udp, tcp=tcp))
        .http(
            2748,
            title="NMEA Injector API",
            description="NMEA Injector is a service responsible for injecting external NMEA data on the Mavlink stream.",
        )
        .logging()
        .build()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="NMEA Injector service for Blue Robotics BlueOS")
    parser.add_argument("-u", "--udp", type=int, help="change the default UDP input port")
    parser.add_argument("-t", "--tcp", type=int, help="change the default TCP input port")
    args = parser.parse_args()
    Runtime().sentry().add_service(build_service(udp=args.udp, tcp=args.tcp)).run()


if __name__ == "__main__":
    main()
