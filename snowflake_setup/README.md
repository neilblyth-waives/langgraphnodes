# Snowflake Key Pair Authentication Setup

This folder contains scripts to set up **Snowflake authentication WITHOUT 2FA** for your DV360 Agent System.

## Quick Start

Run these scripts in order:

```bash
cd snowflake_setup

# Step 1: Generate RSA key pair (if not already done)
chmod +x 1_generate_keys.sh
./1_generate_keys.sh

# Step 2: Format public key for Snowflake
chmod +x 2_format_public_key.sh
./2_format_public_key.sh
# Copy the output and add to Snowflake (see below)

# Step 3: Test direct connection
python3 3_test_connection.py

# Step 4: Test DV360 data access
python3 4_test_dv360_data.py

# Step 5: Update backend configuration
python3 5_update_backend_config.py

# Step 6: Test backend connection
python3 6_test_backend_connection.py
```

---

## Detailed Steps

### Step 1: Generate Keys (if needed)

If you already have `rsa_key.p8` in this directory or `~/.snowflake/`, skip this step.

```bash
./1_generate_keys.sh
```

This creates:
- `~/.snowflake/rsa_key.p8` - Private key (keep secret!)
- `~/.snowflake/rsa_key.pub` - Public key (add to Snowflake)

### Step 2: Add Public Key to Snowflake

```bash
./2_format_public_key.sh
```

This outputs your formatted public key. Copy it and:

1. Log into Snowflake: https://app.snowflake.com/
2. Run this SQL:

```sql
ALTER USER "neilb@sub2tech.com" SET RSA_PUBLIC_KEY='YOUR_LONG_KEY_STRING_HERE';
```

3. Verify it was added:

```sql
DESC USER "neilb@sub2tech.com";
-- Look for RSA_PUBLIC_KEY_FP in the output
```

### Step 3: Test Connection

```bash
python3 3_test_connection.py
```

Expected output:
```
✅ Connection Test PASSED!
Snowflake Version: 9.40.7
Connected as User: NEILB@SUB2TECH.COM
Active Role: ACCOUNTADMIN
🎉 Key pair authentication working - NO 2FA required!
```

### Step 4: Test DV360 Data Access

```bash
python3 4_test_dv360_data.py
```

This shows:
- Available schemas in REPORTS database
- Tables in METRICS schema
- Sample data from tables
- Campaign-related tables

### Step 5: Update Backend Config

```bash
python3 5_update_backend_config.py
```

This updates your `.env` file to use:
- Key pair authentication (no password)
- Correct warehouse: COMPUTE_WH_REPORTING
- Correct role: ACCOUNTADMIN

### Step 6: Test Backend Connection

```bash
python3 6_test_backend_connection.py
```

This verifies the backend can connect using the new configuration.

---

## Your Connection Details

```python
conn = snowflake.connector.connect(
    user='neilb@sub2tech.com',
    private_key=private_key,  # Read from rsa_key.p8
    account='ai60319.eu-west-1',
    warehouse='COMPUTE_WH_REPORTING',
    database='REPORTS',
    role='ACCOUNTADMIN'
)
```

---

## Troubleshooting

### "JWT token is invalid"

**Problem:** Public key not added to Snowflake user

**Solution:**
1. Run `./2_format_public_key.sh`
2. Copy the formatted key
3. Run in Snowflake: `ALTER USER "neilb@sub2tech.com" SET RSA_PUBLIC_KEY='...';`
4. Make sure you removed BEGIN/END lines and newlines

### "Private key file not found"

**Problem:** Key file missing

**Solution:**
- Run `./1_generate_keys.sh` to generate new keys
- Or copy your existing `rsa_key.p8` to `~/.snowflake/`

### "250001: Could not connect"

**Problem:** Network connection issue

**Solution:**
- Check account identifier: `ai60319.eu-west-1`
- Verify you can access: https://ai60319.eu-west-1.snowflakecomputing.com
- Check VPN/firewall settings

### Connection works but queries fail

**Problem:** Wrong schema or table names

**Solution:**
- Run `./4_test_dv360_data.py` to see actual table names
- Update `backend/src/tools/snowflake_tool.py` with correct names

---

## Security Notes

✅ **DO:**
- Keep `rsa_key.p8` secure (it's in `.gitignore`)
- Use file permissions `600` on private key
- Generate different keys for dev/prod

❌ **DON'T:**
- Commit private keys to git
- Share keys via email/Slack
- Use same key across multiple users

---

## Files in this Directory

- `1_generate_keys.sh` - Generate RSA key pair
- `2_format_public_key.sh` - Format public key for Snowflake
- `3_test_connection.py` - Test basic connection
- `4_test_dv360_data.py` - Test data access
- `5_update_backend_config.py` - Update .env file
- `6_test_backend_connection.py` - Test backend connection
- `README.md` - This file

---

## Next Steps After Setup

Once all tests pass:

1. **Restart the backend:**
   ```bash
   cd ..
   docker-compose restart backend
   ```

2. **Test through the API:**
   ```bash
   curl -X POST http://localhost:8000/api/chat/ \
     -H "Content-Type: application/json" \
     -d '{"message": "How is campaign 12345 performing?", "user_id": "test"}'
   ```

3. **No more 2FA prompts!** 🎉

---

## Support

If you encounter issues:
1. Check each test script output for specific error messages
2. Verify your public key is correctly added in Snowflake
3. Ensure the private key file exists and has correct permissions
4. Check the backend logs: `docker-compose logs backend`
