# pylint: disable=redefined-outer-name
import pathlib
import re
import sys
import warnings
from typing import List

import pytest

# import local library
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent))

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.MAVLinkRouter import MAVLinkRouter
from mavlink_proxy.MAVProxy import MAVProxy


@pytest.fixture
def valid_output_endpoints() -> List[Endpoint]:
    return [
        Endpoint("udpin", "0.0.0.0", 14551),
        Endpoint("udpout", "0.0.0.0", 14552),
        Endpoint("tcpin", "0.0.0.0", 14553),
        Endpoint("tcpout", "0.0.0.0", 14554),
        Endpoint("serial", "/dev/radiolink", 57600),
    ]


@pytest.fixture
def valid_master_endpoints() -> List[Endpoint]:
    return [
        Endpoint("udpin", "0.0.0.0", 14550),
        Endpoint("udpout", "0.0.0.0", 14550),
        Endpoint("tcpin", "0.0.0.0", 14550),
        Endpoint("tcpout", "0.0.0.0", 14550),
        Endpoint("serial", "/dev/autopilot", 115200),
    ]


def test_endpoint() -> None:
    endpoint = Endpoint("udpout", "0.0.0.0", 14550)
    assert endpoint.connection_type == EndpointType.UDPClient, "Connection type does not match."
    assert endpoint.place == "0.0.0.0", "Connection place does not match."
    assert endpoint.argument == 14550, "Connection argument does not match."
    assert endpoint.__str__() == "udpout:0.0.0.0:14550", "Connection string does not match."
    assert endpoint.asdict() == {
        "connection_type": "udpout",
        "place": "0.0.0.0",
        "argument": 14550,
    }, "Endpoint dict does not match."


def test_endpoint_validators() -> None:
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": "udpin", "place": "0.0.0.0", "argument": -30})
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": "udpin", "place": "42", "argument": 14555})
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": "serial", "place": "dev/autopilot", "argument": 115200})
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": "serial", "place": "/dev/autopilot", "argument": 100000})
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": "potato", "place": "path/to/file", "argument": 100})


def test_mavproxy(valid_output_endpoints: List[Endpoint], valid_master_endpoints: List[Endpoint]) -> None:
    if not MAVProxy.is_ok():
        warnings.warn("Failed to test mavproxy service", UserWarning)
        return

    assert AbstractRouter.get_interface("MAVProxy"), "Failed to find interface MAVProxy"

    mavproxy = MAVProxy()
    assert mavproxy.name() == "MAVProxy", "Name does not match."
    assert mavproxy.logdir().exists(), "Default MAVProxy log directory does not exist."
    assert mavproxy.set_logdir(pathlib.Path(".")), "Local path as MAVProxy log directory failed."
    assert re.search(r"\d+.\d+.\d+", str(mavproxy.version())) is not None, "Version does not follow pattern."

    allowed_output_types = [
        EndpointType.Serial,
        EndpointType.UDPServer,
        EndpointType.UDPClient,
        EndpointType.TCPServer,
        EndpointType.TCPClient,
    ]
    allowed_master_types = [
        EndpointType.Serial,
        EndpointType.UDPServer,
        EndpointType.UDPClient,
        EndpointType.TCPServer,
        EndpointType.TCPClient,
    ]
    run_common_routing_tests(
        mavproxy, allowed_output_types, allowed_master_types, valid_output_endpoints, valid_master_endpoints
    )


def test_mavlink_router(valid_output_endpoints: List[Endpoint], valid_master_endpoints: List[Endpoint]) -> None:
    if not MAVLinkRouter.is_ok():
        warnings.warn("Failed to test MAVLinkRouter service", UserWarning)
        return

    assert AbstractRouter.get_interface("MAVLinkRouter"), "Failed to find interface MAVLinkRouter"

    mavlink_router = MAVLinkRouter()
    assert mavlink_router.name() == "MAVLinkRouter", "Name does not match."
    assert mavlink_router.logdir().exists(), "Default MAVLinkRouter log directory does not exist."
    assert mavlink_router.set_logdir(pathlib.Path(".")), "Local path as MAVLinkRouter log directory failed."
    assert re.search(r"\d+", str(mavlink_router.version())) is not None, "Version does not follow pattern."

    allowed_output_types = [EndpointType.UDPClient, EndpointType.TCPServer, EndpointType.TCPClient]
    allowed_master_types = [EndpointType.UDPServer, EndpointType.Serial, EndpointType.TCPServer]
    run_common_routing_tests(
        mavlink_router, allowed_output_types, allowed_master_types, valid_output_endpoints, valid_master_endpoints
    )


@pytest.mark.timeout(10)
def run_common_routing_tests(
    router: AbstractRouter,
    allowed_output_types: List[EndpointType],
    allowed_master_types: List[EndpointType],
    output_endpoints: List[Endpoint],
    master_endpoints: List[Endpoint],
) -> None:
    allowed_output_endpoints = list(
        filter(lambda endpoint: endpoint.connection_type in allowed_output_types, output_endpoints)
    )
    for endpoint in allowed_output_endpoints:
        assert router.add_endpoint(endpoint), f"Failed to add endpoint {endpoint}."
    assert router.endpoints() == allowed_output_endpoints, "Endpoint list does not match."

    unallowed_output_endpoints = list(
        filter(lambda endpoint: endpoint not in allowed_output_endpoints, output_endpoints)
    )
    for endpoint in unallowed_output_endpoints:
        with pytest.raises(NotImplementedError):
            router.add_endpoint(endpoint)

    allowed_master_endpoints = list(
        filter(lambda endpoint: endpoint.connection_type in allowed_master_types, master_endpoints)
    )
    for endpoint in allowed_master_endpoints:
        assert router.start(endpoint), f"Failed to start {router.name()} with endpoint {endpoint}."
        assert router.is_running(), f"{router.name()} is not running after start."
        assert router.exit(), f"{router.name()} could not stop."
        while router.is_running():
            pass
        assert not router.is_running(), f"{router.name()} is not stopping after exit."

    unallowed_master_endpoints = list(
        filter(lambda endpoint: endpoint not in allowed_master_endpoints, master_endpoints)
    )
    for endpoint in unallowed_master_endpoints:
        with pytest.raises(NotImplementedError):
            router.start(endpoint)
