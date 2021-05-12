# pylint: disable=redefined-outer-name
import pathlib
import re
import sys
import warnings
from typing import List, Set

import pytest

# import local library
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent))

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.MAVLinkRouter import MAVLinkRouter
from mavlink_proxy.MAVProxy import MAVProxy


@pytest.fixture
def valid_output_endpoints() -> Set[Endpoint]:
    return {
        Endpoint("Test endpoint 1", "pytest", "udpin", "0.0.0.0", 14551),
        Endpoint("Test endpoint 2", "pytest", "udpout", "0.0.0.0", 14552),
        Endpoint("Test endpoint 3", "pytest", "tcpin", "0.0.0.0", 14553),
        Endpoint("Test endpoint 4", "pytest", "tcpout", "0.0.0.0", 14554),
        Endpoint("Test endpoint 5", "pytest", "serial", "/dev/radiolink", 57600),
    }


@pytest.fixture
def valid_master_endpoints() -> Set[Endpoint]:
    return {
        Endpoint("Master endpoint 1", "pytest", "udpin", "0.0.0.0", 14550),
        Endpoint("Master endpoint 2", "pytest", "udpout", "0.0.0.0", 14550),
        Endpoint("Master endpoint 3", "pytest", "tcpin", "0.0.0.0", 14550),
        Endpoint("Master endpoint 4", "pytest", "tcpout", "0.0.0.0", 14550),
        Endpoint("Master endpoint 5", "pytest", "serial", "/dev/autopilot", 115200),
    }


def test_endpoint() -> None:
    endpoint = Endpoint("Test endpoint", "pytest", "udpout", "0.0.0.0", 14550)
    assert endpoint.name == "Test endpoint", "Name does not match."
    assert endpoint.owner == "pytest", "Owner does not match."
    assert endpoint.persistent is False, "Persistent does not match."
    assert endpoint.protected is False, "Protected does not match."
    assert endpoint.connection_type == EndpointType.UDPClient, "Connection type does not match."
    assert endpoint.place == "0.0.0.0", "Connection place does not match."
    assert endpoint.argument == 14550, "Connection argument does not match."
    assert endpoint.__str__() == "udpout:0.0.0.0:14550", "Connection string does not match."
    assert endpoint.asdict() == {
        "name": "Test endpoint",
        "owner": "pytest",
        "connection_type": "udpout",
        "place": "0.0.0.0",
        "argument": 14550,
        "persistent": False,
        "protected": False,
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


def test_mavproxy(valid_output_endpoints: Set[Endpoint], valid_master_endpoints: Set[Endpoint]) -> None:
    if not MAVProxy.is_ok():
        warnings.warn("Failed to test mavproxy service", UserWarning)
        return

    assert AbstractRouter.get_interface("MAVProxy"), "Failed to find interface MAVProxy"

    mavproxy = MAVProxy()
    assert mavproxy.name() == "MAVProxy", "Name does not match."
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


def test_mavlink_router(valid_output_endpoints: Set[Endpoint], valid_master_endpoints: Set[Endpoint]) -> None:
    if not MAVLinkRouter.is_ok():
        warnings.warn("Failed to test MAVLinkRouter service", UserWarning)
        return

    assert AbstractRouter.get_interface("MAVLinkRouter"), "Failed to find interface MAVLinkRouter"

    mavlink_router = MAVLinkRouter()
    assert mavlink_router.name() == "MAVLinkRouter", "Name does not match."
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
    output_endpoints: Set[Endpoint],
    master_endpoints: Set[Endpoint],
) -> None:
    assert router.logdir().exists(), "Default router log directory does not exist."
    router.set_logdir(pathlib.Path("."))

    allowed_output_endpoints = set(
        filter(lambda endpoint: endpoint.connection_type in allowed_output_types, output_endpoints)
    )
    for endpoint in allowed_output_endpoints:
        router.add_endpoint(endpoint)
    assert router.endpoints() == allowed_output_endpoints, "Endpoint list does not match."

    unallowed_output_endpoints = output_endpoints.difference(allowed_output_endpoints)
    for endpoint in unallowed_output_endpoints:
        with pytest.raises(ValueError):
            router.add_endpoint(endpoint)

    allowed_master_endpoints = set(
        filter(lambda endpoint: endpoint.connection_type in allowed_master_types, master_endpoints)
    )
    for endpoint in allowed_master_endpoints:
        router.start(endpoint)
        assert router.is_running(), f"{router.name()} is not running after start."
        router.exit()
        while router.is_running():
            pass
        assert not router.is_running(), f"{router.name()} is not stopping after exit."

    unallowed_master_endpoints = master_endpoints.difference(allowed_master_endpoints)
    for endpoint in unallowed_master_endpoints:
        with pytest.raises(ValueError):
            router.start(endpoint)
