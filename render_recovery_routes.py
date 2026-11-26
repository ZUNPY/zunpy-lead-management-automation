"""Private recovery HTTP adapter; not mounted by the production app yet.

Only an authenticated trusted worker may call these endpoints. Raw tokens
must not enter worker execution history or logs. Public request/redeem,
mail delivery, abuse controls and migration remain separate gates.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.security.auth import require_internal_service
from render_recovery import issue_recovery, redeem_recovery

from render_sensitive_http import BoundedRecoveryRoute

router = APIRouter(
    route_class=BoundedRecoveryRoute,
    prefix="/internal/recovery",
    tags=["internal-recovery"],
    dependencies=[Depends(require_internal_service)],
)


class IssuePayload(BaseModel):
    order_id: str = Field(min_length=1, max_length=32)
    email: str = Field(min_length=3, max_length=320)


class RedeemPayload(BaseModel):
    order_id: str = Field(min_length=1, max_length=32)
    recovery_token: str = Field(min_length=20, max_length=128)


def private_response(content: dict, status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=content, status_code=status_code, headers={
        "Cache-Control": "no-store", "Pragma": "no-cache",
    })


@router.post("/issue")
def issue(payload: IssuePayload, db: Session = Depends(get_db)) -> JSONResponse:
    try:
        result = issue_recovery(db, order_id=payload.order_id, email=payload.email)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if result is None:
        return private_response({"delivery": None})
    return private_response({"delivery": {
        "order_id": result.order_id,
        "recipient": result.recipient,
        "recovery_token": result.raw_token,
        "expires_at": result.expires_at.isoformat(),
    }})


@router.post("/redeem")
def redeem(payload: RedeemPayload, db: Session = Depends(get_db)) -> JSONResponse:
    try:
        result = redeem_recovery(db, order_id=payload.order_id,
                                 raw_token=payload.recovery_token)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if result is None:
        return private_response({"detail": "Recovery unavailable or expired."}, 400)
    return private_response({"order_id": result.order_id,
                             "order_token": result.order_token})
