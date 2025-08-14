"""Mark default system message as system owned

Revision ID: ed69302be19a
Revises: 77836ba6e455
Create Date: 2025-08-14 14:39:52.275633

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed69302be19a'
down_revision = '77836ba6e455'
branch_labels = None
depends_on = None


def upgrade():
    # Mark "Default System Message" as system-owned (created_by = NULL)
    op.execute("""
        UPDATE system_message 
        SET created_by = NULL 
        WHERE name = 'Default System Message'
    """)
    
    # Log the change
    connection = op.get_bind()
    result = connection.execute(sa.text(
        "SELECT COUNT(*) FROM system_message WHERE name = 'Default System Message' AND created_by IS NULL"
    ))
    count = result.scalar()
    print(f"Updated {count} default system message(s) to be system-owned")


def downgrade():
    # If needed, assign defaults back to the first admin user
    op.execute("""
        UPDATE system_message 
        SET created_by = (SELECT id FROM "user" WHERE is_admin = true ORDER BY id LIMIT 1)
        WHERE created_by IS NULL AND name = 'Default System Message'
    """)
