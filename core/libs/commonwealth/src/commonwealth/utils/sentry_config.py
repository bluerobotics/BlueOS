import os
import re
from typing import Any, Dict, Optional

import sentry_sdk


def _get_sentry_config() -> Optional[Dict[str, Any]]:
    """
    Retrieves the Sentry configuration for the BlueOS backend project

    Returns:
        Optional[ClientConstructor]: The Sentry configuration if valid, otherwise None.
    """

    SENTRY_PROJECT = "BlueOS"
    SENTRY_DSN = "https://d93d1be8ddb7d5e1f45fb1eeca287eac@o4507696465707008.ingest.us.sentry.io/4509446521683968"
    VALID_TAG_PATTERN = r"^\d+\.\d+\.\d+-\d+-g[0-9a-f]{7,}$"

    git_describe_tag = os.environ.get("GIT_DESCRIBE_TAGS")

    if not git_describe_tag or not re.match(VALID_TAG_PATTERN, git_describe_tag):
        return None

    release = f"{SENTRY_PROJECT}@{git_describe_tag}".replace("tags/", "").replace("/", ":")

    return {
        "dsn": SENTRY_DSN,
        "release": release,
        "traces_sample_rate": 1.0,
        "trace_propagation_targets": [],
        "send_default_pii": True,
    }


def init_sentry(name: Optional[str] = None) -> None:
    sentry_config = _get_sentry_config()
    if sentry_config:
        sentry_sdk.init(server_name=name, **sentry_config)


async def init_sentry_async(name: Optional[str] = None) -> None:
    """
    Initializes Sentry when used in an async context.

    Per sentry's documentation, when using async context, the init function should be called within an async function.
    https://docs.sentry.io/platforms/python/#configure
    """
    sentry_config = _get_sentry_config()
    if sentry_config:
        sentry_sdk.init(server_name=name, **sentry_config)
