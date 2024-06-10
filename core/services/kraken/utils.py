import psutil


def has_enough_disk_space(path: str = "/", required_bytes: int = 2**30) -> bool:
    try:
        free_space = psutil.disk_usage(path).free
        # Default is to require 1GB (2**30)
        return bool(free_space > required_bytes)
    except FileNotFoundError:
        return False
