#!/usr/bin/env python3
"""
Test querying actual DV360 data from Snowflake
Verifies you can access the REPORTS.METRICS schema
"""
import snowflake.connector
from pathlib import Path
import sys

def test_dv360_queries():
    """Test querying DV360 campaign data"""

    print("📊 Testing DV360 Data Access")
    print("=" * 60)
    print()

    # Key file location - check multiple locations
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    local_key = script_dir / "rsa_key.p8"
    root_key = project_root / "rsa_key.p8"
    home_key = Path.home() / ".snowflake" / "rsa_key.p8"

    if local_key.exists():
        key_file_path = local_key
    elif root_key.exists():
        key_file_path = root_key
    elif home_key.exists():
        key_file_path = home_key
    else:
        print(f"❌ Private key not found!")
        print(f"   Looked in: {local_key}")
        print(f"   Looked in: {root_key}")
        print(f"   Looked in: {home_key}")
        return False

    try:
        # Read private key
        with open(key_file_path, "rb") as key_file:
            private_key = key_file.read()

        # Connect
        print("Connecting to Snowflake...")
        conn = snowflake.connector.connect(
            user='neilb@sub2tech.com',
            private_key=private_key,
            account='ai60319.eu-west-1',
            warehouse='COMPUTE_WH_REPORTING',
            database='REPORTS',
            role='ACCOUNTADMIN'
        )
        print("✓ Connected")
        print()

        cursor = conn.cursor()

        # Test 1: List available schemas
        print("[Test 1] Available Schemas in REPORTS database:")
        print("-" * 60)
        cursor.execute("SHOW SCHEMAS IN DATABASE REPORTS")
        schemas = cursor.fetchall()
        for schema in schemas[:10]:  # Show first 10
            print(f"  - {schema[1]}")
        print(f"  ... ({len(schemas)} total schemas)")
        print()

        # Test 2: List tables in METRICS schema
        print("[Test 2] Tables in REPORTS.METRICS schema:")
        print("-" * 60)
        cursor.execute("SHOW TABLES IN SCHEMA REPORTS.METRICS")
        tables = cursor.fetchall()

        if len(tables) == 0:
            print("  ⚠️  No tables found in METRICS schema")
            print()
            print("  Available schemas might be:")
            for schema in schemas[:5]:
                print(f"    - {schema[1]}")
            print()
            print("  Try checking these schemas for DV360 data.")
        else:
            for table in tables[:20]:  # Show first 20
                print(f"  - {table[1]}")
            print(f"  ... ({len(tables)} total tables)")
        print()

        # Test 3: Sample query on first available table
        if len(tables) > 0:
            first_table = tables[0][1]
            print(f"[Test 3] Sample data from {first_table}:")
            print("-" * 60)

            cursor.execute(f"""
                SELECT *
                FROM REPORTS.METRICS.{first_table}
                LIMIT 5
            """)

            # Get column names
            columns = [desc[0] for desc in cursor.description]
            print("Columns:", ", ".join(columns[:10]))  # Show first 10 columns
            print()

            rows = cursor.fetchall()
            print(f"Retrieved {len(rows)} sample rows")
            print()

        # Test 4: Check for campaign-related tables
        print("[Test 4] Looking for campaign-related tables:")
        print("-" * 60)
        campaign_tables = [t for t in tables if 'campaign' in t[1].lower() or 'dv360' in t[1].lower()]

        if campaign_tables:
            print("Found campaign tables:")
            for table in campaign_tables[:10]:
                print(f"  ✓ {table[1]}")
        else:
            print("  ⚠️  No tables with 'campaign' or 'dv360' in name")
            print()
            print("  Some table names from METRICS schema:")
            for table in tables[:10]:
                print(f"    - {table[1]}")
        print()

        # Test 5: Query execution time
        print("[Test 5] Query Performance Test:")
        print("-" * 60)
        import time
        start = time.time()
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = 'METRICS'")
        result = cursor.fetchone()
        duration = time.time() - start
        print(f"  Tables in METRICS: {result[0]}")
        print(f"  Query time: {duration:.2f} seconds")
        print()

        cursor.close()
        conn.close()

        print("=" * 60)
        print("✅ DV360 Data Access Test COMPLETED")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Note the table names that contain your DV360 data")
        print("  2. Update backend/src/tools/snowflake_tool.py with correct table names")
        print("  3. Run: python3 5_update_backend_config.py")
        print()

        return True

    except Exception as e:
        print()
        print("=" * 60)
        print("❌ Test FAILED")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_dv360_queries()
    exit(0 if success else 1)
