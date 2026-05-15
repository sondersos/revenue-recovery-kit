from dataclasses import dataclass
from typing import Literal
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

# Detection is imported at call-time inside find() to avoid circular imports.


@dataclass
class Rule:
    name: str
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    subject_type: Literal["contact", "invoice"]
    recommended_action: str = ""

    async def find(self, session: AsyncSession, org_id: uuid.UUID) -> list:
        """Return list of Detection model instances. Override in subclasses."""
        raise NotImplementedError
