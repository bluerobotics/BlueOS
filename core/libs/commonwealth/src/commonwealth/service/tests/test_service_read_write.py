from commonwealth.service.service import (
    EventHandler,
    ReadModelUpdated,
    Service,
    ServiceState,
)


class _SnapView:
    def __init__(self, value: int) -> None:
        self.value = value


class _MutableSnap(ServiceState):
    def __init__(self, value: int = 0, secret: list[int] | None = None) -> None:
        super().__init__()
        self.value = value
        self.secret = secret

    def snapshot(self) -> _SnapView:
        return _SnapView(value=self.value)


class _NoSnapState(ServiceState):
    def __init__(self) -> None:
        super().__init__()
        self.value = 0


def test_read_model_updated_via_event() -> None:
    live = _MutableSnap(value=0, secret=[1])
    seen: list[object] = []
    service = Service("snap", live, event_handlers=[seen.append])

    with service.write() as state:
        state.value = 7
        assert state.secret is not None
        state.secret.append(2)
        state.publish_read_model()

    assert isinstance(service._snapshot, _SnapView)
    assert service._snapshot.value == 7
    assert not hasattr(service._snapshot, "secret")
    assert len(seen) == 1
    assert isinstance(seen[0], ReadModelUpdated)
    assert seen[0].model.value == 7

    with service._state.lock() as state:
        state.value = 99

    with service.read() as view:
        assert isinstance(view, _SnapView)
        assert view.value == 7


def test_state_subscribers_receive_events() -> None:
    class _Persisting(_MutableSnap):
        def __init__(self) -> None:
            super().__init__(value=0)
            self.persisted: list[int] = []

        def subscribers(self) -> list[EventHandler]:
            return [self._persist]

        def _persist(self, event: object) -> None:
            if isinstance(event, ReadModelUpdated):
                self.persisted.append(event.model.value)

    live = _Persisting()
    service = Service("persist", live)
    with service.write() as state:
        state.value = 4
        state.publish_read_model()
    assert live.persisted == [4]


def test_write_without_event_does_not_update_snapshot() -> None:
    service = Service("snap", _MutableSnap(value=1))
    assert service._snapshot is not None
    assert service._snapshot.value == 1

    with service.write() as state:
        state.value = 2

    with service.read() as view:
        assert view.value == 1


def test_no_snapshot_service_read_sees_live_state_under_lock() -> None:
    service = Service("nosnap", _NoSnapState())
    assert service._snapshot is None

    with service.write() as state:
        state.value = 3

    with service.read() as state:
        assert state.value == 3
