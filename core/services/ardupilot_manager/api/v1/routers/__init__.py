# pylint: disable=W0406
from .eeprom import eeprom_router_v1
from .endpoints import endpoints_router_v1
from .index import index_router_v1

__all__ = ["eeprom_router_v1", "endpoints_router_v1", "index_router_v1"]
