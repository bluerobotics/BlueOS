import pathlib
import re
import warnings

from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.MAVLinkRouter import MAVLinkRouter
from mavlink_proxy.MAVProxy import MAVProxy


def test_endpoint() -> None:
    endpoint = Endpoint("udp:0.0.0.0:14550")
    assert endpoint.connType == EndpointType.UDPClient, "Connection type does not match."
    assert endpoint.place == "0.0.0.0", "Connection place does not match."
    assert endpoint.argument == "14550", "Connection argument does not match."
    assert endpoint.__str__() == "udp:0.0.0.0:14550", "Connection string does not match."


def test_mavproxy() -> None:
    if not MAVProxy.is_ok():
        warnings.warn("Failed to test mavproxy service", UserWarning)
        return

    mavproxy = MAVProxy()
    assert mavproxy.name() == "MAVProxy", "Name does not match."
    assert mavproxy.logdir().exists(), "Default MAVProxy log directory does not exist."
    assert mavproxy.set_logdir(pathlib.Path(".")), "Local path as MAVProxy log directory failed."
    assert re.search(r"\d+.\d+.\d+", str(mavproxy.version())) is not None, "Version does not follow pattern."

    endpoint_1 = Endpoint("udpout:0.0.0.0:14551")
    endpoint_2 = Endpoint("udpout:0.0.0.0:14552")
    assert mavproxy.add_endpoint(endpoint_1), "Failed to add first endpoint"
    assert mavproxy.add_endpoint(endpoint_2), "Failed to add second endpoint"
    assert mavproxy.endpoints() == [
        endpoint_1,
        endpoint_2,
    ], "Endpoint list does not match."

    assert mavproxy.start(Endpoint("udp:0.0.0.0:14550")), "Failed to start mavproxy"
    assert mavproxy.is_running(), "MAVProxy is not running after start."


def test_mavlink_router() -> None:
    if not MAVLinkRouter.is_ok():
        warnings.warn("Failed to test MAVLinkRouter service", UserWarning)
        return

    mavlink_router = MAVLinkRouter()
    assert mavlink_router.name() == "MAVLinkRouter", "Name does not match."
    assert mavlink_router.logdir().exists(), "Default MAVLinkRouter log directory does not exist."
    assert mavlink_router.set_logdir(pathlib.Path(".")), "Local path as MAVLinkRouter log directory failed."
    assert re.search(r"\d+", str(mavlink_router.version())) is not None, "Version does not follow pattern."

    endpoint_1 = Endpoint("udpout:0.0.0.0:14551")
    endpoint_2 = Endpoint("udpout:0.0.0.0:14552")
    assert mavlink_router.add_endpoint(endpoint_1), "Failed to add first endpoint"
    assert mavlink_router.add_endpoint(endpoint_2), "Failed to add second endpoint"
    assert mavlink_router.endpoints() == [
        endpoint_1,
        endpoint_2,
    ], "Endpoint list does not match."

    assert mavlink_router.start(Endpoint("udp:0.0.0.0:14550")), "Failed to start MAVLinkRouter"
    assert mavlink_router.is_running(), "MAVLinkRouter is not running after start."
