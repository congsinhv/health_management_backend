"""add_december_2025_partition

Revision ID: 6fc6b98c4223
Revises: d17fc2fd9c9d
Create Date: 2025-12-03 11:05:09.528276

"""
from migrations.utils import database_connect

# revision identifiers, used by Alembic.
revision = '6fc6b98c4223'
down_revision = 'd17fc2fd9c9d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create partition for December 2025 and future months."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Create partition for December 2025
            CREATE TABLE IF NOT EXISTS _messages_y2025m12 PARTITION OF messages
            FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

            -- Create partitions for Q1 2026 to prevent future issues
            CREATE TABLE IF NOT EXISTS _messages_y2026m01 PARTITION OF messages
            FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

            CREATE TABLE IF NOT EXISTS _messages_y2026m02 PARTITION OF messages
            FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

            CREATE TABLE IF NOT EXISTS _messages_y2026m03 PARTITION OF messages
            FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: December 2025 and Q1 2026 partitions created successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Drop December 2025 and Q1 2026 partitions."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Drop Q1 2026 partitions
            DROP TABLE IF EXISTS _messages_y2026m03;
            DROP TABLE IF EXISTS _messages_y2026m02;
            DROP TABLE IF EXISTS _messages_y2026m01;

            -- Drop December 2025 partition
            DROP TABLE IF EXISTS _messages_y2025m12;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Partitions dropped successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
