"""Init database

Revision ID: 904d1105f515
Revises:
Create Date: 2025-10-02 21:36:17.645623

"""

from migrations.utils import database_connect

# revision identifiers, used by Alembic.
revision = "904d1105f515"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial database schema with users table."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Create users table
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                deleted_at TIMESTAMP WITH TIME ZONE NULL
            );

            -- Create indexes for better performance
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
            WHERE deleted_at IS NULL;

            CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)
            WHERE deleted_at IS NULL;

            CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

            -- Create function to update updated_at timestamp
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';

            -- Create trigger to automatically update updated_at
            CREATE TRIGGER update_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();

            -- Insert a sample admin user (password: "admin123")
            -- Hash generated with bcrypt for "admin123"
            INSERT INTO users (
                email,
                first_name,
                last_name,
                password_hash,
                is_active
            )
            VALUES (
                'admin@health.com',
                'Admin',
                'User',
                '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj8g5KWGj2FO',
                TRUE
            ) ON CONFLICT (email) DO NOTHING;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Initial schema created successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Drop initial database schema."""
    conn = database_connect()
    cur = conn.cursor()

    try:
        query = """
            -- Drop trigger
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;

            -- Drop function
            DROP FUNCTION IF EXISTS update_updated_at_column();

            -- Drop indexes
            DROP INDEX IF EXISTS idx_users_created_at;
            DROP INDEX IF EXISTS idx_users_active;
            DROP INDEX IF EXISTS idx_users_email;

            -- Drop users table
            DROP TABLE IF EXISTS users;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Initial schema dropped successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
