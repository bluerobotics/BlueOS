import logging

from blueos.core import BlueOS
from utils.retry import wait_until

logger = logging.getLogger(__name__)


def test_sitl(blueos: BlueOS) -> None:
    boards = {board["name"]: board for board in blueos.ardupilot.available_boards()}
    assert "SITL" in boards, f"SITL is not an available board: {list(boards)}"

    logger.info("starting sitl")
    blueos.ardupilot.set_board(boards["SITL"])
    try:
        board = blueos.ardupilot.board()
        assert board is not None and board["name"] == "SITL"

        def running() -> None:
            assert blueos.ardupilot.vehicle_type() == "Submarine"

        wait_until(running, 300, interval=5, errors=(AssertionError, RuntimeError))
        logger.info("sitl is sending heartbeats")
    finally:
        blueos.ardupilot.stop()
