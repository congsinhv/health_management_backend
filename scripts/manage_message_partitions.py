#!/usr/bin/env python3
"""
Automated partition management for messages table.

This script:
1. Checks existing partitions
2. Creates missing partitions for current and future months
3. Can be run manually or via cron job
4. Prevents the "no partition found for row" error

Usage:
    python scripts/manage_message_partitions.py [--months-ahead N]

Examples:
    # Create partitions for next 6 months (default)
    python scripts/manage_message_partitions.py

    # Create partitions for next 12 months
    python scripts/manage_message_partitions.py --months-ahead 12
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from migrations.utils import database_connect


def get_existing_partitions(cur):
    """Get list of existing partition table names."""
    query = """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE '_messages_y%'
        ORDER BY tablename;
    """
    cur.execute(query)
    return [row[0] for row in cur.fetchall()]


def generate_partition_name(year: int, month: int) -> str:
    """Generate partition table name for given year and month."""
    return f"_messages_y{year}m{month:02d}"


def create_partition(cur, year: int, month: int) -> bool:
    """
    Create partition for specified year and month.

    Returns:
        bool: True if partition was created, False if already exists
    """
    partition_name = generate_partition_name(year, month)

    # Calculate date range for partition
    start_date = f"{year}-{month:02d}-01"

    # Calculate next month
    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1

    end_date = f"{next_year}-{next_month:02d}-01"

    # Create partition
    query = f"""
        CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF messages
        FOR VALUES FROM ('{start_date}') TO ('{end_date}');
    """

    try:
        cur.execute(query)
        return True
    except Exception as e:
        print(f"Error creating partition {partition_name}: {e}")
        return False


def ensure_partitions(months_ahead: int = 6) -> dict:
    """
    Ensure partitions exist for current month and N months ahead.

    Args:
        months_ahead: Number of future months to create partitions for

    Returns:
        dict: Summary of operations
    """
    conn = database_connect()
    cur = conn.cursor()

    try:
        # Get existing partitions
        existing_partitions = get_existing_partitions(cur)
        print(f"Existing partitions: {len(existing_partitions)}")
        for partition in existing_partitions:
            print(f"  - {partition}")

        # Generate list of months to ensure partitions for
        current_date = datetime.now()
        months_to_create = []

        for i in range(months_ahead + 1):  # +1 to include current month
            target_date = current_date + timedelta(days=30 * i)
            year = target_date.year
            month = target_date.month
            months_to_create.append((year, month))

        # Remove duplicates and sort
        months_to_create = sorted(set(months_to_create))

        # Create missing partitions
        created = []
        skipped = []

        for year, month in months_to_create:
            partition_name = generate_partition_name(year, month)

            if partition_name in existing_partitions:
                skipped.append(partition_name)
                print(f"Skipping existing partition: {partition_name}")
            else:
                print(f"Creating partition: {partition_name}")
                if create_partition(cur, year, month):
                    created.append(partition_name)
                    print(f"  ✓ Created: {partition_name}")

        # Commit changes
        conn.commit()

        return {
            "existing": len(existing_partitions),
            "created": len(created),
            "skipped": len(skipped),
            "total": len(existing_partitions) + len(created),
            "created_partitions": created,
            "skipped_partitions": skipped,
        }

    except Exception as e:
        print(f"Error managing partitions: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    """Main entry point for partition management."""
    parser = argparse.ArgumentParser(
        description="Manage message table partitions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create partitions for next 6 months (default)
  python scripts/manage_message_partitions.py

  # Create partitions for next 12 months
  python scripts/manage_message_partitions.py --months-ahead 12

  # Create partitions for next 3 months only
  python scripts/manage_message_partitions.py --months-ahead 3
        """,
    )

    parser.add_argument(
        "--months-ahead",
        type=int,
        default=6,
        help="Number of future months to create partitions for (default: 6)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Message Partition Management")
    print("=" * 60)
    print(f"Creating partitions for next {args.months_ahead} months...")
    print()

    try:
        result = ensure_partitions(months_ahead=args.months_ahead)

        print()
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Existing partitions: {result['existing']}")
        print(f"Created partitions:  {result['created']}")
        print(f"Skipped partitions:  {result['skipped']}")
        print(f"Total partitions:    {result['total']}")
        print()

        if result["created"]:
            print("Newly created partitions:")
            for partition in result["created_partitions"]:
                print(f"  ✓ {partition}")

        print()
        print("SUCCESS: Partition management completed successfully")
        return 0

    except Exception as e:
        print()
        print("ERROR: Partition management failed")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
