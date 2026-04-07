import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
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
            "success": False,
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

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        detail = exc.detail
        # detail may be a dict (e.g. from get_api_key) or a plain string
        if isinstance(detail, dict):
            error = detail.get("error", "HTTP_ERROR")
            message = detail.get("message", str(exc.detail))
        else:
            error = "HTTP_ERROR"
            message = str(detail)
        logger.warning(
            "HTTP error: method=%s, path=%s, status=%s, error=%s, request_id=%s",
            request.method,
            request.url.path,
            exc.status_code,
            error,
            request_id,
        )
        return _error_response(exc.status_code, error, message, request_id)

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
