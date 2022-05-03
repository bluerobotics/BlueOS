import pynmea2
import pytest
from nmeasim.simulator import Simulator
from pynmea2.nmea_utils import dm_to_sd

from nmea_injector.exceptions import UnsupportedSentenceType
from nmea_injector.MavlinkNMEA import parse_mavlink_from_sentence


class TestMavlinkNMEA:
    ALTITUDE = -13
    HDOP = 3.1
    NUM_SATS = 14
    # Latitude and longitude values represented as DMS (degrees, minutes, seconds)
    LAT_DMS = "4332.69262"
    LON_DMS = "17235.48549"
    # Latitude and longitude values represented as float degrees
    LAT_FD = dm_to_sd(LAT_DMS)  # 48.1265044
    LON_FD = dm_to_sd(LON_DMS)  # 11.6593258

    sim = Simulator()
    with sim.lock:
        sim.gps.output = ("GGA", "GLL", "RMC")
        sim.gps.lat = LAT_FD
        sim.gps.lon = LON_FD
        sim.gps.altitude = ALTITUDE
        sim.gps.hdop = HDOP
        sim.gps.num_sats = NUM_SATS
    ZDA_TEST_MSG = "$GPZDA,172809.456,12,07,1996,00,00*57"
    GNS_TEST_MSG = f"$GNGNS,014035.00,{LAT_DMS},N,{LON_DMS},E,RR,{NUM_SATS},{HDOP},25.63,11.24,,U,*18"

    supported_nmea_sentences = [pynmea2.parse(msg) for msg in list(sim.get_output(1)) + [GNS_TEST_MSG]]
    unsupported_nmea_sentences = [pynmea2.parse(msg) for msg in [ZDA_TEST_MSG]]

    def test_supported_sentence_types(self) -> None:
        """Tests if supported sentence types are indeed supported, and if other types raise.

        It is important to notice that GNS sentence type is not supported by the nmeasim library, and thus we currently
        don't test it here.
        """
        for sentence in self.supported_nmea_sentences:
            parse_mavlink_from_sentence(sentence)

        for sentence in self.unsupported_nmea_sentences:
            # NMEA-Injector does not support ZDA sentence type, thus it will raise
            with pytest.raises(UnsupportedSentenceType):
                parse_mavlink_from_sentence(sentence)

    def test_lat_lon(self) -> None:
        """Tests if latitude and longitude values parsed to Mavlink package are the correct ones."""
        for sentence in self.supported_nmea_sentences:
            mavlink_data = parse_mavlink_from_sentence(sentence)
            # Mavlink GPS input uses "degE7" unit, thus we need to transform the original degree value to do the check
            assert mavlink_data.lat == pytest.approx(self.LAT_FD * 1e7)
            assert mavlink_data.lon == pytest.approx(self.LON_FD * 1e7)

    def test_hdop(self) -> None:
        """Tests if 'hdop' field is working correctly for all sentence types that support it."""
        types_support_hdop = ["GGA", "GNS"]
        for sentence in [msg for msg in self.supported_nmea_sentences if msg.sentence_type in types_support_hdop]:
            mavlink_data = parse_mavlink_from_sentence(sentence)
            assert mavlink_data.hdop == self.HDOP

    def test_num_sats(self) -> None:
        """Tests if 'satellites_visible' field is working correctly for all sentence types that support it."""
        types_support_sats = ["GGA", "GNS"]
        for sentence in [msg for msg in self.supported_nmea_sentences if msg.sentence_type in types_support_sats]:
            mavlink_data = parse_mavlink_from_sentence(sentence)
            assert mavlink_data.satellites_visible == self.NUM_SATS

    def test_alt(self) -> None:
        """Tests if 'alt' field is working correctly for all sentence types that support it."""
        types_support_alt = ["GGA"]
        for sentence in [msg for msg in self.supported_nmea_sentences if msg.sentence_type in types_support_alt]:
            mavlink_data = parse_mavlink_from_sentence(sentence)
            assert mavlink_data.alt == self.ALTITUDE
