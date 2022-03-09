import os


def is_running_as_root() -> bool:
    return os.geteuid() == 0
