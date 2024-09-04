import abc

class AutopilotPlatform(abc.ABC):
    @abc.abstractmethod
    def start(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def restart(self) -> None:
        raise NotImplementedError
