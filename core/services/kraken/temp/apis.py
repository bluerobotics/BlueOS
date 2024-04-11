from typing import Any, Callable, Coroutine, Dict, Optional
from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRoute
from loguru import logger

def stack_trace_message(error: BaseException) -> str:
    """Get string containing joined messages from all exceptions in stack trace, beginning with the most recent one."""
    message = str(error)
    sub_error = error.__cause__
    while sub_error is not None:
        message = f"{message} {sub_error}"
        sub_error = sub_error.__cause__
    return message

class GenericErrorHandlingRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except HTTPException as error:
                logger.exception(error)
                raise error
            except Exception as error:
                logger.error("Unhandled service exception.")
                logger.exception(error)
                error_msg = stack_trace_message(error)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg) from error

        return custom_route_handler
