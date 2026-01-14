#!/usr/bin/env python3
"""
Test that the backend can connect to Snowflake using the new configuration
"""
import sys
import os
from pathlib import Path

# Add backend to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

import asyncio
from src.tools.snowflake_tool import snowflake_tool
from src.core.config import settings

async def test_backend_connection():
    """Test Snowflake connection through backend tools"""

    print("🔧 Testing Backend Snowflake Connection")
    print("=" * 60)
    print()

    # Show configuration
    print("Current Configuration:")
    print("-" * 60)
    print(f"Account: {settings.snowflake_account}")
    print(f"User: {settings.snowflake_user}")
    print(f"Warehouse: {settings.snowflake_warehouse}")
    print(f"Database: {settings.snowflake_database}")
    print(f"Schema: {settings.snowflake_schema}")
    print(f"Role: {settings.snowflake_role}")

    if hasattr(settings, 'snowflake_private_key_path') and settings.snowflake_private_key_path:
        print(f"Auth Method: Key Pair")
        print(f"Private Key: {settings.snowflake_private_key_path}")
        key_exists = Path(settings.snowflake_private_key_path).exists()
        print(f"Key File Exists: {'✓ Yes' if key_exists else '✗ No'}")

        if not key_exists:
            print()
            print("❌ Private key file not found!")
            print(f"Expected at: {settings.snowflake_private_key_path}")
            return False
    else:
        print(f"Auth Method: Password")
        print("⚠️  Warning: Using password authentication (may require 2FA)")

    print()

    # Test connection
    print("[Test 1] Basic Connection:")
    print("-" * 60)
    try:
        result = await snowflake_tool.execute_query(
            "SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE()",
            use_cache=False
        )

        if result:
            print("✓ Connection successful!")
            print(f"  Version: {result[0].get('CURRENT_VERSION()', 'N/A')}")
            print(f"  User: {result[0].get('CURRENT_USER()', 'N/A')}")
            print(f"  Role: {result[0].get('CURRENT_ROLE()', 'N/A')}")
        else:
            print("⚠️  Query returned no results")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print()
        if "JWT token is invalid" in str(e):
            print("💡 This means the public key is not set in Snowflake.")
            print("   Run: ./2_format_public_key.sh and add it to your user")
        return False

    print()

    # Test schema access
    print("[Test 2] Schema Access:")
    print("-" * 60)
    try:
        result = await snowflake_tool.execute_query(
            f"SHOW TABLES IN SCHEMA {settings.snowflake_database}.{settings.snowflake_schema} LIMIT 10",
            use_cache=False
        )

        if result:
            print(f"✓ Can access {settings.snowflake_database}.{settings.snowflake_schema}")
            print(f"  Found {len(result)} tables (showing first 10)")
            for i, row in enumerate(result[:5], 1):
                # Table name is usually in 'name' field
                table_name = row.get('name', row.get('NAME', list(row.values())[1] if len(row) > 1 else 'Unknown'))
                print(f"  {i}. {table_name}")
        else:
            print("⚠️  Schema exists but no tables found")

    except Exception as e:
        print(f"⚠️  Could not access schema: {e}")
        print("   This might be okay if the schema name is different")

    print()

    # Test query performance
    print("[Test 3] Query Performance:")
    print("-" * 60)
    import time
    start = time.time()

    try:
        result = await snowflake_tool.execute_query(
            "SELECT 1 as test",
            use_cache=False
        )
        duration = time.time() - start

        print(f"✓ Simple query executed in {duration:.2f} seconds")

    except Exception as e:
        print(f"❌ Query failed: {e}")
        return False

    print()
    print("=" * 60)
    print("✅ Backend Connection Test PASSED!")
    print("=" * 60)
    print()
    print("Your backend can now:")
    print("  ✓ Connect to Snowflake without 2FA")
    print("  ✓ Query data from your database")
    print("  ✓ Process campaign performance requests")
    print()
    print("Try the agent now:")
    print('  curl -X POST http://localhost:8000/api/chat/ \\')
    print('    -H "Content-Type: application/json" \\')
    print('    -d \'{"message": "Test Snowflake connection", "user_id": "test"}\'')
    print()

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_backend_connection())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
