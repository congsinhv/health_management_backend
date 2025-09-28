"""add_enhanced_authentication_support

Revision ID: cde7763a63b8
Revises:
Create Date: 2025-09-25 22:30:46.369877

"""

from alembic import op
from migrations.utils import database_connect


# revision identifiers, used by Alembic.
revision = "cde7763a63b8"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add enhanced authentication support including OAuth, email verification, and refresh tokens."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            ALTER TABLE USERS
            ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE,
                ADD COLUMN IF NOT EXISTS provider VARCHAR(50) DEFAULT 'local',
                ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500),
                ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR(255) UNIQUE,
                ADD COLUMN IF NOT EXISTS email_verification_sent_at TIMESTAMP WITH TIME ZONE,
                ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255) UNIQUE,
                ADD COLUMN IF NOT EXISTS password_reset_sent_at TIMESTAMP WITH TIME ZONE;

            ALTER TABLE USERS
            ALTER COLUMN password_hash DROP NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_users_google_id ON USERS(google_id)
            WHERE google_id IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_users_provider ON USERS(provider);

            CREATE INDEX IF NOT EXISTS idx_users_email_verification_token ON USERS(email_verification_token)
            WHERE email_verification_token IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_users_password_reset_token ON USERS(password_reset_token)
            WHERE password_reset_token IS NOT NULL;

            CREATE TABLE IF NOT EXISTS REFRESH_TOKENS (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES USERS(id) ON DELETE CASCADE,
                token_hash VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                revoked BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON REFRESH_TOKENS(user_id);
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON REFRESH_TOKENS(token_hash);
            CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON REFRESH_TOKENS(expires_at);

            CREATE TRIGGER update_refresh_tokens_updated_at BEFORE
            UPDATE ON REFRESH_TOKENS FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            CREATE TABLE IF NOT EXISTS AUTH_LOGS (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES USERS(id) ON DELETE
                    SET NULL,
                        event_type VARCHAR(50) NOT NULL,
                        ip_address INET,
                        user_agent TEXT,
                        success BOOLEAN DEFAULT TRUE,
                        details JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );

            CREATE INDEX IF NOT EXISTS idx_auth_logs_user_id ON AUTH_LOGS(user_id);
            CREATE INDEX IF NOT EXISTS idx_auth_logs_event_type ON AUTH_LOGS(event_type);
            CREATE INDEX IF NOT EXISTS idx_auth_logs_created_at ON AUTH_LOGS(created_at);
            CREATE INDEX IF NOT EXISTS idx_auth_logs_success ON AUTH_LOGS(success);

        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Upgrade completed successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Remove enhanced authentication support."""
    conn = database_connect()
    cur = conn.cursor()

    try:
        query = """
            -- Drop auth logs table and its indexes
            DROP INDEX IF EXISTS idx_auth_logs_success;
            DROP INDEX IF EXISTS idx_auth_logs_created_at;
            DROP INDEX IF EXISTS idx_auth_logs_event_type;
            DROP INDEX IF EXISTS idx_auth_logs_user_id;
            DROP TABLE IF EXISTS AUTH_LOGS;

            -- Drop refresh tokens table, its indexes and trigger
            DROP INDEX IF EXISTS idx_refresh_tokens_expires_at;
            DROP INDEX IF EXISTS idx_refresh_tokens_token_hash;
            DROP INDEX IF EXISTS idx_refresh_tokens_user_id;
            DROP TRIGGER IF EXISTS update_refresh_tokens_updated_at ON REFRESH_TOKENS;
            DROP TABLE IF EXISTS REFRESH_TOKENS;

            -- Remove indexes from users table
            DROP INDEX IF EXISTS idx_users_password_reset_token;
            DROP INDEX IF EXISTS idx_users_email_verification_token;
            DROP INDEX IF EXISTS idx_users_provider;
            DROP INDEX IF EXISTS idx_users_google_id;

            -- Make password_hash required again
            ALTER TABLE USERS ALTER COLUMN password_hash SET NOT NULL;

            -- Remove OAuth and token fields from users table
            ALTER TABLE USERS
            DROP COLUMN IF EXISTS password_reset_sent_at,
            DROP COLUMN IF EXISTS password_reset_token,
            DROP COLUMN IF EXISTS email_verification_sent_at,
            DROP COLUMN IF EXISTS email_verification_token,
            DROP COLUMN IF EXISTS email_verified,
            DROP COLUMN IF EXISTS avatar_url,
            DROP COLUMN IF EXISTS provider,
            DROP COLUMN IF EXISTS google_id;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Downgrade completed successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
