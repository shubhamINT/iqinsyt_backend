import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.exceptions")


class IQinsytException(Exception):
    def __init__(
        self, status_code: int, error: str, message: str, request_id: str = ""
    ):
        self.status_code = status_code
        self.error = error
        self.message = message
        self.request_id = request_id
        super().__init__(message)


def _error_response(
    status_code: int, error: str, message: str, request_id: str
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "message": message,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IQinsytException)
    async def iqinsyt_exception_handler(
        request: Request, exc: IQinsytException
    ) -> JSONResponse:
        logger.warning(
            "Business error: method=%s, path=%s, error=%s, message=%s, request_id=%s",
            request.method,
            request.url.path,
            exc.error,
            exc.message,
            exc.request_id,
        )
        return _error_response(exc.status_code, exc.error, exc.message, exc.request_id)

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        logger.error(
            "Unhandled exception: method=%s, path=%s, error_type=%s, request_id=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
            request_id,
            exc_info=True,
        )
        return _error_response(
            500, "INTERNAL_ERROR", "An unexpected error occurred.", request_id
        )
