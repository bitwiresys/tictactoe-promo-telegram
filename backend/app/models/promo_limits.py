from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PromoIssuanceLimit(Base):
    __tablename__ = "promo_issuance_limits"
    __table_args__ = (
        Index("ix_promo_issuance_limits_client_id_issued_at", "client_id", "issued_at"),
        Index("ix_promo_issuance_limits_ip_issued_at", "ip", "issued_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
