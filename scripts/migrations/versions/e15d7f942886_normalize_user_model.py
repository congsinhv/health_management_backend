"""normalize_user_model

Revision ID: e15d7f942886
Revises: cde7763a63b8
Create Date: 2025-01-27 12:00:00.000000

"""

from migrations.utils import database_connect


# revision identifiers, used by Alembic.
revision = "e15d7f942886"
down_revision = "cde7763a63b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Normalize user model by creating user_profiles table and moving profile fields."""
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- Create user_profiles table
            CREATE TABLE IF NOT EXISTS user_profiles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                first_name VARCHAR(50),
                last_name VARCHAR(50),
                avatar_url VARCHAR(500),
                gender VARCHAR(20),
                height_cm NUMERIC(5,2),
                weight_kg NUMERIC(5,2),
                date_of_birth DATE,
                family_medical_history TEXT,
                goal VARCHAR(255),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            -- Create index on user_id for faster lookups
            CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

            -- Create trigger to automatically update updated_at
            CREATE TRIGGER update_user_profiles_updated_at
            BEFORE UPDATE ON user_profiles
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();

            -- Migrate existing data from users to user_profiles
            INSERT INTO user_profiles (user_id, first_name, last_name, avatar_url, created_at, updated_at)
            SELECT id, first_name, last_name, avatar_url, created_at, updated_at
            FROM users
            WHERE deleted_at IS NULL;

            -- Drop the moved columns from users table
            ALTER TABLE users
            DROP COLUMN IF EXISTS first_name,
            DROP COLUMN IF EXISTS last_name,
            DROP COLUMN IF EXISTS avatar_url;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: User model normalization completed successfully")
    except Exception as ex:
        print(f"ERROR: Error in upgrade: {ex}")
        conn.rollback()
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    """Revert user model normalization by restoring columns to users table."""
    conn = database_connect()
    cur = conn.cursor()

    try:
        query = """
            -- Recreate columns in users table
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS first_name VARCHAR(50),
            ADD COLUMN IF NOT EXISTS last_name VARCHAR(50),
            ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500);

            -- Copy values back from user_profiles to users
            UPDATE users
            SET first_name = up.first_name,
                last_name = up.last_name,
                avatar_url = up.avatar_url
            FROM user_profiles up
            WHERE users.id = up.user_id AND users.deleted_at IS NULL;

            -- Drop trigger
            DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles;

            -- Drop index
            DROP INDEX IF EXISTS idx_user_profiles_user_id;

            -- Drop user_profiles table
            DROP TABLE IF EXISTS user_profiles;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: User model normalization reverted successfully")
    except Exception as ex:
        print(f"ERROR: Error in downgrade: {ex}")
        conn.rollback()
        raise ex
    finally:
        cur.close()
        conn.close()
