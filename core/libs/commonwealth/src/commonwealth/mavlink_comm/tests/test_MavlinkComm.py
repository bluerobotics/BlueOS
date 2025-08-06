import os
from unittest.mock import patch

import pytest

from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger


class TestMavlinkMessenger:
    """Test cases for MavlinkMessenger class."""

    def test_init_default_values(self) -> None:
        """Test initialization with default values."""
        with patch.dict(os.environ, {"MAV_SYSTEM_ID": "1", "MAV_COMPONENT_ID_ONBOARD_COMPUTER4": "194"}):
            messenger = MavlinkMessenger()
            assert messenger.system_id == 1
            assert messenger.component_id == 194
            assert messenger.sequence == 0
            assert messenger.m2r_address == "localhost:6040"

    def test_set_system_id(self) -> None:
        """Test setting system ID."""
        messenger = MavlinkMessenger()
        messenger.set_system_id(10)
        assert messenger.system_id == 10

    def test_set_component_id(self) -> None:
        """Test setting component ID."""
        messenger = MavlinkMessenger()
        messenger.set_component_id(200)
        assert messenger.component_id == 200

    def test_set_sequence(self) -> None:
        """Test setting sequence."""
        messenger = MavlinkMessenger()
        messenger.set_sequence(5)
        assert messenger.sequence == 5

    def test_set_m2r_address_valid(self) -> None:
        """Test setting valid m2r address."""
        messenger = MavlinkMessenger()
        messenger.set_m2r_address("192.168.1.100:8080")
        assert messenger.m2r_address == "192.168.1.100:8080"

    def test_set_m2r_address_invalid(self) -> None:
        """Test setting invalid m2r address."""
        messenger = MavlinkMessenger()
        with pytest.raises(
            ValueError, match="Invalid address. Valid address should follow the format 'localhost:6040'."
        ):
            messenger.set_m2r_address("invalid_address")

    def test_m2r_rest_url_property(self) -> None:
        """Test m2r_rest_url property."""
        messenger = MavlinkMessenger()
        assert messenger.m2r_rest_url == "http://localhost:6040/mavlink"
