"""Add thinking_process column to Conversation

Revision ID: 010ce5c3f7e9
Revises: 969f1bdbfe28
Create Date: 2025-03-03 20:33:11.745538

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010ce5c3f7e9'
down_revision = '969f1bdbfe28'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('system_message', 'reasoning_effort')
    op.drop_index('ix_website_url', table_name='website')
    op.create_index('idx_website_url', 'website', ['url'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('idx_website_url', table_name='website')
    op.create_index('ix_website_url', 'website', ['url'], unique=False)
    op.add_column('system_message', sa.Column('reasoning_effort', sa.VARCHAR(length=20), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
