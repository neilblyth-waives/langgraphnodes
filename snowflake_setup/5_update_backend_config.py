#!/usr/bin/env python3
"""
Update backend configuration to use Snowflake key pair authentication
"""
from pathlib import Path
import os

def update_env_file():
    """Update .env file with key pair authentication settings"""

    print("🔧 Updating Backend Configuration for Key Pair Auth")
    print("=" * 60)
    print()

    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_file = project_root / ".env"

    # Check for key in multiple locations
    local_key = script_dir / "rsa_key.p8"
    root_key = project_root / "rsa_key.p8"
    home_key = Path.home() / ".snowflake" / "rsa_key.p8"

    if local_key.exists():
        key_file = local_key
        print(f"✓ Using key from snowflake_setup/: {key_file}")
    elif root_key.exists():
        key_file = root_key
        print(f"✓ Using key from project root: {key_file}")
    elif home_key.exists():
        key_file = home_key
        print(f"✓ Using key from home: {key_file}")
    else:
        print(f"❌ Private key not found!")
        print(f"   Looked in: {local_key}")
        print(f"   Looked in: {root_key}")
        print(f"   Looked in: {home_key}")
        return False

    if not env_file.exists():
        print(f"❌ .env file not found at: {env_file}")
        return False

    # Read current .env
    print(f"Reading {env_file}...")
    with open(env_file, 'r') as f:
        lines = f.readlines()

    # Update lines
    new_lines = []
    updated_fields = []
    found_snowflake_section = False

    for line in lines:
        # Update Snowflake settings
        if line.startswith('SNOWFLAKE_USER='):
            new_lines.append('SNOWFLAKE_USER=neilb@sub2tech.com\n')
            updated_fields.append('SNOWFLAKE_USER')
            found_snowflake_section = True

        elif line.startswith('SNOWFLAKE_WAREHOUSE='):
            new_lines.append('SNOWFLAKE_WAREHOUSE=COMPUTE_WH_REPORTING\n')
            updated_fields.append('SNOWFLAKE_WAREHOUSE')

        elif line.startswith('SNOWFLAKE_ROLE='):
            new_lines.append('SNOWFLAKE_ROLE=ACCOUNTADMIN\n')
            updated_fields.append('SNOWFLAKE_ROLE')

        elif line.startswith('SNOWFLAKE_PASSWORD='):
            # Comment out password - not needed with key pair auth
            new_lines.append(f'# {line}# Not needed with key pair authentication\n')
            updated_fields.append('SNOWFLAKE_PASSWORD (commented out)')

        else:
            new_lines.append(line)

    # Add private key path if not present
    if 'SNOWFLAKE_PRIVATE_KEY_PATH' not in ''.join(lines):
        # Find where to insert (after Snowflake section)
        insert_idx = None
        for i, line in enumerate(new_lines):
            if line.startswith('# Memory Configuration') or line.startswith('# Session Management'):
                insert_idx = i
                break

        if insert_idx:
            new_lines.insert(insert_idx, f'\n# Key Pair Authentication (NO 2FA!)\n')
            new_lines.insert(insert_idx + 1, f'SNOWFLAKE_PRIVATE_KEY_PATH={key_file}\n')
            updated_fields.append('SNOWFLAKE_PRIVATE_KEY_PATH (added)')

    # Write back
    print("Updating .env file...")
    with open(env_file, 'w') as f:
        f.writelines(new_lines)

    print("✓ .env file updated")
    print()
    print("Updated fields:")
    for field in updated_fields:
        print(f"  ✓ {field}")
    print()

    # Show what was configured
    print("=" * 60)
    print("New Snowflake Configuration:")
    print("=" * 60)
    print(f"User: neilb@sub2tech.com")
    print(f"Account: ai60319.eu-west-1")
    print(f"Warehouse: COMPUTE_WH_REPORTING")
    print(f"Database: REPORTS")
    print(f"Schema: METRICS")
    print(f"Role: ACCOUNTADMIN")
    print(f"Private Key: {key_file}")
    print(f"Authentication: Key Pair (NO PASSWORD/2FA!)")
    print()

    return True


def show_next_steps():
    """Show next steps after configuration"""
    print("=" * 60)
    print("✅ Configuration Updated Successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print()
    print("1. Restart the backend to load new configuration:")
    print("   cd ..")
    print("   docker-compose restart backend")
    print()
    print("2. Test the connection from the backend:")
    print("   python3 snowflake_setup/6_test_backend_connection.py")
    print()
    print("3. Test a performance query:")
    print("   curl -X POST http://localhost:8000/api/chat/ \\")
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"message": "How is campaign 12345 performing?", "user_id": "test"}\'')
    print()


if __name__ == "__main__":
    success = update_env_file()
    if success:
        show_next_steps()
    exit(0 if success else 1)
