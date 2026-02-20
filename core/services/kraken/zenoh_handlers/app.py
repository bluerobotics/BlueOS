from commonwealth.utils.zenoh_helper import ZenohRouter, ZenohSession
from config import SERVICE_NAME
from zenoh_handlers.extension_handler import ExtensionHandlers

session = ZenohSession(SERVICE_NAME)
router = ZenohRouter(SERVICE_NAME)

# Extension
extension_handlers = ExtensionHandlers(router)
extension_handlers.register_queryables()
