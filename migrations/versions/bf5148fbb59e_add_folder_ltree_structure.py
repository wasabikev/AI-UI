"""add_folder_ltree_structure

Revision ID: bf5148fbb59e
Revises: 988a4bb32f10
Create Date: 2023-11-15 12:34:56.789012

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils import LtreeType
from sqlalchemy.orm import Session
from sqlalchemy import select, text
import uuid
from datetime import datetime, timezone

# revision identifiers, used by Alembic
revision = 'bf5148fbb59e'
down_revision = '988a4bb32f10'
branch_labels = None
depends_on = None


def upgrade():
    # Create PostgreSQL ltree extension if it doesn't exist
    op.execute('CREATE EXTENSION IF NOT EXISTS ltree')
    
    # Get connection
    connection = op.get_bind()
    session = Session(bind=connection)
    
    # 1. First, temporarily drop the foreign key constraint
    op.execute(text("ALTER TABLE conversation DROP CONSTRAINT conversation_folder_id_fkey"))
    
    # 2. Create the new folder table with ltree path
    op.create_table('new_folder',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('path', LtreeType(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, 
                 server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, 
                 server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 3. Create indexes
    op.create_index('ix_new_folder_path_gist', 'new_folder', ['path'], postgresql_using='gist')
    op.create_index('ix_new_folder_user_id', 'new_folder', ['user_id'], unique=False)
    
    # 4. Migrate data from folder to new_folder
    # First, get all users using raw SQL
    users = session.execute(text("SELECT id FROM \"user\"")).fetchall()
    
    # Create a mapping of old folder IDs to new folder IDs
    folder_mapping = {}
    
    # For each user, create a root folder
    for user in users:
        user_id = user[0]
        
        # Create root folder for user
        root_result = session.execute(
            text(
                "INSERT INTO new_folder (name, path, user_id) VALUES ('Root', '0', :user_id) RETURNING id"
            ).bindparams(user_id=user_id)
        ).fetchone()
        
        if root_result:
            root_folder_id = root_result[0]
            
            # Get all old folders for this user
            # Since the old folder table doesn't have user_id, we need to join with conversations
            old_folders = session.execute(
                text("""
                    SELECT DISTINCT f.id, f.title 
                    FROM folder f
                    JOIN conversation c ON f.id = c.folder_id
                    WHERE c.user_id = :user_id
                """).bindparams(user_id=user_id)
            ).fetchall()
            
            # For each old folder, create a new folder under the root
            for old_folder in old_folders:
                old_id = old_folder[0]
                title = old_folder[1]
                
                # Insert new folder
                new_folder = session.execute(
                    text("""
                        INSERT INTO new_folder (name, path, user_id) 
                        VALUES (:name, :path, :user_id)
                        RETURNING id
                    """).bindparams(
                        name=title or "Untitled Folder",
                        path=f"0.{uuid.uuid4().hex[:8]}",  # Generate a unique path
                        user_id=user_id
                    )
                ).fetchone()
                
                if new_folder:
                    new_id = new_folder[0]
                    folder_mapping[old_id] = new_id
                    
                    # Update the path to include the folder's ID
                    session.execute(
                        text("""
                            UPDATE new_folder 
                            SET path = :path 
                            WHERE id = :id
                        """).bindparams(
                            path=f"0.{new_id}",
                            id=new_id
                        )
                    )
    
    # 5. Create a temporary column in the conversation table to store the new folder IDs
    op.add_column('conversation', sa.Column('new_folder_id', sa.Integer(), nullable=True))
    
    # 6. Update the temporary column with the new folder IDs
    for old_id, new_id in folder_mapping.items():
        session.execute(
            text("""
                UPDATE conversation 
                SET new_folder_id = :new_id 
                WHERE folder_id = :old_id
            """).bindparams(
                new_id=new_id,
                old_id=old_id
            )
        )
    
    # 7. For conversations without a folder, assign them to the root folder
    for user in users:
        user_id = user[0]
        
        # Get the root folder ID for this user
        root_folder = session.execute(
            text(
                "SELECT id FROM new_folder WHERE user_id = :user_id AND path = '0'"
            ).bindparams(user_id=user_id)
        ).fetchone()
        
        if root_folder:
            root_folder_id = root_folder[0]
            
            # Update conversations without a folder
            session.execute(
                text("""
                    UPDATE conversation 
                    SET new_folder_id = :root_id 
                    WHERE (folder_id IS NULL OR new_folder_id IS NULL) 
                    AND user_id = :user_id
                """).bindparams(
                    root_id=root_folder_id,
                    user_id=user_id
                )
            )
    
    # Commit the session to ensure all changes are applied
    session.commit()
    
    # 8. Drop the old folder table
    op.drop_table('folder')
    
    # 9. Rename the new folder table to folder
    op.rename_table('new_folder', 'folder')
    op.drop_index('ix_new_folder_path_gist', table_name='folder')
    op.drop_index('ix_new_folder_user_id', table_name='folder')
    op.create_index('ix_folder_path_gist', 'folder', ['path'], postgresql_using='gist')
    op.create_index('ix_folder_user_id', 'folder', ['user_id'], unique=False)
    
    # 10. Update the folder_id column with the values from new_folder_id
    op.execute(text("UPDATE conversation SET folder_id = new_folder_id"))
    
    # 11. Drop the temporary column
    op.drop_column('conversation', 'new_folder_id')
    
    # 12. Re-add the foreign key constraint
    op.create_foreign_key(
        'conversation_folder_id_fkey',
        'conversation', 'folder',
        ['folder_id'], ['id']
    )


def downgrade():
    # This downgrade is complex and potentially lossy
    # It will create a simple folder table and move conversations back
    
    # 1. Drop the foreign key constraint
    op.execute(text("ALTER TABLE conversation DROP CONSTRAINT conversation_folder_id_fkey"))
    
    # 2. Create the old folder table structure
    op.create_table('old_folder',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 3. Get connection
    connection = op.get_bind()
    session = Session(bind=connection)
    
    # 4. Migrate data from folder to old_folder
    # Get all folders except root folders
    folders = session.execute(
        text("""
            SELECT id, name, user_id 
            FROM folder 
            WHERE path != '0'
        """)
    ).fetchall()
    
    # Create a mapping of new folder IDs to old folder IDs
    folder_mapping = {}
    
    # For each folder, create an entry in old_folder
    for folder in folders:
        folder_id = folder[0]
        folder_name = folder[1]
        
        # Insert into old_folder
        new_folder = session.execute(
            text("""
                INSERT INTO old_folder (title) 
                VALUES (:title)
                RETURNING id
            """).bindparams(title=folder_name)
        ).fetchone()
        
        if new_folder:
            old_id = new_folder[0]
            folder_mapping[folder_id] = old_id
    
    # 5. Add a temporary column to store the old folder IDs
    op.add_column('conversation', sa.Column('old_folder_id', sa.Integer(), nullable=True))
    
    # 6. Update the temporary column with the old folder IDs
    for new_id, old_id in folder_mapping.items():
        session.execute(
            text("""
                UPDATE conversation 
                SET old_folder_id = :old_id 
                WHERE folder_id = :new_id
            """).bindparams(
                old_id=old_id,
                new_id=new_id
            )
        )
    
    # 7. Set old_folder_id to NULL for conversations in root folders
    session.execute(
        text("""
            UPDATE conversation c
            SET old_folder_id = NULL
            FROM folder f
            WHERE c.folder_id = f.id AND f.path = '0'
        """)
    )
    
    # Commit the session to ensure all changes are applied
    session.commit()
    
    # 8. Drop the folder table
    op.drop_index('ix_folder_user_id', table_name='folder')
    op.drop_index('ix_folder_path_gist', table_name='folder')
    op.drop_table('folder')
    
    # 9. Rename old_folder to folder
    op.rename_table('old_folder', 'folder')
    
    # 10. Update the folder_id column with the values from old_folder_id
    op.execute(text("UPDATE conversation SET folder_id = old_folder_id"))
    
    # 11. Drop the temporary column
    op.drop_column('conversation', 'old_folder_id')
    
    # 12. Re-add the foreign key constraint
    op.create_foreign_key(
        'conversation_folder_id_fkey',
        'conversation', 'folder',
        ['folder_id'], ['id']
    )