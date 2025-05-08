from typing import Any, Dict


class Singleton(type):
    _instances: Dict[Any, Any] = {}

    def __call__(cls: Any, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
