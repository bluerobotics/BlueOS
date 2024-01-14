# pylint: disable=redefined-outer-name
import os
import pathlib
import pty
import re
import sys
import warnings
from typing import List, Set

import pytest

# import local library
sys.path.append(str(pathlib.Path(__file__).absolute().parent.parent))

from mavlink_proxy.AbstractRouter import AbstractRouter
from mavlink_proxy.Endpoint import Endpoint
from mavlink_proxy.MAVLinkRouter import MAVLinkRouter
from mavlink_proxy.MAVP2P import MAVP2P
from mavlink_proxy.MAVProxy import MAVProxy
from typedefs import EndpointType

_, slave_port = pty.openpty()
serial_port_name = os.ttyname(slave_port)


@pytest.fixture
def valid_output_endpoints() -> Set[Endpoint]:
    return {
        Endpoint(
            name="Test endpoint 1",
            owner="pytest",
            connection_type=EndpointType.UDPServer,
            place="0.0.0.0",
            argument=14551,
        ),
        Endpoint(
            name="Test endpoint 2",
            owner="pytest",
            connection_type=EndpointType.UDPClient,
            place="0.0.0.0",
            argument=14552,
        ),
        Endpoint(
            name="Test endpoint 3",
            owner="pytest",
            connection_type=EndpointType.TCPServer,
            place="0.0.0.0",
            argument=14553,
        ),
        Endpoint(
            name="Test endpoint 4",
            owner="pytest",
            connection_type=EndpointType.TCPClient,
            place="0.0.0.0",
            argument=14554,
        ),
        Endpoint(
            name="Test endpoint 5",
            owner="pytest",
            connection_type=EndpointType.Serial,
            place=serial_port_name,
            argument=57600,
        ),
    }


@pytest.fixture
def valid_master_endpoints() -> Set[Endpoint]:
    return {
        Endpoint(
            name="Master endpoint 1",
            owner="pytest",
            connection_type=EndpointType.UDPServer,
            place="0.0.0.0",
            argument=14550,
        ),
        Endpoint(
            name="Master endpoint 2",
            owner="pytest",
            connection_type=EndpointType.UDPClient,
            place="0.0.0.0",
            argument=14550,
        ),
        Endpoint(
            name="Master endpoint 3",
            owner="pytest",
            connection_type=EndpointType.TCPServer,
            place="0.0.0.0",
            argument=14550,
        ),
        Endpoint(
            name="Master endpoint 4",
            owner="pytest",
            connection_type=EndpointType.TCPClient,
            place="0.0.0.0",
            argument=14550,
        ),
        Endpoint(
            name="Master endpoint 5",
            owner="pytest",
            connection_type=EndpointType.Serial,
            place=serial_port_name,
            argument=115200,
        ),
    }


def test_endpoint() -> None:
    endpoint = Endpoint(
        name="Test endpoint", owner="pytest", connection_type=EndpointType.UDPClient, place="0.0.0.0", argument=14550
    )
    assert endpoint.name == "Test endpoint", "Name does not match."
    assert endpoint.owner == "pytest", "Owner does not match."
    assert endpoint.persistent is False, "Persistent does not match."
    assert endpoint.protected is False, "Protected does not match."
    assert endpoint.connection_type == EndpointType.UDPClient, "Connection type does not match."
    assert endpoint.place == "0.0.0.0", "Connection place does not match."
    assert endpoint.argument == 14550, "Connection argument does not match."
    assert str(endpoint) == "udpout:0.0.0.0:14550", "Connection string does not match."
    assert endpoint.as_dict() == {
        "__pydantic_initialised__": True,
        "name": "Test endpoint",
        "owner": "pytest",
        "connection_type": EndpointType.UDPClient.value,
        "place": "0.0.0.0",
        "argument": 14550,
        "persistent": False,
        "protected": False,
        "enabled": True,
        "overwrite_settings": False,
    }, "Endpoint dict does not match."


def test_endpoint_validators() -> None:
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": EndpointType.UDPServer, "place": "0.0.0.0", "argument": -30})
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": EndpointType.UDPServer, "place": "42", "argument": 14555})
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint(
            {"connection_type": EndpointType.Serial, "place": "dev/autopilot", "argument": 115200}
        )
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint(
            {"connection_type": EndpointType.Serial, "place": serial_port_name, "argument": 100000}
        )
    with pytest.raises(ValueError):
        Endpoint.is_mavlink_endpoint({"connection_type": "potato", "place": serial_port_name, "argument": 100})


