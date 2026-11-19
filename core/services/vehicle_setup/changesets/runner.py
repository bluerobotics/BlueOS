import asyncio

# Shared by changeset applies and calibration sessions, so only one of them writes to the vehicle at a time
VEHICLE_WRITE_LOCK = asyncio.Lock()
