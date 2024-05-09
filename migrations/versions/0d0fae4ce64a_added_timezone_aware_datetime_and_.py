"""Added timezone-aware datetime and nullable indexing frequency

Revision ID: 0d0fae4ce64a
Revises: 86b593b45d08
Create Date: 2024-05-09 15:32:42.599777

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d0fae4ce64a'
down_revision = '86b593b45d08'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('website',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('url', sa.String(length=2048), nullable=False),
    sa.Column('site_metadata', sa.JSON(), nullable=True),
    sa.Column('system_message_id', sa.Integer(), nullable=False),
    sa.Column('indexed_at', sa.DateTime(), nullable=True),
    sa.Column('indexing_status', sa.String(length=50), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('indexing_frequency', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['system_message_id'], ['system_message.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('website', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_website_url'), ['url'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('website', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_website_url'))

    op.drop_table('website')
    # ### end Alembic commands ###
