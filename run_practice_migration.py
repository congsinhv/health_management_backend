"""
Standalone script to run practice table migration
"""
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set DATABASE_URI from DATABASE_URL if not set
if 'DATABASE_URI' not in os.environ and 'DATABASE_URL' in os.environ:
    os.environ['DATABASE_URI'] = os.environ['DATABASE_URL']

# Add the scripts directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

# Import and run the migration
from migrations.versions.f1a2b3c4d5e6_create_practice_table import upgrade

if __name__ == "__main__":
    print("=" * 60)
    print("Running Practice Table Migration")
    print("=" * 60)
    try:
        upgrade()
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ Migration failed: {e}")
        print("=" * 60)
        sys.exit(1)
