"""Create the Phase 1.5 Cloud public-data schema.

Revision ID: 20260913_0001
Revises:
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260913_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked_at", sa.DateTime()),
        sa.Column("last_success_at", sa.DateTime()),
        sa.Column("last_error", sa.Text()),
        sa.Column("consecutive_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ownership", sa.String(40), nullable=False, server_default="OFFICIAL_CLOUD"),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="generic_html"),
        sa.Column("parser", sa.String(80), nullable=False, server_default="generic_html"),
        sa.Column("parser_config", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("subscribed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auth_type", sa.String(40), nullable=False, server_default="none"),
        sa.Column("auth_username", sa.String(300)),
        sa.Column("credential_ref", sa.String(300)),
        sa.Column("login_url", sa.String(2000)),
        sa.Column("session_profile_ref", sa.String(300)),
        sa.Column("allow_private_network", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("health_state", sa.String(40), nullable=False, server_default="unconfigured"),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("reauth_notified_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_identity", sa.String(64)),
        sa.Column("cloud_source_id", sa.String(80)),
        sa.Column("source_scope", sa.String(20), nullable=False, server_default="personal"),
        sa.Column("execution", sa.String(20), nullable=False, server_default="local"),
        sa.Column("execution_policy", sa.String(24), nullable=False, server_default="cloud_preferred"),
        sa.Column("cloud_policy", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("crawl_interval_seconds", sa.Integer()),
        sa.Column("validation_status", sa.String(20), nullable=False, server_default="untested"),
        sa.Column("validated_at", sa.DateTime()),
        sa.UniqueConstraint("code", name="uq_sources_code"),
    )
    for name in (
        "ownership", "subscribed", "health_state", "is_deleted", "source_identity",
        "cloud_source_id", "source_scope", "execution", "execution_policy", "cloud_policy",
    ):
        op.create_index(f"ix_sources_{name}", "sources", [name])

    op.create_table(
        "notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(80)),
        sa.Column("title", sa.String(1000), nullable=False),
        sa.Column("normalized_title", sa.String(1000), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("canonical_url", sa.String(2000), nullable=False),
        sa.Column("publish_date", sa.Date()),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("publisher", sa.String(500)),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("category", sa.String(80), nullable=False, server_default="other"),
        sa.Column("importance_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("registration_start", sa.Date()),
        sa.Column("registration_deadline", sa.Date()),
        sa.Column("event_start", sa.Date()),
        sa.Column("event_end", sa.Date()),
        sa.Column("target_students", sa.Text()),
        sa.Column("registration_method", sa.Text()),
        sa.Column("competition_level", sa.String(100)),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("public_id", name="uq_notices_public_id"),
    )
    for name in (
        "normalized_title", "canonical_url", "publish_date", "source_id", "content_hash",
        "category", "importance_score", "registration_deadline", "status", "first_seen_at", "version",
    ):
        op.create_index(f"ix_notices_{name}", "notices", [name])
    op.create_index("ix_notices_category_score", "notices", ["category", "importance_score"])
    op.create_index("ix_notices_dates", "notices", ["publish_date", "registration_deadline"])

    op.create_table(
        "notice_source_relations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.String(2000), nullable=False),
        sa.Column("origin_item_key", sa.String(160)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("notice_id", "source_id", "source_url", name="uq_notice_source_url"),
    )
    op.create_index("ix_notice_source_relations_notice_id", "notice_source_relations", ["notice_id"])
    op.create_index("ix_notice_source_relations_source_id", "notice_source_relations", ["source_id"])
    op.create_index(
        "ix_notice_source_origin_item_key", "notice_source_relations", ["source_id", "origin_item_key"]
    )

    op.create_table(
        "notice_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("old_hash", sa.String(64), nullable=False),
        sa.Column("new_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
    )
    op.create_index("ix_notice_updates_notice_id", "notice_updates", ["notice_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(1000), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("notice_id", "url", name="uq_attachment_notice_url"),
    )
    op.create_index("ix_attachments_notice_id", "attachments", ["notice_id"])
    op.create_index("ix_attachments_content_hash", "attachments", ["content_hash"])

    op.create_table(
        "importance_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keyword", sa.String(200), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_system_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_importance_rules_keyword", "importance_rules", ["keyword"])
    op.create_index("ix_importance_rules_enabled", "importance_rules", ["enabled"])

    op.create_table(
        "app_state",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    for name in (
        "app_state",
        "importance_rules",
        "attachments",
        "notice_updates",
        "notice_source_relations",
        "notices",
        "sources",
    ):
        op.drop_table(name)
