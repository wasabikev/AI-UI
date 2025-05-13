"""update_timestamp_columns_to_timezone_aware

Revision ID: 61a5581cec4f
Revises: e307c2c299b3
Create Date: 2025-05-13 15:27:20.922390

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '61a5581cec4f'
down_revision = 'e307c2c299b3'
branch_labels = None
depends_on = None


def upgrade():
    # Folder table
    op.alter_column('folder', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='created_at AT TIME ZONE \'UTC\'')
    op.alter_column('folder', 'updated_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='updated_at AT TIME ZONE \'UTC\'')

    # Conversation table
    op.alter_column('conversation', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='created_at AT TIME ZONE \'UTC\'')
    op.alter_column('conversation', 'updated_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='updated_at AT TIME ZONE \'UTC\'')

    # User table
    op.alter_column('user', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='created_at AT TIME ZONE \'UTC\'')
    op.alter_column('user', 'updated_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='updated_at AT TIME ZONE \'UTC\'')
    op.alter_column('user', 'last_login',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='last_login AT TIME ZONE \'UTC\'')

    # UserUsage table
    op.alter_column('user_usage', 'session_start',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='session_start AT TIME ZONE \'UTC\'')
    op.alter_column('user_usage', 'session_end',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='session_end AT TIME ZONE \'UTC\'')

    # SystemMessage table
    op.alter_column('system_message', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='created_at AT TIME ZONE \'UTC\'')
    op.alter_column('system_message', 'updated_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='updated_at AT TIME ZONE \'UTC\'')

    # Website table
    op.alter_column('website', 'indexed_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='indexed_at AT TIME ZONE \'UTC\'')
    op.alter_column('website', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='created_at AT TIME ZONE \'UTC\'')
    op.alter_column('website', 'updated_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='updated_at AT TIME ZONE \'UTC\'')

    # UploadedFile table
    op.alter_column('uploaded_file', 'upload_timestamp',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using='upload_timestamp AT TIME ZONE \'UTC\'')

def downgrade():
    # Convert back to timezone-naive if needed
    # (Similar structure but reverse the changes)
    pass