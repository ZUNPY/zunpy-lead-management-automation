"""Public recovery adapter. Disabled until a trusted delivery adapter is installed.

Do not expose until trusted proxy/source identity, delivery privacy and the
PayPal claim retry lifecycle have been verified. Never put raw tokens in logs.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
import ipaddress
import logging
from typing import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from render_recovery import RecoveryDelivery, issue_recovery, redeem_recovery
from render_recovery_limits import allow_request
from render_recovery_routes import IssuePayload, RedeemPayload, private_response

from render_sensitive_http import BoundedRecoveryRoute

router = APIRouter(prefix="/recovery", tags=["recovery"], route_class=BoundedRecoveryRoute)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PublicRecoveryConfig:
    source_secret: bytes = field(repr=False)
    deliver: Callable[[RecoveryDelivery], None] = field(repr=False)

    def __post_init__(self):
        if len(self.source_secret) < 32 or not callable(self.deliver):
            raise ValueError("Recovery requires a strong source secret and delivery adapter.")


def get_public_recovery_config() -> PublicRecoveryConfig | None:
    # Fail closed. No environment flag alone can enable public recovery.
    return None


def _reserve(db: Session, request: Request, order_id: str,
             config: PublicRecoveryConfig, *, redeem: bool = False) -> bool:
    # Never parse forwarding headers here. ASGI client identity must come
    # from a verified proxy configuration; otherwise deployment stays disabled.
    if request.client is None:
        return False
    try:
        address = ipaddress.ip_address(request.client.host)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    # Aggregate IPv6 sources by /64 to limit trivial address rotation.
    source = str(ipaddress.ip_network(f"{address}/64", strict=False)) if address.version == 6 else str(address)
    key = hmac.new(config.source_secret, source.encode(), hashlib.sha256).hexdigest()
    try:
        allowed = allow_request(db, order_id=order_id, source_key=key, redeem=redeem)
        db.commit()  # Rejected or invalid credentials cannot undo quota consumption.
        return allowed
    except Exception:
        db.rollback()
        raise


def _deliver_safely(config: PublicRecoveryConfig, delivery: RecoveryDelivery) -> None:
    try:
        config.deliver(delivery)
    except Exception:
        # Do not log exception details: a transport may include secrets.
        logger.warning("Recovery delivery failed; link will expire normally.")


@router.post("/request", status_code=202)
def request_recovery(payload: IssuePayload, request: Request,
                     background: BackgroundTasks,
                     db: Session = Depends(get_db),
                     config: PublicRecoveryConfig | None = Depends(get_public_recovery_config)):
    if config is None:
        return private_response({"detail": "Recovery unavailable."}, 503)
    accepted = {"status": "accepted"}
    if not _reserve(db, request, payload.order_id, config):
        return private_response(accepted, 202)
    try:
        delivery = issue_recovery(db, order_id=payload.order_id, email=payload.email)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if delivery is not None:
        background.add_task(_deliver_safely, config, delivery)
    # Identical status/body for unknown order, wrong email, duplicate or quota.
    # This is response uniformity, not proof of constant-time processing.
    return private_response(accepted, 202)


@router.post("/redeem")
def redeem_public(payload: RedeemPayload, request: Request,
                  db: Session = Depends(get_db),
                  config: PublicRecoveryConfig | None = Depends(get_public_recovery_config)):
    if config is None:
        return private_response({"detail": "Recovery unavailable."}, 503)
    invalid = {"detail": "Recovery unavailable or expired."}
    if not _reserve(db, request, payload.order_id, config, redeem=True):
        return private_response(invalid, 400)
    try:
        result = redeem_recovery(db, order_id=payload.order_id, raw_token=payload.recovery_token)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if result is None:
        return private_response(invalid, 400)
    return private_response({"order_id": result.order_id, "order_token": result.order_token})
