import os

CORE = os.environ.get("E2E_CORE_IMAGE", "bluerobotics/blueos-core:master")
BOOTSTRAP = os.environ.get("E2E_BOOTSTRAP_IMAGE", "bluerobotics/blueos-bootstrap:master")
