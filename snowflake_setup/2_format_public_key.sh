#!/bin/bash
# Step 2: Format the public key for Snowflake
# Removes BEGIN/END lines and newlines to create a single string

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check for private key in local directory first, then project root, then ~/.snowflake
LOCAL_KEY="$SCRIPT_DIR/rsa_key.p8"
ROOT_KEY="$PROJECT_ROOT/rsa_key.p8"
HOME_KEY="$HOME/.snowflake/rsa_key.p8"

if [ -f "$LOCAL_KEY" ]; then
    PRIV_KEY="$LOCAL_KEY"
    echo "✓ Found key in snowflake_setup/: $PRIV_KEY"
elif [ -f "$ROOT_KEY" ]; then
    PRIV_KEY="$ROOT_KEY"
    echo "✓ Found key in project root: $PRIV_KEY"
elif [ -f "$HOME_KEY" ]; then
    PRIV_KEY="$HOME_KEY"
    echo "✓ Found key in home: $PRIV_KEY"
else
    echo "❌ Private key not found!"
    echo "   Looked in: $LOCAL_KEY"
    echo "   Looked in: $ROOT_KEY"
    echo "   Looked in: $HOME_KEY"
    echo ""
    echo "Please ensure rsa_key.p8 exists in one of these locations"
    exit 1
fi

echo "🔑 Formatting public key for Snowflake..."
echo ""

# Generate public key from private key (temporary)
echo "Generating public key from private key..."
PUB_KEY_TEMP=$(mktemp)
openssl rsa -in "$PRIV_KEY" -pubout -out "$PUB_KEY_TEMP" 2>/dev/null

# Remove BEGIN/END lines and newlines
FORMATTED_KEY=$(grep -v "BEGIN PUBLIC KEY" "$PUB_KEY_TEMP" | grep -v "END PUBLIC KEY" | tr -d '\n')

# Clean up temp file
rm "$PUB_KEY_TEMP"

echo "=========================================="
echo "✅ Formatted Public Key (copy this):"
echo "=========================================="
echo ""
echo "$FORMATTED_KEY"
echo ""
echo "=========================================="
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Copy the key above (the long string)"
echo ""
echo "2. Log into Snowflake Web UI: https://app.snowflake.com/"
echo ""
echo "3. Run this SQL (replace YOUR_EMAIL with your Snowflake username):"
echo ""
echo "ALTER USER \"YOUR_EMAIL@DOMAIN.COM\" SET RSA_PUBLIC_KEY='$FORMATTED_KEY';"
echo ""
echo "4. Verify it was added:"
echo ""
echo "DESC USER \"YOUR_EMAIL@DOMAIN.COM\";"
echo ""
echo "5. Then run: python3 3_test_connection.py"
echo ""