@pytest.mark.skip(
    reason="MavProxy tests are failling for several endpoint combinations. Since it's not being used \
    and it's not a priority to support it, they are being temporarily disabled."
)
@pytest.mark.asyncio
async def serial_test_mavproxy(valid_output_endpoints: Set[Endpoint], valid_master_endpoints: Set[Endpoint]) -> None:
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
    await run_common_routing_tests(
        mavproxy, allowed_output_types, allowed_master_types, valid_output_endpoints, valid_master_endpoints
    )


async def serial_test_mavlink_router(
    valid_output_endpoints: Set[Endpoint], valid_master_endpoints: Set[Endpoint]
) -> None:
    if not MAVLinkRouter.is_ok():
        warnings.warn("Failed to test MAVLinkRouter service", UserWarning)
        return

    assert AbstractRouter.get_interface("MAVLinkRouter"), "Failed to find interface MAVLinkRouter"

    mavlink_router = MAVLinkRouter()
    assert mavlink_router.name() == "MAVLinkRouter", "Name does not match."
    assert re.search(r"\d+", str(mavlink_router.version())) is not None, "Version does not follow pattern."

    allowed_output_types = [
        EndpointType.UDPServer,
        EndpointType.UDPClient,
        EndpointType.TCPServer,
        EndpointType.TCPClient,
    ]
    allowed_master_types = [
        EndpointType.UDPServer,
        EndpointType.TCPServer,
        EndpointType.TCPClient,
        EndpointType.Serial,
    ]
    await run_common_routing_tests(
        mavlink_router, allowed_output_types, allowed_master_types, valid_output_endpoints, valid_master_endpoints
    )


@pytest.mark.asyncio
async def serial_test_mavp2p(valid_output_endpoints: Set[Endpoint], valid_master_endpoints: Set[Endpoint]) -> None:
    if not MAVP2P.is_ok():
        warnings.warn("Failed to test MAVP2P service", UserWarning)
        return

    assert AbstractRouter.get_interface("MAVP2P"), "Failed to find interface MAVP2P"

    mavp2p = MAVP2P()
    assert mavp2p.name() == "MAVP2P", "Name does not match."
    assert re.search(r"\d+.\d+.\d+", str(mavp2p.version())) is not None, "Version does not follow pattern."

    allowed_output_types = [
        EndpointType.UDPServer,
        EndpointType.UDPClient,
        EndpointType.TCPServer,
        EndpointType.TCPClient,
        EndpointType.Serial,
    ]
    allowed_master_types = allowed_output_types
    await run_common_routing_tests(
        mavp2p, allowed_output_types, allowed_master_types, valid_output_endpoints, valid_master_endpoints
    )


@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_router(valid_output_endpoints: Set[Endpoint], valid_master_endpoints: Set[Endpoint]) -> None:
    for router in [serial_test_mavlink_router, serial_test_mavp2p]:
        await router(valid_output_endpoints, valid_master_endpoints)


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def run_common_routing_tests(
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

    allowed_master_endpoints = set(
        filter(lambda endpoint: endpoint.connection_type in allowed_master_types, master_endpoints)
    )

    unallowed_output_endpoints = output_endpoints.difference(allowed_output_endpoints)
    unallowed_master_endpoints = master_endpoints.difference(allowed_master_endpoints)

    for endpoint in unallowed_output_endpoints:
        with pytest.raises(ValueError):
            router.add_endpoint(endpoint)

    for endpoint in unallowed_master_endpoints:
        with pytest.raises(ValueError):
            await router.start(endpoint)

    async def test_endpoint_combinations(master_endpoints: Set[Endpoint], output_endpoints: List[Endpoint]) -> None:
        for master_endpoint in master_endpoints:
            router.clear_endpoints()

            for output_endpoint in output_endpoints:
                router.add_endpoint(output_endpoint)
            assert set(router.endpoints()) == set(output_endpoints), "Endpoint list does not match."

            await router.start(master_endpoint)
            assert await router.is_running(), f"{router.name()} is not running after start."
            await router.exit()
            while await router.is_running():
                pass
            assert not await router.is_running(), f"{router.name()} is not stopping after exit."

    types_order = {
        EndpointType.UDPServer: 0,
        EndpointType.UDPClient: 1,
        EndpointType.TCPServer: 2,
        EndpointType.TCPClient: 3,
        EndpointType.Serial: 4,
    }
    sorted_endpoints = sorted(allowed_output_endpoints, key=lambda e: types_order[e.connection_type])  # type: ignore

    # Test endpoint combinationsin two orders: regular and reversed
    await test_endpoint_combinations(allowed_master_endpoints, sorted_endpoints)
    await test_endpoint_combinations(allowed_master_endpoints, sorted_endpoints[::-1])
