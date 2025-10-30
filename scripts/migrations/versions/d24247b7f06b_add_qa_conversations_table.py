"""add_qa_conversations_table

Revision ID: d24247b7f06b
Revises: cde7763a63b8
Create Date: 2025-10-30 14:59:03.026821

"""

from migrations.utils import database_connect


# revision identifiers, used by Alembic.
revision = "d24247b7f06b"
down_revision = "cde7763a63b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Q&A conversations table."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Create Q&A conversations table
            CREATE TABLE IF NOT EXISTS qa_conversations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                question TEXT NOT NULL,
                question_cleaned TEXT,
                answers JSONB,
                summary TEXT,
                threshold FLOAT DEFAULT 0.55,
                top_k INTEGER DEFAULT 7,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            -- Create indexes for better performance
            CREATE INDEX IF NOT EXISTS idx_qa_conversations_user_id ON qa_conversations(user_id);
            CREATE INDEX IF NOT EXISTS idx_qa_conversations_created_at ON qa_conversations(created_at);
            CREATE INDEX IF NOT EXISTS idx_qa_conversations_question ON qa_conversations 
            USING gin(to_tsvector('english', question));
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Q&A conversations table created successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Drop Q&A conversations table."""
    conn = database_connect()
    cur = conn.cursor()

    try:
        query = """
            -- Drop indexes
            DROP INDEX IF EXISTS idx_qa_conversations_question;
            DROP INDEX IF EXISTS idx_qa_conversations_created_at;
            DROP INDEX IF EXISTS idx_qa_conversations_user_id;

            -- Drop Q&A conversations table
            DROP TABLE IF EXISTS qa_conversations;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Q&A conversations table dropped successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
