"""Pydantic payload models for GoHighLevel webhook events.

Kept in a separate module so that dedup.py can import just the models
without pulling in FastAPI routing or database dependencies.
"""

from typing import Optional

from pydantic import BaseModel


class ContactPayload(BaseModel):
    ghl_contact_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    organization_id: Optional[str] = None


class InvoicePayload(BaseModel):
    ghl_invoice_id: Optional[str] = None
    contact_ghl_id: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None
    due_date: Optional[str] = None


class WebhookEnvelope(BaseModel):
    type: str
    data: dict
