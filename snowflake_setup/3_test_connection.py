#!/usr/bin/env python3
"""
Test Snowflake connection with key pair authentication
Uses your exact connection pattern
"""
import snowflake.connector
import os
from pathlib import Path

def test_connection():
    """Test basic Snowflake connection with key pair auth"""

    print("🔐 Testing Snowflake Key Pair Authentication")
    print("=" * 60)
    print()

    # Key file location - check multiple locations
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # Priority order: script dir, project root, ~/.snowflake
    local_key = script_dir / "rsa_key.p8"
    root_key = project_root / "rsa_key.p8"
    home_key = Path.home() / ".snowflake" / "rsa_key.p8"

    if local_key.exists():
        key_file_path = local_key
        print(f"✓ Using key from snowflake_setup/: {key_file_path}")
    elif root_key.exists():
        key_file_path = root_key
        print(f"✓ Using key from project root: {key_file_path}")
    elif home_key.exists():
        key_file_path = home_key
        print(f"✓ Using key from home: {key_file_path}")
    else:
        print(f"❌ Private key not found!")
        print(f"   Looked in: {local_key}")
        print(f"   Looked in: {root_key}")
        print(f"   Looked in: {home_key}")
        print()
        print("Please ensure rsa_key.p8 exists in one of these locations")
        return False

    print(f"✓ Found private key at: {key_file_path}")
    print()

    try:
        # Read the private key
        print("Reading private key...")
        with open(key_file_path, "rb") as key_file:
            private_key = key_file.read()

        print("✓ Private key loaded")
        print()

        # Connect to Snowflake (YOUR EXACT PATTERN)
        print("Connecting to Snowflake...")
        print(f"  User: neilb@sub2tech.com")
        print(f"  Account: ai60319.eu-west-1")
        print(f"  Warehouse: COMPUTE_WH_REPORTING")
        print(f"  Database: REPORTS")
        print(f"  Role: ACCOUNTADMIN")
        print()

        conn = snowflake.connector.connect(
            user='neilb@sub2tech.com',
            private_key=private_key,
            account='ai60319.eu-west-1',
            warehouse='COMPUTE_WH_REPORTING',
            database='REPORTS',
            role='ACCOUNTADMIN'
        )

        print("✓ Connected successfully!")
        print()

        # Test a simple query
        print("Running test query...")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                CURRENT_VERSION() as version,
                CURRENT_USER() as user,
                CURRENT_ROLE() as role,
                CURRENT_DATABASE() as database,
                CURRENT_WAREHOUSE() as warehouse
        """)

        result = cursor.fetchone()

        print()
        print("=" * 60)
        print("✅ Connection Test PASSED!")
        print("=" * 60)
        print()
        print(f"Snowflake Version: {result[0]}")
        print(f"Connected as User: {result[1]}")
        print(f"Active Role: {result[2]}")
        print(f"Database: {result[3]}")
        print(f"Warehouse: {result[4]}")
        print()
        print("🎉 Key pair authentication working - NO 2FA required!")
        print()

        cursor.close()
        conn.close()

        return True

    except snowflake.connector.errors.DatabaseError as e:
        print()
        print("=" * 60)
        print("❌ Connection FAILED")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()

        if "JWT token is invalid" in str(e):
            print("💡 This usually means:")
            print("   1. Public key not added to Snowflake user")
            print("   2. Public key format is incorrect")
            print()
            print("Solutions:")
            print("   - Run: ./2_format_public_key.sh")
            print("   - Copy the formatted key")
            print("   - Run in Snowflake:")
            print('     ALTER USER "neilb@sub2tech.com" SET RSA_PUBLIC_KEY=\'YOUR_KEY\';')

        elif "250001" in str(e):
            print("💡 Network connection issue:")
            print("   - Check account identifier: ai60319.eu-west-1")
            print("   - Verify you can access https://ai60319.eu-west-1.snowflakecomputing.com")
            print("   - Check firewall/VPN settings")

        return False

    except Exception as e:
        print()
        print(f"❌ Unexpected error: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_connection()
    exit(0 if success else 1)
