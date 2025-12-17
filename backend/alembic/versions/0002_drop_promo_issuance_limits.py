"""drop promo issuance limits

Revision ID: 0002_drop_promo_issuance_limits
Revises: 0001_initial
Create Date: 2025-12-17

"""

from __future__ import annotations

from alembic import op

revision = "0002_drop_promo_issuance_limits"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS promo_issuance_limits CASCADE")


def downgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS promo_issuance_limits ("
        "id uuid PRIMARY KEY, "
        "client_id uuid NOT NULL, "
        "ip varchar(64) NOT NULL, "
        "issued_at timestamptz NOT NULL DEFAULT now()"
        ")"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_promo_issuance_limits_client_id_issued_at "
        "ON promo_issuance_limits (client_id, issued_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_promo_issuance_limits_ip_issued_at "
        "ON promo_issuance_limits (ip, issued_at)"
    )
