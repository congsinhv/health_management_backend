"""create_predictions_table

Revision ID: f43158448255
Revises: ad409d2e799e
Create Date: 2025-11-22 17:38:31.998385

"""
from migrations.utils import database_connect

# revision identifiers, used by Alembic.
revision = "f43158448255"
down_revision = "ad409d2e799e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create predictions table with indexes."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Create predictions table
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                user_input JSONB NOT NULL,
                prediction_data JSONB NOT NULL,
                pdf_url VARCHAR(1024),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                deleted_at TIMESTAMP WITH TIME ZONE NULL
            );

            -- Create indexes
            CREATE INDEX IF NOT EXISTS idx_predictions_user_id ON predictions(user_id)
            WHERE deleted_at IS NULL;

            CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at);

            CREATE INDEX IF NOT EXISTS idx_predictions_user_created ON predictions(user_id, created_at DESC)
            WHERE deleted_at IS NULL;

            -- Create trigger for updated_at
            CREATE TRIGGER update_predictions_updated_at
            BEFORE UPDATE ON predictions
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: predictions table created successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Drop predictions table and related objects."""
    conn = database_connect()
    cur = conn.cursor()

    try:
        query = """
            -- Drop trigger
            DROP TRIGGER IF EXISTS update_predictions_updated_at ON predictions;

            -- Drop indexes
            DROP INDEX IF EXISTS idx_predictions_user_created;
            DROP INDEX IF EXISTS idx_predictions_created_at;
            DROP INDEX IF EXISTS idx_predictions_user_id;

            -- Drop table
            DROP TABLE IF EXISTS predictions;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: predictions table dropped successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
