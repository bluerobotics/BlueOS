#! /usr/bin/env python3
import argparse
import asyncio
import json
import logging
import math
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import appdirs
import zenoh
from commonwealth.utils.apis import GenericErrorHandlingRoute
from commonwealth.utils.logs import InterceptHandler, init_logger
from commonwealth.utils.sentry_config import init_sentry_async
from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi_versioning import VersionedFastAPI, version, versioned_api_route
from loguru import logger
from pydantic import BaseModel, Field
from uvicorn import Config, Server

SERVICE_NAME = "odometer"
DEFAULT_DATA_DIR = Path(appdirs.user_data_dir(SERVICE_NAME, "blueos"))
DEFAULT_STATE_PATH = DEFAULT_DATA_DIR / "odometer.json"
DEFAULT_KEY_EXPR = "mavlink/**/GLOBAL_POSITION_INT"

parser = argparse.ArgumentParser(description="Odometer service using Zenoh")
parser.add_argument(
    "--port",
    type=int,
    default=9127,
    help="Port to run the HTTP server on (default: 9127).",
)
parser.add_argument(
    "--state-path",
    type=str,
    default=os.environ.get("ODOMETER_STATE_PATH", str(DEFAULT_STATE_PATH)),
    help="Path to the odometer JSON state file.",
)
parser.add_argument(
    "--zenoh-config",
    type=str,
    default=os.environ.get("ODOMETER_ZENOH_CONFIG"),
    help="Optional path to a Zenoh JSON/JSON5 configuration file.",
)
parser.add_argument(
    "--key-expr",
    type=str,
    default=os.environ.get("ODOMETER_KEY_EXPR", DEFAULT_KEY_EXPR),
    help="Zenoh key expression to subscribe to for position updates.",
)
parser.add_argument(
    "--persist-interval",
    type=float,
    default=float(os.environ.get("ODOMETER_PERSIST_SECONDS", "5")),
    help="Interval in seconds to persist odometer state to disk.",
)

args = parser.parse_args()

logging.basicConfig(handlers=[InterceptHandler()], level=0)
init_logger(SERVICE_NAME)

EARTH_RADIUS_M = 6_371_000.0


class Position(BaseModel):
    lat_deg: float = Field(..., description="Latitude in degrees.")
    lon_deg: float = Field(..., description="Longitude in degrees.")
    alt_m: Optional[float] = Field(None, description="Altitude in meters if available.")
    time_boot_ms: Optional[int] = Field(None, description="ArduPilot boot timestamp in milliseconds.")


class OdometerState(BaseModel):
    total_distance_m: float = Field(0, ge=0, description="Total distance traveled in meters.")
    last_position: Optional[Position] = None
    sample_count: int = Field(0, ge=0, description="Number of processed position samples.")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class _RawState:
    total_distance_m: float
    last_position: Optional[dict[str, Any]]
    sample_count: int
    updated_at: str


def _haversine_distance_m(pos_a: Position, pos_b: Position) -> float:
    """Compute great-circle distance between two positions in meters."""
    lat1, lon1, lat2, lon2 = map(math.radians, (pos_a.lat_deg, pos_a.lon_deg, pos_b.lat_deg, pos_b.lon_deg))
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a_term = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c_term = 2 * math.asin(min(1.0, math.sqrt(a_term)))
    return EARTH_RADIUS_M * c_term


