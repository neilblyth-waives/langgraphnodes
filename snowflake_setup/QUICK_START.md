# Snowflake Key Pair Setup - Quick Start Guide

## What You Have

✅ Private key file: `rsa_key.p8` (in this directory or `~/.snowflake/`)
✅ Test scripts ready to run
✅ Backend code updated to support key pair auth

## What You Need to Do

### 1. Format & Add Public Key to Snowflake (5 minutes)

```bash
cd snowflake_setup

# Generate public key from your private key
./2_format_public_key.sh
```

**Copy the long string it outputs**, then:

1. Go to https://app.snowflake.com/
2. Log in with your normal credentials (last time you'll need 2FA!)
3. Run this SQL:

```sql
ALTER USER "neilb@sub2tech.com"
SET RSA_PUBLIC_KEY='PASTE_THE_LONG_STRING_HERE';
```

4. Verify it worked:

```sql
DESC USER "neilb@sub2tech.com";
-- Look for RSA_PUBLIC_KEY_FP in the output
```

### 2. Test Connection (1 minute)

```bash
# Test direct connection (no backend)
python3 3_test_connection.py
```

Expected output:
```
✅ Connection Test PASSED!
🎉 Key pair authentication working - NO 2FA required!
```

### 3. Test Your Data (1 minute)

```bash
# See what tables you have available
python3 4_test_dv360_data.py
```

This shows all your tables in REPORTS.METRICS

### 4. Update Backend Config (1 minute)

```bash
# Update .env file with key pair settings
python3 5_update_backend_config.py
```

This updates:
- Warehouse → COMPUTE_WH_REPORTING
- Role → ACCOUNTADMIN
- Adds private key path
- Comments out password

### 5. Test Backend Connection (1 minute)

```bash
# Restart backend with new config
cd ..
docker-compose restart backend

# Test it
cd snowflake_setup
python3 6_test_backend_connection.py
```

Expected output:
```
✅ Backend Connection Test PASSED!
Your backend can now:
  ✓ Connect to Snowflake without 2FA
  ✓ Query data from your database
  ✓ Process campaign performance requests
```

### 6. Test End-to-End (1 minute)

```bash
# Send a chat message
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me available data sources", "user_id": "test"}'
```

---

## Complete Setup in One Command

If you want to run all tests at once:

```bash
cd snowflake_setup

# Run all tests (assuming public key is already in Snowflake)
python3 3_test_connection.py && \
python3 4_test_dv360_data.py && \
python3 5_update_backend_config.py && \
cd .. && docker-compose restart backend && cd snowflake_setup && \
python3 6_test_backend_connection.py
```

---

## Your Connection Pattern

The backend now uses YOUR EXACT pattern:

```python
# Read private key
with open("rsa_key.p8", "rb") as key_file:
    private_key = key_file.read()

# Connect (no password, no 2FA!)
conn = snowflake.connector.connect(
    user='neilb@sub2tech.com',
    private_key=private_key,
    account='ai60319.eu-west-1',
    warehouse='COMPUTE_WH_REPORTING',
    database='REPORTS',
    role='ACCOUNTADMIN'
)
```

---

## Troubleshooting

### Script fails with "JWT token is invalid"
→ Public key not added to Snowflake. Go back to step 1.

### Script fails with "Private key file not found"
→ Make sure `rsa_key.p8` is in `~/.snowflake/` directory

### Connection works but no data
→ Run `4_test_dv360_data.py` to see what tables exist
→ Update table names in `backend/src/tools/snowflake_tool.py`

---

## What Changed in Your Backend

**Before:**
- Used password authentication
- Required 2FA every time
- Connection would time out after ~100 seconds

**After:**
- Uses private key authentication
- NO 2FA prompts
- Fast, reliable connections
- More secure than passwords

---

## Files Modified

- ✅ `backend/src/tools/snowflake_tool.py` - Added key pair auth support
- ✅ `backend/src/core/config.py` - Added `snowflake_private_key_path` setting
- ✅ `.env` - Will be updated by script #5

---

## Security

Your private key (`rsa_key.p8`):
- ✅ Stored in `~/.snowflake/` (not in git)
- ✅ Has 600 permissions (only you can read)
- ✅ Never transmitted anywhere
- ✅ Added to `.gitignore`

---

## Next: Use Real DV360 Data

Once setup is complete:

1. **Find your campaign tables:**
   ```bash
   python3 4_test_dv360_data.py
   ```

2. **Update query templates** in `backend/src/tools/snowflake_tool.py`:
   - Replace `dv360_campaigns` with your actual table name
   - Update column names to match your schema

3. **Test performance query:**
   ```bash
   curl -X POST http://localhost:8000/api/chat/ \
     -H "Content-Type: application/json" \
     -d '{"message": "How is campaign 12345 performing?", "user_id": "test"}'
   ```

---

## Done! 🎉

You now have:
- ✅ Snowflake connection without 2FA
- ✅ Fast, reliable data access
- ✅ Working DV360 agent system
- ✅ No more manual authentication prompts

**Time to setup:** ~10 minutes total
**Time saved:** Every connection from now on!
