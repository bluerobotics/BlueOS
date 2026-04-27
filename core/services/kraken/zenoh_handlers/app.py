from commonwealth.utils.zenoh_helper import ZenohRouter, ZenohSession
from config import SERVICE_NAME
from zenoh_handlers.container_handler import ContainerHandlers
from zenoh_handlers.extension_handler import ExtensionHandlers

session = ZenohSession(SERVICE_NAME)
router = ZenohRouter(SERVICE_NAME)

# Extension
extension_handlers = ExtensionHandlers(router)
extension_handlers.register_queryables()

# Container
container_handlers = ContainerHandlers(router)
container_handlers.register_queryables()
