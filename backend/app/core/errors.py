import logging
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("intellicrm")


class AppError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail=message)
        self.code = code


def not_found(what="Resource"):
    return AppError(404, "RESOURCE_NOT_FOUND", f"{what} not found")


def forbidden(msg="You do not have permission to perform this action"):
    return AppError(403, "FORBIDDEN", msg)


def bad_request(msg, code="BAD_REQUEST"):
    return AppError(400, code, msg)


def conflict(msg, code="CONFLICT"):
    return AppError(409, code, msg)


def _body(request: Request, code: str, message: str, details=None):
    err = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details is not None:
        err["details"] = details
    return {"error": err}


def install_handlers(app: FastAPI):
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = request.state.request_id
        return resp

    @app.exception_handler(AppError)
    async def _app(request, exc: AppError):
        return JSONResponse(_body(request, exc.code, exc.detail), status_code=exc.status_code)

    @app.exception_handler(HTTPException)
    async def _http(request, exc: HTTPException):
        codes = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "RESOURCE_NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(_body(request, codes.get(exc.status_code, "HTTP_ERROR"), str(exc.detail)),
                            status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _val(request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(_body(request, "VALIDATION_ERROR", "Invalid request", details), status_code=422)

    @app.exception_handler(IntegrityError)
    async def _integrity(request, exc: IntegrityError):
        log.warning("integrity error: %s", exc.orig)
        return JSONResponse(_body(request, "CONFLICT", "The change violates a data integrity rule"), status_code=409)

    @app.exception_handler(Exception)
    async def _any(request, exc: Exception):
        log.exception("unhandled error request_id=%s", getattr(request.state, "request_id", None))
        return JSONResponse(_body(request, "INTERNAL_ERROR", "An unexpected error occurred"), status_code=500)
