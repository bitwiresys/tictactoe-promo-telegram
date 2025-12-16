"""initial

Revision ID: 0001_initial
Revises:
Create Date: 2025-12-16

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE game_status AS ENUM ('in_progress','player_won','computer_won','draw')")
    op.execute("CREATE TYPE turn AS ENUM ('player','computer')")
    op.execute("CREATE TYPE outbox_status AS ENUM ('pending','processing','sent','failed')")

    game_status_enum = postgresql.ENUM(
        "in_progress",
        "player_won",
        "computer_won",
        "draw",
        name="game_status",
        create_type=False,
    )
    turn_enum = postgresql.ENUM("player", "computer", name="turn", create_type=False)
    outbox_status_enum = postgresql.ENUM(
        "pending", "processing", "sent", "failed", name="outbox_status", create_type=False
    )

    op.create_table(
        "games",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", game_status_enum, nullable=False),
        sa.Column("board", sa.Text(), nullable=False),
        sa.Column("next_turn", turn_enum, nullable=False),
        sa.Column("player_symbol", sa.String(length=1), nullable=False),
        sa.Column("computer_symbol", sa.String(length=1), nullable=False),
        sa.Column("move_count", sa.SmallInteger(), nullable=False),
        sa.Column("promo_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_games_status", "games", ["status"], unique=False)
    op.create_index("ix_games_finished_at", "games", ["finished_at"], unique=False)

    op.create_table(
        "promo_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=5), nullable=False),
        sa.Column("game_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], name="fk_promo_codes_game_id"),
        sa.UniqueConstraint("code", name="uq_promo_codes_code"),
        sa.UniqueConstraint("game_id", name="uq_promo_codes_game_id"),
    )

    op.create_foreign_key(
        "fk_games_promo_code_id",
        "games",
        "promo_codes",
        ["promo_code_id"],
        ["id"],
        use_alter=True,
    )

    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", outbox_status_enum, nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("dedupe_key", name="uq_outbox_events_dedupe_key"),
    )
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"], unique=False)
    op.create_index(
        "ix_outbox_events_next_retry_at", "outbox_events", ["next_retry_at"], unique=False
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.Text(), primary_key=True, nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "promo_issuance_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
    )
    op.create_index(
        "ix_promo_issuance_limits_client_id_issued_at",
        "promo_issuance_limits",
        ["client_id", "issued_at"],
        unique=False,
    )
    op.create_index(
        "ix_promo_issuance_limits_ip_issued_at",
        "promo_issuance_limits",
        ["ip", "issued_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_promo_issuance_limits_ip_issued_at", table_name="promo_issuance_limits")
    op.drop_index(
        "ix_promo_issuance_limits_client_id_issued_at", table_name="promo_issuance_limits"
    )
    op.drop_table("promo_issuance_limits")

    op.drop_table("idempotency_keys")

    op.drop_index("ix_outbox_events_next_retry_at", table_name="outbox_events")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_table("outbox_events")

    op.drop_constraint("fk_games_promo_code_id", "games", type_="foreignkey")

    op.drop_table("promo_codes")

    op.drop_index("ix_games_finished_at", table_name="games")
    op.drop_index("ix_games_status", table_name="games")
    op.drop_table("games")

    op.execute("DROP TYPE outbox_status")
    op.execute("DROP TYPE turn")
    op.execute("DROP TYPE game_status")
