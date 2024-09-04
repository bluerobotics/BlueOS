import abc

class AutopilotFirmware(abc.ABC):
    @abc.abstractmethod
    def is_installed(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def install(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def uninstall(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def update(self) -> None:
        raise NotImplementedError
