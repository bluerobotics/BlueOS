"""
    TODO: Update to pydantic v2 to get rid of this sad file.
    
    This is a temporary shin to be replaced by pydantic IPvAnyAddress,
    IPvAnyInterface and IPvAnyNetwork. This is needed because the Routes code
    requires the differentiation embedded in those types (like that
    '192.168.2.1' can't be used in place of a '192.168.2.0/24'). Yes, we
    should be using the pydantic types in the Route, but our current pydantic
    version doeesn't allow us to serialize the underlying types, so we must
    keep them as 'str' in the Route properties while using these weak shins
    in the manager implementations. This whole file should will be deleted
    once we update to pydantic v2. The necessary glue between the Route props
    and the manager code is spread both in typedefs and in the manager code,
    like using str(ip_address('192.168.2.1')) when instantiating a Route,
    and accessing Route.destination_parsed instead of Route.destiantion --
    all quick things to adjust once the pydantic update takes place.
"""

from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
    ip_address,
    ip_interface,
    ip_network,
)
from typing import Any, Union


class IPvAnyAddress:
    def __init__(self, ip: Union[str, IPv4Address, IPv6Address]):
        self._value: Union[IPv4Address, IPv6Address] = ip_address(ip)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"IPvAnyAddress('{self._value}')"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, IPvAnyAddress):
            return self._value == other._value
        return self._value == ip_address(other)

    def __json__(self) -> str:
        return str(self)

    @property
    def version(self) -> int:
        return ip_address(self._value).version


class IPvAnyInterface:
    def __init__(self, ip: Union[str, IPv4Interface, IPv6Interface]):
        self._value: Union[IPv4Interface, IPv6Interface] = ip_interface(ip)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"IPvAnyInterface('{self._value}')"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, IPvAnyInterface):
            return self._value == other._value
        return self._value == ip_interface(other)

    def __json__(self) -> str:
        return str(self)

    @property
    def version(self) -> int:
        return ip_interface(self._value).version


class IPvAnyNetwork:
    def __init__(self, ip: Union[str, IPv4Network, IPv6Network]):
        self._value: Union[IPv4Network, IPv6Network] = ip_network(ip)

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"IPvAnyNetwork('{self._value}')"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, IPvAnyNetwork):
            return self._value == other._value
        return self._value == ip_network(other)

    def __json__(self) -> str:
        return str(self)

    @property
    def version(self) -> int:
        return ip_network(self._value).version
