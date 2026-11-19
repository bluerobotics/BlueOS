import asyncio
from contextlib import suppress
from typing import Any, Dict, Optional, Protocol, Set

from fastapi import WebSocket
from loguru import logger
from pydantic import BaseModel, ValidationError

Outbox = asyncio.Queue  # of {"topic": ..., "payload": ...}, one per websocket
# A client this far behind is dropped; it loses nothing, since it resubscribes and gets the current values again
OUTBOX_SIZE = 100


class Bus(Protocol):
    def publish(self, name: str, payload: Any) -> None:
        ...


class Subscription(BaseModel):
    subscribe: Optional[str] = None
    unsubscribe: Optional[str] = None


class HttpBus:
    """Keeps the last value of every state for GET and late subscribers, and fans publishes out to websockets."""

    def __init__(self, service: str) -> None:
        self.prefix = f"{service}/state/"
        self.values: Dict[str, Any] = {}
        # Exact topics only, no wildcards
        self.subscribers: Dict[str, Set["Outbox[Dict[str, Any]]"]] = {}
        self.dropped: Dict["Outbox[Dict[str, Any]]", asyncio.Event] = {}

    def topic(self, name: str) -> str:
        return f"{self.prefix}{name}"

    def publish(self, name: str, payload: Any) -> None:
        topic = self.topic(name)
        self.values[topic] = payload
        for outbox in list(self.subscribers.get(topic, set())):
            self.send(outbox, {"topic": topic, "payload": payload})

    def value(self, name: str) -> Any:
        return self.values[self.topic(name)]

    def subscribe(self, topic: str, outbox: "Outbox[Dict[str, Any]]") -> None:
        self.subscribers.setdefault(topic, set()).add(outbox)
        if topic in self.values:
            self.send(outbox, {"topic": topic, "payload": self.values[topic]})

    def unsubscribe(self, topic: str, outbox: "Outbox[Dict[str, Any]]") -> None:
        subscribers = self.subscribers.get(topic, set())
        subscribers.discard(outbox)
        if not subscribers:
            self.subscribers.pop(topic, None)

    def send(self, outbox: "Outbox[Dict[str, Any]]", message: Dict[str, Any]) -> None:
        try:
            outbox.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Dropping a websocket client that stopped reading")
            for topic in list(self.subscribers):
                self.unsubscribe(topic, outbox)
            if outbox in self.dropped:
                self.dropped[outbox].set()

    async def serve(self, websocket: WebSocket) -> None:
        await websocket.accept()
        outbox: "Outbox[Dict[str, Any]]" = asyncio.Queue(OUTBOX_SIZE)
        dropped = self.dropped[outbox] = asyncio.Event()
        topics: Set[str] = set()
        tasks = {
            asyncio.create_task(self.read(websocket, outbox, topics)),
            asyncio.create_task(self.write(websocket, outbox)),
            asyncio.create_task(dropped.wait()),
        }
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            for topic in topics:
                self.unsubscribe(topic, outbox)
            self.dropped.pop(outbox)
            if dropped.is_set():
                await asyncio.gather(*tasks, return_exceptions=True)
                with suppress(Exception):
                    await websocket.close()

    async def read(self, websocket: WebSocket, outbox: "Outbox[Dict[str, Any]]", topics: Set[str]) -> None:
        try:
            while True:
                try:
                    request = Subscription.model_validate(await websocket.receive_json())
                except (ValidationError, ValueError) as error:
                    logger.warning(f"Ignoring an unreadable websocket message: {error}")
                    continue
                if request.subscribe is not None:
                    topics.add(request.subscribe)
                    self.subscribe(request.subscribe, outbox)
                if request.unsubscribe is not None:
                    topics.discard(request.unsubscribe)
                    self.unsubscribe(request.unsubscribe, outbox)
        except Exception as error:
            logger.info(f"Websocket closed: {error!r}")

    @staticmethod
    async def write(websocket: WebSocket, outbox: "Outbox[Dict[str, Any]]") -> None:
        try:
            while True:
                await websocket.send_json(await outbox.get())
        except Exception as error:
            logger.info(f"Dropping a websocket that can't be written to: {error!r}")
