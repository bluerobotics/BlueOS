# This file holds default configs for mavlink_comm

from commonwealth.mavlink_comm.typedefs import MavDataStream, MavDataStreamIntervalRequest

# Default data streams requested when a vehicle is connected
DEFAULT_DATA_STREAMS_CONFIG = [
    MavDataStreamIntervalRequest(MavDataStream.MAV_DATA_STREAM_RAW_SENSORS, 500000),
    MavDataStreamIntervalRequest(MavDataStream.MAV_DATA_STREAM_EXTENDED_STATUS, 500000),
    MavDataStreamIntervalRequest(MavDataStream.MAV_DATA_STREAM_RC_CHANNELS, 500000),
    MavDataStreamIntervalRequest(MavDataStream.MAV_DATA_STREAM_POSITION, 333333),
    MavDataStreamIntervalRequest(MavDataStream.MAV_DATA_STREAM_EXTRA1, 50000),
    MavDataStreamIntervalRequest(MavDataStream.MAV_DATA_STREAM_EXTRA2, 100000),
    MavDataStreamIntervalRequest(MavDataStream.MAV_DATA_STREAM_EXTRA3, 333333),
]
