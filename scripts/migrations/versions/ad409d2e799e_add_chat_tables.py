"""Add chat tables for conversation and message management

Revision ID: ad409d2e799e
Revises: e15d7f942886
Create Date: 2025-11-14 11:58:10.930161

"""
from migrations.utils import database_connect

# revision identifiers, used by Alembic.
revision = "ad409d2e799e"
down_revision = "e15d7f942886"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create chat tables and related indexes/triggers."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Core conversation table
            CREATE TABLE IF NOT EXISTS conversations (
                id BIGSERIAL PRIMARY KEY,
                title VARCHAR(255),
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                is_pinned BOOLEAN DEFAULT FALSE,
                is_archived BOOLEAN DEFAULT FALSE,
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                deleted_at TIMESTAMP WITH TIME ZONE NULL
            );

            -- Core messages table (prepared for partitioning)
            CREATE TABLE IF NOT EXISTS messages (
                id BIGSERIAL,
                conversation_id BIGINT REFERENCES conversations(id) ON DELETE CASCADE,
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                content_type VARCHAR(20) DEFAULT 'text',
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                deleted_at TIMESTAMP WITH TIME ZONE NULL,
                PRIMARY KEY (id, created_at)
            ) PARTITION BY RANGE (created_at);

            -- Create initial partition for current month
            CREATE TABLE IF NOT EXISTS _messages_y2025m11 PARTITION OF messages
            FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');

            -- Message versions for edit history
            CREATE TABLE IF NOT EXISTS message_versions (
                id BIGSERIAL PRIMARY KEY,
                message_id BIGINT NOT NULL,
                message_created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                version_number INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{}',
                user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(message_id, version_number),
                FOREIGN KEY (message_id, message_created_at) REFERENCES messages(id, created_at) ON DELETE CASCADE
            );

            -- Conversation indexes
            CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)
            WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_conversations_pinned ON conversations(user_id, is_pinned, updated_at DESC)
            WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_conversations_metadata ON conversations USING GIN(metadata);

            -- Message indexes for pagination
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_time ON messages(conversation_id, created_at DESC)
            WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id, created_at DESC)
            WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_messages_content_type ON messages(content_type);

            -- JSONB expression indexes
            CREATE INDEX IF NOT EXISTS idx_messages_metadata_sender_info ON messages USING GIN((metadata -> 'sender_info'));

            -- Message versions indexes
            CREATE INDEX IF NOT EXISTS idx_message_versions_message_id ON message_versions(message_id, version_number DESC);

            -- Auto-create message versions on content change
            CREATE OR REPLACE FUNCTION create_message_version()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.content IS DISTINCT FROM NEW.content THEN
                    INSERT INTO message_versions (message_id, message_created_at, version_number, content, metadata, user_id)
                    VALUES (NEW.id, NEW.created_at, COALESCE((SELECT MAX(version_number) FROM message_versions WHERE message_id = NEW.id), 0) + 1, OLD.content, OLD.metadata, NEW.user_id);
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            -- Create triggers for automatic timestamp and versioning
            CREATE TRIGGER update_conversations_updated_at
            BEFORE UPDATE ON conversations
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_messages_updated_at
            BEFORE UPDATE ON messages
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER message_version_trigger
            BEFORE UPDATE ON messages
            FOR EACH ROW EXECUTE FUNCTION create_message_version();
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Chat tables created successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Drop chat tables and related objects."""
    conn = database_connect()
    cur = conn.cursor()

    try:
        query = """
            -- Drop triggers
            DROP TRIGGER IF EXISTS message_version_trigger ON messages;
            DROP TRIGGER IF EXISTS update_messages_updated_at ON messages;
            DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;

            -- Drop indexes
            DROP INDEX IF EXISTS idx_message_versions_message_id;
            DROP INDEX IF EXISTS idx_messages_content_type;
            DROP INDEX IF EXISTS idx_messages_user_id;
            DROP INDEX IF EXISTS idx_messages_conversation_time;
            DROP INDEX IF EXISTS idx_messages_metadata_sender_info;
            DROP INDEX IF EXISTS idx_conversations_metadata;
            DROP INDEX IF EXISTS idx_conversations_pinned;
            DROP INDEX IF EXISTS idx_conversations_user_id;

            -- Drop partition tables
            DROP TABLE IF EXISTS _messages_y2025m11;

            -- Drop main tables
            DROP TABLE IF EXISTS message_versions;
            DROP TABLE IF EXISTS messages;
            DROP TABLE IF EXISTS conversations;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Chat tables dropped successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
