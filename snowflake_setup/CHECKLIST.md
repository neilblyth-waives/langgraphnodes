# Snowflake Key Pair Setup - Step-by-Step Checklist

Use this checklist to track your progress through the setup.

---

## Pre-Setup

- [x] Private key file exists (`rsa_key.p8` added to directory)
- [ ] Private key is in `~/.snowflake/` OR in `snowflake_setup/`

---

## Step 1: Format Public Key (2 min)

```bash
cd snowflake_setup
./2_format_public_key.sh
```

- [ ] Script ran successfully
- [ ] Copied the long public key string (starts with "MIIB...")

---

## Step 2: Add Key to Snowflake (3 min)

1. Go to: https://app.snowflake.com/
2. Log in with username/password + 2FA (last time!)
3. Run this SQL:

```sql
ALTER USER "neilb@sub2tech.com"
SET RSA_PUBLIC_KEY='PASTE_YOUR_KEY_HERE';
```

4. Verify it was added:

```sql
DESC USER "neilb@sub2tech.com";
```

**Checklist:**
- [ ] Logged into Snowflake Web UI
- [ ] Ran ALTER USER command
- [ ] Saw RSA_PUBLIC_KEY_FP in DESC USER output

---

## Step 3: Test Direct Connection (1 min)

```bash
python3 3_test_connection.py
```

**Expected Output:**
```
✅ Connection Test PASSED!
🎉 Key pair authentication working - NO 2FA required!
```

**Checklist:**
- [ ] Script ran without errors
- [ ] Saw "Connection Test PASSED"
- [ ] Confirmed NO 2FA was required

**If it failed:**
- Check error message in output
- Common issue: Public key not added correctly (go back to Step 2)
- Run: `cat QUICK_START.md` for troubleshooting

---

## Step 4: Check Available Data (2 min)

```bash
python3 4_test_dv360_data.py
```

**This shows:**
- Available schemas in REPORTS database
- Tables in METRICS schema
- Sample data

**Checklist:**
- [ ] Script ran successfully
- [ ] Saw list of tables in METRICS schema
- [ ] Made note of table names for later (write them down):
  - Campaign table: _______________
  - Performance table: _______________
  - Other tables: _______________

---

## Step 5: Update Backend Config (1 min)

```bash
python3 5_update_backend_config.py
```

**This updates:**
- Warehouse → COMPUTE_WH_REPORTING
- Role → ACCOUNTADMIN
- Adds private key path to .env
- Comments out password

**Checklist:**
- [ ] Script completed successfully
- [ ] Saw "Configuration Updated Successfully"
- [ ] Backed up old .env (optional): `cp ../.env ../.env.backup`

---

## Step 6: Restart Backend (1 min)

```bash
cd ..
docker-compose restart backend
sleep 5  # Wait for restart
```

**Checklist:**
- [ ] Container restarted successfully
- [ ] Check logs: `docker-compose logs backend --tail=20`
- [ ] Look for: "Snowflake initialized with key pair authentication"

---

## Step 7: Test Backend Connection (1 min)

```bash
cd snowflake_setup
python3 6_test_backend_connection.py
```

**Expected Output:**
```
✅ Backend Connection Test PASSED!
Your backend can now:
  ✓ Connect to Snowflake without 2FA
  ✓ Query data from your database
```

**Checklist:**
- [ ] Script ran successfully
- [ ] Saw "Backend Connection Test PASSED"
- [ ] No errors in output

---

## Step 8: Test End-to-End (1 min)

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me Snowflake connection status", "user_id": "test"}'
```

**Checklist:**
- [ ] Got a 200 response
- [ ] Response mentions Snowflake or data sources
- [ ] No 2FA prompt occurred

---

## Final Verification

Run the complete test suite:

```bash
cd ..
python3 test_e2e.py
```

**Checklist:**
- [ ] All tests passed
- [ ] Chat message test completed in < 10 seconds (no 100s timeout!)
- [ ] Response included Snowflake data or graceful error

---

## Setup Complete! ✅

You should have:
- [x] Backend configured for key pair auth
- [x] No 2FA required for connections
- [x] Faster, more reliable Snowflake access
- [x] Agent system can query DV360 data

---

## Next Steps (Optional)

### Update Table Names

If your DV360 tables have different names than the defaults:

1. Open: `backend/src/tools/snowflake_tool.py`
2. Find the query methods (search for "dv360_campaigns")
3. Replace with your actual table names from Step 4

### Test with Real Campaign ID

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "How is campaign REAL_CAMPAIGN_ID performing?", "user_id": "test"}'
```

Replace `REAL_CAMPAIGN_ID` with an actual campaign ID from your data.

---

## Troubleshooting

### "JWT token is invalid"
→ Public key not added to Snowflake. Repeat Step 2.

### "Private key file not found"
→ Check key location:
```bash
ls -la ~/.snowflake/rsa_key.p8
# OR
ls -la snowflake_setup/rsa_key.p8
```

### Connection timeout
→ Check network access to Snowflake:
```bash
curl -I https://ai60319.eu-west-1.snowflakecomputing.com
```

### Backend not picking up changes
→ Full restart:
```bash
docker-compose down
docker-compose up -d
```

---

## Need Help?

📖 Read: `QUICK_START.md` for detailed setup guide
📖 Read: `README.md` for full documentation
🐛 Check: `docker-compose logs backend` for errors

---

## Success Criteria

✅ You can run `python3 3_test_connection.py` successfully
✅ No 2FA prompts appear
✅ Backend connects to Snowflake in < 5 seconds
✅ Chat API returns responses with Snowflake data

**Time to complete:** ~10-15 minutes
**Time saved:** Every connection from now on! 🎉
