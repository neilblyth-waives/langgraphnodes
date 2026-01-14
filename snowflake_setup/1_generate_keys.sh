#!/bin/bash
# Step 1: Generate RSA Key Pair for Snowflake Authentication
# This allows you to connect to Snowflake WITHOUT 2FA prompts

set -e  # Exit on error

echo "🔐 Generating Snowflake Key Pair..."
echo ""

# Create directory for keys
KEYS_DIR="$HOME/.snowflake"
mkdir -p "$KEYS_DIR"
echo "✓ Created keys directory: $KEYS_DIR"

# Generate private key (unencrypted for automation)
echo ""
echo "Generating private key..."
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out "$KEYS_DIR/rsa_key.p8" -nocrypt
echo "✓ Private key generated: $KEYS_DIR/rsa_key.p8"

# Generate public key from private key
echo ""
echo "Generating public key..."
openssl rsa -in "$KEYS_DIR/rsa_key.p8" -pubout -out "$KEYS_DIR/rsa_key.pub"
echo "✓ Public key generated: $KEYS_DIR/rsa_key.pub"

# Set proper permissions
echo ""
echo "Setting permissions..."
chmod 600 "$KEYS_DIR/rsa_key.p8"
chmod 644 "$KEYS_DIR/rsa_key.pub"
echo "✓ Permissions set (private key: 600, public key: 644)"

echo ""
echo "=========================================="
echo "✅ Keys generated successfully!"
echo "=========================================="
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Copy your public key to add to Snowflake:"
echo "   cat $KEYS_DIR/rsa_key.pub"
echo ""
echo "2. Remove the BEGIN/END lines and newlines to get a single string"
echo ""
echo "3. Run this SQL in Snowflake Web UI:"
echo "   ALTER USER \"your.email@domain.com\" SET RSA_PUBLIC_KEY='YOUR_PUBLIC_KEY_HERE';"
echo ""
echo "4. Run: ./2_format_public_key.sh to help format the key"
echo ""
