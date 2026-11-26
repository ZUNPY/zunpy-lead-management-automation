"""Safe validation responses for credential-bearing HTTP routes."""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute


class SensitiveRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError:
                # Pydantic error details can contain the rejected input,
                # including secrets, email addresses or malformed JSON.
                return JSONResponse(
                    {"detail": "Invalid request."},
                    status_code=422,
                    headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
                )

        return safe_handler


# Recovery requests contain only small JSON credentials, never files.
# Keep PayPal webhook and PDF upload handling outside this limit.
RECOVERY_BODY_LIMIT = 4096


class BoundedRecoveryRoute(SensitiveRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded_handler(request: Request):
            def reject(code: int, detail: str):
                return JSONResponse({"detail": detail}, status_code=code,
                    headers={"Cache-Control": "no-store", "Pragma": "no-cache"})

            lengths = request.headers.getlist("content-length")
            if lengths:
                length = lengths[0]
                if (len(lengths) != 1 or not length.isascii()
                        or not length.isdecimal()):
                    return reject(400, "Invalid request.")
                # Avoid converting an arbitrarily long integer.
                normalized = length.lstrip("0") or "0"
                if len(normalized) > 4 or int(normalized) > RECOVERY_BODY_LIMIT:
                    return reject(413, "Request too large.")
            # Enforce actual bytes even for chunked requests or absent lengths.
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > RECOVERY_BODY_LIMIT:
                    return reject(413, "Request too large.")
                body.extend(chunk)
            if lengths and len(body) != int(normalized):
                return reject(400, "Invalid request.")

            # Replay the bounded body to FastAPI's ordinary JSON parser.
            pending = True
            async def receive():
                nonlocal pending
                if pending:
                    pending = False
                    return {"type": "http.request", "body": bytes(body),
                            "more_body": False}
                return await request.receive()

            return await handler(Request(request.scope, receive))

        return bounded_handler
