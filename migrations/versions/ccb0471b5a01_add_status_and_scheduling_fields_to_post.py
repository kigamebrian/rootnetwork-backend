"""Add status and scheduling fields to post

Revision ID: ccb0471b5a01
Revises: 
Create Date: 2026-06-12 21:01:15.010028

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'ccb0471b5a01'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Get the database connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('post')]

    with op.batch_alter_table('post', schema=None) as batch_op:
        # Add status column if it doesn't exist
        if 'status' not in columns:
            batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'))
        # Add scheduled_for if missing
        if 'scheduled_for' not in columns:
            batch_op.add_column(sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True))
        # Add published_at if missing
        if 'published_at' not in columns:
            batch_op.add_column(sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
        # Make timestamp nullable (if not already)
        # We'll just set it nullable – it's safe to repeat.
        batch_op.alter_column('timestamp', existing_type=sa.DATETIME(), nullable=True)

def downgrade():
    # Reverse the upgrade – drop only if they exist
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('post')]

    with op.batch_alter_table('post', schema=None) as batch_op:
        if 'published_at' in columns:
            batch_op.drop_column('published_at')
        if 'scheduled_for' in columns:
            batch_op.drop_column('scheduled_for')
        if 'status' in columns:
            batch_op.drop_column('status')
        # Revert timestamp to non-nullable (assuming it was non-nullable originally)
        batch_op.alter_column('timestamp', existing_type=sa.DATETIME(), nullable=False)
