from pathlib import Path

import appdirs
from commonwealth.service.runtime import Runtime
from commonwealth.service.service import Service
from database import Database
from routes import build_bag_router
from service import BagOfHoldingState

SERVICE_NAME = "bag-of-holding"


def build_service() -> Service[BagOfHoldingState]:
    store = Database(Path(appdirs.user_config_dir(SERVICE_NAME, "db.json")))
    return (
        Service.builder(SERVICE_NAME)
        .state(BagOfHoldingState(store))
        .routes(build_bag_router)
        .http(
            9101,
            title="Bag of Holding API",
            description=(
                "Bag of Holding implements a FastAPI service with versioning that provides a simple key-value"
                "storage API, enabling the user to store and retrieve data as JSON objects through HTTP requests."
            ),
        )
        .logging()
        .build()
    )


def main() -> None:
    Runtime().sentry().add_service(build_service()).run()


if __name__ == "__main__":

    main()
