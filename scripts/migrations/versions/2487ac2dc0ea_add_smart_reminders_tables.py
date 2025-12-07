"""add_smart_reminders_tables

Revision ID: 2487ac2dc0ea
Revises: 6fc6b98c4223
Create Date: 2025-12-07 14:17:24.894482

"""
from alembic import op
import sqlalchemy as sa
from migrations.utils import database_connect


# revision identifiers, used by Alembic.
revision = '2487ac2dc0ea'
down_revision = '6fc6b98c4223'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            -- schedule_plans table
            CREATE TABLE IF NOT EXISTS schedule_plans (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                height_m DECIMAL(4,2),
                weight_kg DECIMAL(5,2),
                target_weight_kg DECIMAL(5,2),
                goal VARCHAR(20) NOT NULL,
                schedule_mode VARCHAR(20) NOT NULL DEFAULT 'fixed',
                selected_days TEXT[] NOT NULL,
                timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
                fixed_start_time TIME,
                fixed_end_time TIME,
                flexible_periods JSONB,
                sports_predefined TEXT[] NOT NULL,
                sports_custom TEXT[],
                weekly_plan JSONB,
                personal_notes TEXT,
                health_warnings TEXT,
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                deleted_at TIMESTAMPTZ
            );

            CREATE INDEX IF NOT EXISTS idx_schedule_plans_user
                ON schedule_plans(user_id) WHERE deleted_at IS NULL;
            CREATE INDEX IF NOT EXISTS idx_schedule_plans_status
                ON schedule_plans(user_id, status) WHERE status = 'active';
            CREATE UNIQUE INDEX IF NOT EXISTS idx_schedule_plans_unique_active
                ON schedule_plans(user_id)
                WHERE status = 'active' AND deleted_at IS NULL;

            DROP TRIGGER IF EXISTS update_schedule_plans_updated_at ON schedule_plans;
            CREATE TRIGGER update_schedule_plans_updated_at
                BEFORE UPDATE ON schedule_plans
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            -- scheduled_notifications table
            CREATE TABLE IF NOT EXISTS scheduled_notifications (
                id SERIAL PRIMARY KEY,
                schedule_plan_id INTEGER NOT NULL REFERENCES schedule_plans(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                scheduled_at TIMESTAMPTZ NOT NULL,
                workout_date DATE NOT NULL,
                workout_day VARCHAR(20) NOT NULL,
                workout_start_time TIME NOT NULL,
                workout_end_time TIME NOT NULL,
                title VARCHAR(255) NOT NULL,
                body TEXT NOT NULL,
                data JSONB,
                cloud_task_name VARCHAR(500),
                status VARCHAR(20) DEFAULT 'pending',
                sent_at TIMESTAMPTZ,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_notifications_pending
                ON scheduled_notifications(scheduled_at, status)
                WHERE status = 'pending';
            CREATE INDEX IF NOT EXISTS idx_notifications_user
                ON scheduled_notifications(user_id, workout_date);
            CREATE INDEX IF NOT EXISTS idx_notifications_plan
                ON scheduled_notifications(schedule_plan_id);

            DROP TRIGGER IF EXISTS update_notifications_updated_at ON scheduled_notifications;
            CREATE TRIGGER update_notifications_updated_at
                BEFORE UPDATE ON scheduled_notifications
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            -- user_devices table
            CREATE TABLE IF NOT EXISTS user_devices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                fcm_token TEXT NOT NULL,
                device_type VARCHAR(20),
                device_name VARCHAR(100),
                is_active BOOLEAN DEFAULT TRUE,
                last_used_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(user_id, fcm_token)
            );

            CREATE INDEX IF NOT EXISTS idx_devices_user_active
                ON user_devices(user_id) WHERE is_active = TRUE;

            DROP TRIGGER IF EXISTS update_devices_updated_at ON user_devices;
            CREATE TRIGGER update_devices_updated_at
                BEFORE UPDATE ON user_devices
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

            -- user_exercise_logs table
            CREATE TABLE IF NOT EXISTS user_exercise_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                scheduled_notification_id INTEGER REFERENCES scheduled_notifications(id) ON DELETE SET NULL,
                exercise_minutes INTEGER NOT NULL,
                calories INTEGER NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_exercise_logs_user_date
                ON user_exercise_logs(user_id, date);
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Smart reminders tables created")
    except Exception as ex:
        print(f"ERROR: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()


def downgrade() -> None:
    conn = database_connect()
    cur = conn.cursor()
    try:
        query = """
            DROP TRIGGER IF EXISTS update_devices_updated_at ON user_devices;
            DROP INDEX IF EXISTS idx_devices_user_active;
            DROP TABLE IF EXISTS user_devices;

            DROP TABLE IF EXISTS user_exercise_logs;
            DROP INDEX IF EXISTS idx_exercise_logs_user_date;

            DROP TRIGGER IF EXISTS update_notifications_updated_at ON scheduled_notifications;
            DROP INDEX IF EXISTS idx_notifications_plan;
            DROP INDEX IF EXISTS idx_notifications_user;
            DROP INDEX IF EXISTS idx_notifications_pending;
            DROP TABLE IF EXISTS scheduled_notifications;

            DROP TRIGGER IF EXISTS update_schedule_plans_updated_at ON schedule_plans;
            DROP INDEX IF EXISTS idx_schedule_plans_unique_active;
            DROP INDEX IF EXISTS idx_schedule_plans_status;
            DROP INDEX IF EXISTS idx_schedule_plans_user;
            DROP TABLE IF EXISTS schedule_plans;
        """
        cur.execute(query)
        conn.commit()
        print("SUCCESS: Smart reminders tables dropped")
    except Exception as ex:
        print(f"ERROR: {ex}")
        raise ex
    finally:
        cur.close()
        conn.close()
