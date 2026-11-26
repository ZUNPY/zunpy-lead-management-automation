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
