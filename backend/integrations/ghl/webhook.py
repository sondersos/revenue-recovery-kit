import hmac
import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.dedup import upsert_contact, upsert_invoice
from integrations.ghl.models import ContactPayload, InvoicePayload, WebhookEnvelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/ghl", tags=["webhooks"])


@router.post("")
async def receive_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    # 1. Read raw body bytes FIRST — before any JSON parsing.
    body: bytes = await request.body()

    # 2. Check secret is configured and signature header is present.
    secret = settings.GHL_WEBHOOK_SECRET
    received_sig = request.headers.get("X-GHL-Signature")

    if not secret or not received_sig:
        raise HTTPException(
            status_code=401, detail="Missing or unconfigured webhook signature"
        )

    # 3. Compute expected signature with timing-safe comparison.
    expected_sig = hmac.new(
        key=secret.encode(), msg=body, digestmod=hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_sig, received_sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # 4. Parse the envelope (signature verified — safe to parse JSON now).
    try:
        envelope = WebhookEnvelope.model_validate_json(body)

        # 5. Dispatch on event type.
        event_type = envelope.type

        if event_type == "contact.created":
            payload = ContactPayload.model_validate(envelope.data)
            await upsert_contact(session, payload)
            logger.info(
                "Processed contact.created for ghl_contact_id=%s",
                payload.ghl_contact_id,
            )

        elif event_type == "invoice.status_changed":
            payload = InvoicePayload.model_validate(envelope.data)
            await upsert_invoice(session, payload)
            logger.info(
                "Processed invoice.status_changed for ghl_invoice_id=%s",
                payload.ghl_invoice_id,
            )

        else:
            logger.info("Unknown GHL event type: %s", event_type)

        try:
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            logger.exception("webhook: session.commit() failed — rolled back")
            raise HTTPException(status_code=503, detail="Database error — please retry")

    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {"received": True}
