"""add_reasoning_effort_to_system_message

Revision ID: 969f1bdbfe28
Revises: 460c7b9e82a2
Create Date: 2025-02-02 10:03:00.659778

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '969f1bdbfe28'
down_revision = '460c7b9e82a2'
branch_labels = None
depends_on = None


def upgrade():
    # Add the new column
    op.add_column('system_message', 
        sa.Column('reasoning_effort', sa.String(20), nullable=True)
    )
    
    # Set default value for existing rows
    op.execute("UPDATE system_message SET reasoning_effort = 'medium' WHERE reasoning_effort IS NULL")


def downgrade():
    # Remove the column if we need to roll back
    op.drop_column('system_message', 'reasoning_effort')