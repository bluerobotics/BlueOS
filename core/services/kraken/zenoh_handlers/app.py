from commonwealth.utils.zenoh_helper import ZenohRouter, ZenohSession
from config import SERVICE_NAME
from zenoh_handlers.container_handler import ContainerHandlers

session = ZenohSession(SERVICE_NAME)
router = ZenohRouter(SERVICE_NAME)

# Container
container_handlers = ContainerHandlers(router)
container_handlers.register_queryables()