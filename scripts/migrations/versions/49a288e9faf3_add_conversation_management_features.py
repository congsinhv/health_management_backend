"""Add conversation management features

Revision ID: 49a288e9faf3
Revises: e15d7f942886
Create Date: 2025-11-09 22:26:22.172965

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "49a288e9faf3"
down_revision = "e15d7f942886"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to qa_conversations table
    op.execute(
        """
        ALTER TABLE qa_conversations ADD COLUMN title VARCHAR(255);
        ALTER TABLE qa_conversations ADD COLUMN is_pinned BOOLEAN DEFAULT FALSE;
        ALTER TABLE qa_conversations ADD COLUMN tags JSONB DEFAULT '[]'::jsonb;
        ALTER TABLE qa_conversations ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
        ALTER TABLE qa_conversations ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        ALTER TABLE qa_conversations ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE;
    """
    )

    # Add indexes for performance
    op.execute(
        """
        CREATE INDEX idx_qa_conversations_title ON qa_conversations(title);
        CREATE INDEX idx_qa_conversations_is_pinned ON qa_conversations(is_pinned) WHERE is_pinned = TRUE;
        CREATE INDEX idx_qa_conversations_tags ON qa_conversations USING gin(tags);
        CREATE INDEX idx_qa_conversations_updated_at ON qa_conversations(updated_at);
        CREATE INDEX idx_qa_conversations_deleted_at ON qa_conversations(deleted_at) WHERE deleted_at IS NULL;
    """
    )

    # Create qa_messages table for multi-turn support
    op.execute(
        """
        CREATE TABLE qa_messages (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES qa_conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            content_cleaned TEXT,
            answers JSONB,
            metadata JSONB DEFAULT '{}'::jsonb,
            parent_message_id INTEGER REFERENCES qa_messages(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            deleted_at TIMESTAMP WITH TIME ZONE
        );
    """
    )

    # Add indexes for qa_messages table
    op.execute(
        """
        CREATE INDEX idx_qa_messages_conversation_id ON qa_messages(conversation_id);
        CREATE INDEX idx_qa_messages_created_at ON qa_messages(created_at);
        CREATE INDEX idx_qa_messages_parent_message_id ON qa_messages(parent_message_id);
        CREATE INDEX idx_qa_messages_deleted_at ON qa_messages(deleted_at) WHERE deleted_at IS NULL;
    """
    )

    # Create qa_message_versions table for version history
    op.execute(
        """
        CREATE TABLE qa_message_versions (
            id SERIAL PRIMARY KEY,
            message_id INTEGER NOT NULL REFERENCES qa_messages(id) ON DELETE CASCADE,
            version_number INTEGER NOT NULL,
            content TEXT NOT NULL,
            content_cleaned TEXT,
            answers JSONB,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(message_id, version_number)
        );
    """
    )

    # Add indexes for qa_message_versions table
    op.execute(
        """
        CREATE INDEX idx_qa_message_versions_message_id ON qa_message_versions(message_id);
    """
    )

    # Add full-text search indexes
    op.execute(
        """
        -- Add full-text search index on conversations
        CREATE INDEX idx_qa_conversations_fts ON qa_conversations
        USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(question, '')));

        -- Add full-text search index on messages
        CREATE INDEX idx_qa_messages_fts ON qa_messages
        USING gin(to_tsvector('english', content));
    """
    )

    # Create materialized view for search performance
    op.execute(
        """
        CREATE MATERIALIZED VIEW conversation_search_index AS
        SELECT
            c.id,
            c.user_id,
            c.title,
            c.question,
            c.tags,
            c.created_at,
            c.updated_at,
            c.is_pinned,
            COUNT(m.id) as message_count,
            MAX(m.created_at) as last_message_at,
            to_tsvector('english',
                coalesce(c.title, '') || ' ' ||
                coalesce(c.question, '') || ' ' ||
                coalesce(string_agg(m.content, ' '), '')
            ) as search_vector
        FROM qa_conversations c
        LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
        WHERE c.deleted_at IS NULL
        GROUP BY c.id, c.user_id, c.title, c.question, c.tags, c.created_at, c.updated_at, c.is_pinned;
    """
    )

    # Create indexes for materialized view
    op.execute(
        """
        CREATE INDEX idx_conversation_search_vector ON conversation_search_index
        USING gin(search_vector);

        CREATE UNIQUE INDEX idx_conversation_search_id ON conversation_search_index(id);

        CREATE INDEX idx_conversation_search_user_updated ON conversation_search_index(user_id, updated_at DESC);
        CREATE INDEX idx_conversation_search_user_pinned ON conversation_search_index(user_id, is_pinned, updated_at DESC) WHERE is_pinned = TRUE;
    """
    )

    # Create composite indexes for common queries
    op.execute(
        """
        -- Composite indexes for common queries
        CREATE INDEX idx_qa_conversations_user_updated ON qa_conversations(user_id, updated_at DESC)
        WHERE deleted_at IS NULL;

        CREATE INDEX idx_qa_conversations_user_pinned ON qa_conversations(user_id, is_pinned, updated_at DESC)
        WHERE deleted_at IS NULL AND is_pinned = TRUE;

        CREATE INDEX idx_qa_messages_conversation_created ON qa_messages(conversation_id, created_at)
        WHERE deleted_at IS NULL;
    """
    )


def downgrade() -> None:
    # Drop materialized view and search indexes
    op.execute("DROP MATERIALIZED VIEW IF EXISTS conversation_search_index;")

    # Drop full-text search indexes
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_fts;")
    op.execute("DROP INDEX IF EXISTS idx_qa_messages_fts;")

    # Drop composite indexes
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_user_updated;")
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_user_pinned;")
    op.execute("DROP INDEX IF EXISTS idx_qa_messages_conversation_created;")

    # Drop tables in reverse order
    op.execute("DROP TABLE IF EXISTS qa_message_versions;")
    op.execute("DROP TABLE IF EXISTS qa_messages;")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_title;")
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_is_pinned;")
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_tags;")
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_updated_at;")
    op.execute("DROP INDEX IF EXISTS idx_qa_conversations_deleted_at;")

    # Drop columns from qa_conversations table
    op.execute(
        """
        ALTER TABLE qa_conversations DROP COLUMN IF EXISTS title;
        ALTER TABLE qa_conversations DROP COLUMN IF EXISTS is_pinned;
        ALTER TABLE qa_conversations DROP COLUMN IF EXISTS tags;
        ALTER TABLE qa_conversations DROP COLUMN IF EXISTS metadata;
        ALTER TABLE qa_conversations DROP COLUMN IF EXISTS updated_at;
        ALTER TABLE qa_conversations DROP COLUMN IF EXISTS deleted_at;
    """
    )
