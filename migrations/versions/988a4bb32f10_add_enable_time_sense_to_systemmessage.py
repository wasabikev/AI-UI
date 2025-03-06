"""Add enable_time_sense to SystemMessage

Revision ID: 988a4bb32f10
Revises: 010ce5c3f7e9
Create Date: 2025-03-06 09:50:37.199397

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '988a4bb32f10'
down_revision = '010ce5c3f7e9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('system_message', sa.Column('enable_time_sense', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    op.drop_column('system_message', 'enable_time_sense')
