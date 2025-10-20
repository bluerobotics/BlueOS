import subprocess

from loguru import logger


def is_port_in_use(device_path: str) -> bool:
    """
    Check if a serial port is already in use by another process.

    Tries to open the port as the 'blueos' user. Since we run as root,
    if blueos can't open it (and it's not a permission error), the port is in use.

    Args:
        device_path: Path to the serial device (e.g., '/dev/ttyUSB0')

    Returns:
        True if the port is in use by another process, False otherwise
    """
    try:
        # Try to open the device with exec as blueos user
        # Exit code 2 means "Device or resource busy" (port is in use)
        result = subprocess.run(
            ["su", "-", "blueos", "-c", f"exec 3<> {device_path} 2>&1"],
            capture_output=True,
            timeout=1,
            shell=False,
            check=False,
        )

        # Exit code 2 indicates the port is in use
        if result.returncode == 2:
            logger.debug(f"Port {device_path} is in use by another process")
            return True

        return False
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout checking port {device_path}")
        return True
    except Exception as error:
        logger.debug(f"Could not check port {device_path}: {error}")
        return False
