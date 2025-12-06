"""create_practice_table

Revision ID: f1a2b3c4d5e6
Revises: d17fc2fd9c9d
Create Date: 2025-12-03 10:00:00.000000

"""
from migrations.utils import database_connect


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "d17fc2fd9c9d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create practice table with indexes."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Create practice table
            CREATE TABLE IF NOT EXISTS practice (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                
                -- Lịch tập cho từng buổi
                day_of_week INTEGER NOT NULL CHECK (day_of_week >= 1 AND day_of_week <= 7),
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                exercises TEXT[] NOT NULL,
                notes TEXT,
                
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                deleted_at TIMESTAMP WITH TIME ZONE NULL
            );

            -- Create indexes for better performance
            CREATE INDEX IF NOT EXISTS idx_practice_user_id ON practice(user_id)
            WHERE deleted_at IS NULL;
            
            CREATE INDEX IF NOT EXISTS idx_practice_day_of_week ON practice(day_of_week)
            WHERE deleted_at IS NULL;
            
            CREATE INDEX IF NOT EXISTS idx_practice_user_day ON practice(user_id, day_of_week)
            WHERE deleted_at IS NULL;
            
            CREATE INDEX IF NOT EXISTS idx_practice_created_at ON practice(created_at);

            -- Create trigger to automatically update updated_at
            CREATE TRIGGER update_practice_updated_at
            BEFORE UPDATE ON practice
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: practice table created successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        conn.rollback()
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Drop practice table and related objects."""
    conn = database_connect()
    cur = conn.cursor()

    try:
        query = """
            -- Drop trigger
            DROP TRIGGER IF EXISTS update_practice_updated_at ON practice;

            -- Drop indexes
            DROP INDEX IF EXISTS idx_practice_created_at;
            DROP INDEX IF EXISTS idx_practice_user_day;
            DROP INDEX IF EXISTS idx_practice_day_of_week;
            DROP INDEX IF EXISTS idx_practice_user_id;

            -- Drop table
            DROP TABLE IF EXISTS practice;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: practice table dropped successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        conn.rollback()
        raise ex
    finally:
        cur.close()
        conn.close()
