"""Browser-bound extension PKCE handoff and revocable scoped sessions.
Revision ID: 9c2e4a701b36
Revises: 77105a1d036a
"""
from alembic import op
import sqlalchemy as sa
revision = "9c2e4a701b36"
down_revision = "77105a1d036a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("oauth_states", sa.Column("extension_request", sa.String(64), nullable=False, server_default=""))
    op.create_table("extension_auth_requests",
        sa.Column("id", sa.String(64), primary_key=True), sa.Column("extension_id", sa.String(32), nullable=False),
        sa.Column("challenge", sa.String(43), nullable=False), sa.Column("state", sa.String(128), nullable=False),
        sa.Column("browser", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("code_hash", sa.String(64), unique=True), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("extension_sessions", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extension_id", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_extension_sessions_token_hash", "extension_sessions", ["token_hash"], unique=True)
    op.create_index("ix_extension_sessions_user_id", "extension_sessions", ["user_id"])


def downgrade():
    op.drop_table("extension_sessions")
    op.drop_table("extension_auth_requests")
    op.drop_column("oauth_states", "extension_request")
