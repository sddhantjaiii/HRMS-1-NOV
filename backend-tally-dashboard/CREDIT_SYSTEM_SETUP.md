# Credit System Setup - Quick Guide

## ✅ What's Been Implemented

Your HRMS now has **automatic credit deduction** that works even when Railway server sleeps!

### Changes Made:

1. **New Middleware Created** (`excel_data/middleware/credit_check_middleware.py`)
   - `AutoCreditDeductionMiddleware` - Auto-deducts credits on any request
   - `CreditEnforcementMiddleware` - Logs warnings for low credits

2. **Settings Updated** (`dashboard/settings.py`)
   - Added credit middlewares to `MIDDLEWARE` list

3. **New Management Command** (`excel_data/management/commands/check_credits.py`)
   - Check credit status anytime
   - Test credit deduction
   - Clear cache

4. **Documentation Created** (`docs/CREDIT_SYSTEM.md`)
   - Complete system overview
   - Troubleshooting guide
   - Testing procedures

---

## 🚀 How to Use

### 1. Check Credit Status
```bash
# View all tenants
python manage.py check_credits

# Check specific tenant
python manage.py check_credits --tenant-id 1

# Test deduction
python manage.py check_credits --test-deduct
```

### 2. No Additional Setup Needed!
The middleware is already active. Credits will automatically deduct when:
- Server wakes from sleep
- User makes first request of the day
- Any authenticated request occurs

### 3. Monitor Credits
```bash
# Check status regularly
python manage.py check_credits

# Look for warnings in logs
grep "Low credits" logs/app.log
```

---

## 🎯 Railway Deployment

### ✅ You Can Now:
1. **Enable server sleep** on Railway (save costs)
2. **Let server sleep after 10 min** of inactivity
3. **Credits still deduct** automatically when server wakes

### ❌ No Need For:
- External cron services
- Paid Railway cron jobs
- Always-on server (expensive)
- Manual credit processing

---

## 🧪 Testing

### Quick Test:
```bash
# 1. Check current credits
python manage.py check_credits

# 2. Simulate yesterday (in Django shell)
python manage.py shell
>>> from excel_data.models import Tenant
>>> from django.utils import timezone
>>> from datetime import timedelta
>>> tenant = Tenant.objects.first()
>>> tenant.updated_at = timezone.now() - timedelta(days=1)
>>> tenant.save()
>>> exit()

# 3. Clear cache and test
python manage.py check_credits --clear-cache --test-deduct

# 4. Verify deduction worked
python manage.py check_credits
```

---

## 📊 Example Output

```bash
$ python manage.py check_credits

================================================================================
CREDIT SYSTEM STATUS CHECK
================================================================================

🕐 Current Time:
   UTC: 2025-11-01 08:30:00 UTC
   IST: 2025-11-01 14:00:00 IST

📊 Total Tenants: 3

🟢 Tenant: Acme Corp (ID: 1)
   Status: ACTIVE
   Credits: 25
   Active: True
   Last Updated: 2025-11-01 09:00:00 IST
   Cache Status: ✓ Checked recently (within last hour)
   ✓ Up to date (no deduction needed today)

🟡 Tenant: Demo Inc (ID: 2)
   Status: LOW CREDITS
   Credits: 4
   Active: True
   Last Updated: 2025-10-31 15:30:00 IST
   Cache Status: ✗ Not in cache
   ⚠️  DEDUCTION DUE: Credit will be deducted on next request

🔴 Tenant: Old Company (ID: 3)
   Status: INACTIVE
   Credits: 0
   Active: False
   Last Updated: 2025-10-28 10:00:00 IST
   Cache Status: ✗ Not in cache
   ℹ️  No credits to deduct

================================================================================
SUMMARY
================================================================================
🟢 Active Tenants: 2
🟡 Low Credit Tenants (≤5): 1
⚫ Zero Credit Tenants: 1
🔴 Inactive Tenants: 1

💡 Tip: Use --test-deduct to actually deduct credits for tenants that are due
================================================================================
```

---

## 🔧 Configuration (Already Done)

### Middleware Order in `settings.py`:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'excel_data.middleware.tenant_middleware.TenantMiddleware',
    'excel_data.middleware.credit_check_middleware.AutoCreditDeductionMiddleware',  # ✅ NEW
    'excel_data.middleware.credit_check_middleware.CreditEnforcementMiddleware',    # ✅ NEW
    'excel_data.middleware.session_middleware.SingleSessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

---

## 📝 What Happens Now

### Daily Flow:
```
Day 1, 11:00 PM → User logs out, server sleeps
Day 2, 9:00 AM  → User logs in
                  ↓
            Server wakes up
                  ↓
     AuthenticationMiddleware runs
                  ↓
   AutoCreditDeductionMiddleware runs
                  ↓
        Checks last update (Day 1)
                  ↓
      Detects new day (Day 2)
                  ↓
         Deducts 1 credit
                  ↓
     Logs: "Auto-deducted credit for tenant..."
                  ↓
      Caches check for 1 hour
                  ↓
        User proceeds with login
```

### Subsequent Requests (Same Day):
```
Same day, 10:00 AM → User makes another request
                      ↓
           Middleware checks cache
                      ↓
          Cache hit (checked recently)
                      ↓
           Skips deduction check
                      ↓
          Request continues
```

---

## ⚠️ Important Notes

### Credit Deduction Rules:
1. **1 credit per day** (IST timezone)
2. Only deducts if **new day** since last update
3. **Cached for 1 hour** per tenant (reduces DB load)
4. **Thread-safe** (database locking prevents duplicates)

### When Credits Reach Zero:
1. Tenant `is_active` = `False`
2. All tenant users deactivated
3. Login blocked with message: "Company account has no credits"

### Adding Credits Back:
```python
python manage.py shell
>>> from excel_data.models import Tenant
>>> tenant = Tenant.objects.get(id=1)
>>> tenant.add_credits(30)  # Adds 30 credits
>>> # Tenant and users automatically reactivated
```

---

## 🎉 Benefits

✅ **Automatic** - No manual intervention needed  
✅ **Server Sleep Compatible** - Works with Railway free tier  
✅ **Cost Effective** - No paid cron services required  
✅ **Reliable** - Cache + database locking prevents issues  
✅ **Monitored** - Comprehensive logging and status checks  
✅ **Tested** - Built-in testing commands  

---

## 📚 Full Documentation

For complete details, see: `docs/CREDIT_SYSTEM.md`

---

## 🆘 Need Help?

### Common Issues:

**Q: Credits not deducting?**
```bash
python manage.py check_credits --clear-cache --test-deduct
```

**Q: Multiple deductions in one day?**
Check logs for errors:
```bash
grep "Auto-deducted credit" logs/app.log
```

**Q: Want to manually trigger deduction?**
```bash
python manage.py process_daily_credits
```

---

## ✨ You're All Set!

Your credit system is now fully functional and compatible with Railway's server sleep feature. Deploy with confidence! 🚀
