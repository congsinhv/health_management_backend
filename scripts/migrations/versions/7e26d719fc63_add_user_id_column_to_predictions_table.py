"""Add user_id column to predictions table

Revision ID: 7e26d719fc63
Revises: 2487ac2dc0ea
Create Date: 2025-12-13 01:36:25.606909

"""
from migrations.utils import database_connect


# revision identifiers, used by Alembic.
revision = "7e26d719fc63"
down_revision = "2487ac2dc0ea"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            ALTER TABLE predictions ADD COLUMN user_id INTEGER NOT NULL;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: user_id column added to predictions table successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        conn.rollback()
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            ALTER TABLE predictions DROP COLUMN user_id;
        """
        cur.execute(query)
        conn.commit()
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