class OdometerService:
    def __init__(
        self,
        state_path: Path,
        key_expr: str,
        zenoh_config_path: Optional[Path],
        persist_interval_seconds: float,
    ) -> None:
        self.state_path = state_path
        self.key_expr = key_expr
        self.zenoh_config_path = zenoh_config_path
        self.persist_interval_seconds = max(1.0, persist_interval_seconds)

        self._state: OdometerState = OdometerState()
        self._lock = asyncio.Lock()
        self._session: Optional[zenoh.Session] = None
        self._subscriber: Optional[zenoh.Subscriber] = None
        self._persist_task: Optional[asyncio.Task[None]] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        logger.info(
            "Starting odometer service - state_path=%s key_expr=%s zenoh_config=%s",
            self.state_path,
            self.key_expr,
            self.zenoh_config_path,
        )
        self._loop = asyncio.get_running_loop()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = await asyncio.to_thread(self._load_state)

        self._session = await asyncio.to_thread(self._open_session)
        try:
            self._subscriber = self._session.declare_subscriber(self.key_expr, self._on_sample)
        except Exception as exc:
            logger.exception("Failed to declare Zenoh subscriber")
            await asyncio.to_thread(self._session.close)
            raise exc

        self._persist_task = asyncio.create_task(self._persist_state_periodically())
        logger.info("Odometer service started")

    async def stop(self) -> None:
        logger.info("Stopping odometer service")
        if self._persist_task:
            self._persist_task.cancel()
            try:
                await self._persist_task
            except asyncio.CancelledError:
                pass

        if self._subscriber:
            await asyncio.to_thread(self._subscriber.undeclare)
        if self._session:
            await asyncio.to_thread(self._session.close)
        await self.persist_state()
        logger.info("Odometer service stopped")

    def _open_session(self) -> zenoh.Session:
        config = (
            zenoh.Config.from_file(str(self.zenoh_config_path))
            if self.zenoh_config_path is not None
            else zenoh.Config()
        )
        if self.zenoh_config_path is None:
            config.insert_json5("mode", json.dumps("client"))
            config.insert_json5("connect/endpoints", json.dumps(["tcp/127.0.0.1:7447"]))
            config.insert_json5("metadata", json.dumps({"name": SERVICE_NAME}))
        return zenoh.open(config)

    def _load_state(self) -> OdometerState:
        if not self.state_path.exists():
            return OdometerState()
        try:
            with self.state_path.open("r", encoding="utf-8") as state_file:
                payload: _RawState = _RawState(**json.load(state_file))
            last_position = Position(**payload.last_position) if payload.last_position else None
            return OdometerState(
                total_distance_m=payload.total_distance_m,
                last_position=last_position,
                sample_count=payload.sample_count,
                updated_at=datetime.fromisoformat(payload.updated_at),
            )
        except Exception:
            logger.exception("Failed to load odometer state from %s, starting fresh", self.state_path)
            return OdometerState()

    def _on_sample(self, sample: zenoh.Sample) -> None:
        if self._loop is None:
            logger.debug("Ignoring sample before event loop is ready")
            return

        try:
            payload_text = sample.payload.to_string()
            payload_json = json.loads(payload_text)
            message = payload_json.get("message", {})
            lat_raw = message.get("lat")
            lon_raw = message.get("lon")
            if lat_raw is None or lon_raw is None:
                return
            lat_deg = float(lat_raw) / 1e7
            lon_deg = float(lon_raw) / 1e7
            alt_raw = message.get("alt")
            alt_m = float(alt_raw) / 1000 if isinstance(alt_raw, (int, float)) else None
            time_boot_ms = message.get("time_boot_ms")
            position = Position(lat_deg=lat_deg, lon_deg=lon_deg, alt_m=alt_m, time_boot_ms=time_boot_ms)

            asyncio.run_coroutine_threadsafe(self.update_position(position), self._loop)
        except json.JSONDecodeError:
            logger.debug("Received non-JSON sample on %s: %s", self.key_expr, sample)
        except Exception:
            logger.exception("Failed to handle Zenoh sample")

    async def update_position(self, position: Position) -> None:
        async with self._lock:
            if self._state.last_position:
                try:
                    delta_m = _haversine_distance_m(self._state.last_position, position)
                except ValueError:
                    delta_m = 0
                if math.isfinite(delta_m) and delta_m >= 0:
                    self._state.total_distance_m += delta_m
            self._state.last_position = position
            self._state.sample_count += 1
            self._state.updated_at = datetime.now(timezone.utc)

    async def get_state(self) -> OdometerState:
        async with self._lock:
            return OdometerState.parse_obj(self._state.dict())

    async def reset(self) -> OdometerState:
        async with self._lock:
            self._state = OdometerState()
        await self.persist_state()
        return await self.get_state()

    def _serialize_state(self) -> _RawState:
        return _RawState(
            total_distance_m=self._state.total_distance_m,
            last_position=self._state.last_position.dict() if self._state.last_position else None,
            sample_count=self._state.sample_count,
            updated_at=self._state.updated_at.isoformat(),
        )

    async def persist_state(self) -> None:
        async with self._lock:
            serialized = asdict(self._serialize_state())
        await asyncio.to_thread(self._write_state, serialized)

    def _write_state(self, serialized: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as state_file:
            json.dump(serialized, state_file, indent=2)

    async def _persist_state_periodically(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.persist_interval_seconds)
                await self.persist_state()
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Failed during periodic persistence loop iteration")


state_path = Path(args.state_path)
zenoh_config_path = Path(args.zenoh_config) if args.zenoh_config else None
odometer_service = OdometerService(
    state_path=state_path,
    key_expr=args.key_expr,
    zenoh_config_path=zenoh_config_path,
    persist_interval_seconds=args.persist_interval,
)


def get_odometer_service() -> OdometerService:
    return odometer_service


api_router = APIRouter(
    prefix="/odometer",
    tags=["odometer_v1"],
    route_class=versioned_api_route(1, 0),
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"},
    },
)


@api_router.get("/", response_model=OdometerState, summary="Get odometer state.")
@version(1, 0)
async def read_state(service: OdometerService = Depends(get_odometer_service)) -> OdometerState:
    return await service.get_state()


class ResetResponse(BaseModel):
    status: str = Field("reset", description="Status message for reset operation.")
    state: OdometerState


@api_router.post("/reset", response_model=ResetResponse, summary="Reset odometer.")
@version(1, 0)
async def reset_state(service: OdometerService = Depends(get_odometer_service)) -> ResetResponse:
    state = await service.reset()
    return ResetResponse(state=state)


fastapi_app = FastAPI(
    title="Odometer API",
    description="Accumulate distance traveled from MAVLink positions received via Zenoh.",
)
fastapi_app.router.route_class = GenericErrorHandlingRoute
fastapi_app.include_router(api_router)


@fastapi_app.get("/", include_in_schema=False)
async def root() -> HTMLResponse:
    return HTMLResponse("<html><head><title>Odometer</title></head></html>")

@fastapi_app.on_event("startup")
async def on_startup() -> None:
    await init_sentry_async(SERVICE_NAME)
    try:
        await odometer_service.start()
    except Exception as exc:
        logger.exception("Failed to start odometer service")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@fastapi_app.on_event("shutdown")
async def on_shutdown() -> None:
    await odometer_service.stop()


app = VersionedFastAPI(fastapi_app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)


async def main() -> None:
    config = Config(app=app, host="0.0.0.0", port=args.port, log_config=None)
    server = Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
