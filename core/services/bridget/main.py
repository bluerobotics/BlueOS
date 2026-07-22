from pathlib import Path

from adapters import (
    BridgesLibRuntime,
    Linux2RestSerialCatalog,
    PydanticBridgeSettingsStore,
)
from commonwealth.service.runtime import Runtime
from commonwealth.service.service import Service
from routes import build_bridget_router
from service import BridgetState

SERVICE_NAME = "bridget"
# We use userdata because our regular settings folder is under /root, which regular users
# don't have access to.
USERDATA = Path("/usr/blueos/userdata/")


def build_service() -> Service[BridgetState]:
    catalog = Linux2RestSerialCatalog()
    return (
        Service.builder(SERVICE_NAME)
        .state(
            BridgetState(
                BridgesLibRuntime(),
                PydanticBridgeSettingsStore(USERDATA / "settings" / "bridget"),
            )
        )
        .routes(lambda service: build_bridget_router(service, catalog))
        .http(
            27353,
            title="Bridget API",
            description="Bridget is a BlueOS service responsible for managing 'bridges' links.",
        )
        .logging()
        .build()
    )


def main() -> None:
    Runtime().sentry().add_service(build_service()).run()


if __name__ == "__main__":
    main()
