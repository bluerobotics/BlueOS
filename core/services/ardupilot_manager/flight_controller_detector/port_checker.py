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
        check_script = f"import serial; serial.Serial('{device_path}', 115200, timeout=0.1).close()"
        result = subprocess.run(
            ["su", "-", "blueos", "-c", f'python3 -c "{check_script}"'],
            capture_output=True,
            timeout=2,
            check=True,
        )
        if result.returncode != 0:
            # If it's not a permission error, the port is in use
            if b"Permission denied" not in result.stderr and b"PermissionError" not in result.stderr:
                logger.debug(f"Port {device_path} is in use by another process")
                return True
        return False
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout checking port {device_path}")
        return True
    except Exception as error:
        logger.debug(f"Could not check port {device_path}: {error}")
        return False
