# Credit System Documentation

## 📋 Overview

The HRMS Credit System manages access control through a daily credit deduction model. Each tenant (company) receives credits, and **1 credit is automatically deducted per day**. When credits reach zero, the tenant and all associated users are deactivated.

## 🔄 How It Works

### Credit Deduction Logic

**Location:** `excel_data/models/tenant.py` - `deduct_daily_credit()` method

#### Key Features:
- ✅ **Daily Deduction**: 1 credit per day (based on IST timezone)
- ✅ **Automatic**: Triggers on any authenticated request via middleware
- ✅ **Server Sleep Compatible**: Works even when server is inactive
- ✅ **Thread-Safe**: Uses database locking to prevent race conditions
- ✅ **Cached**: Checks once per hour per tenant to reduce database load

#### Deduction Rules:
1. Credits only deduct if it's a new day (compares last update date)
2. Only deducts if `credits > 0`
3. When credits reach `0`:
   - Tenant is marked as `is_active = False`
   - ALL users under that tenant are deactivated
   - Login is blocked with "no credits" message

---

## 🛡️ Implementation (Option 4)

### Auto-Deduction on Server Wake

The system uses **middleware-based credit checking** that works even when the server sleeps.

### Architecture:

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Makes Request                          │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│         AuthenticationMiddleware (Django)                        │
│         Authenticates user and loads tenant                      │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│      AutoCreditDeductionMiddleware (Custom)                      │
│                                                                   │
│  1. Checks if user is authenticated                              │
│  2. Gets tenant from user                                        │
│  3. Checks cache (credit_checked_{tenant_id})                   │
│  4. If not in cache:                                             │
│     - Calls tenant.deduct_daily_credit()                        │
│     - Deducts 1 credit if it's a new day                        │
│     - Logs the deduction                                         │
│     - Stores check in cache (1 hour TTL)                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│      CreditEnforcementMiddleware (Custom)                        │
│                                                                   │
│  1. Logs warning if credits ≤ 5                                  │
│  2. Allows request to continue (login blocks zero credits)      │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
                 View Processing
```

### Components:

#### 1. **AutoCreditDeductionMiddleware**
**File:** `excel_data/middleware/credit_check_middleware.py`

**Purpose:** Automatically checks and deducts credits on any authenticated request

**Features:**
- Runs on **every authenticated request**
- Uses **caching** (1-hour TTL) to prevent excessive database checks
- Thread-safe and database-locked
- Logs all deductions

**Cache Strategy:**
```python
Cache Key: credit_checked_{tenant_id}
TTL: 3600 seconds (1 hour)
Purpose: Prevents checking same tenant multiple times per hour
```

#### 2. **CreditEnforcementMiddleware**
**File:** `excel_data/middleware/credit_check_middleware.py`

**Purpose:** Provides additional monitoring and warnings

**Features:**
- Logs warnings when credits ≤ 5
- Allows admin/auth paths without credit checks
- Non-blocking (doesn't prevent requests)

#### 3. **Login-Time Credit Check**
**File:** `excel_data/views/auth.py` (lines 140-148)

**Purpose:** Final enforcement - blocks login if no credits

```python
if user.tenant.credits <= 0:
    return Response({
        "error": "Company account has no credits...",
        "no_credits": True,
        "credits": user.tenant.credits
    }, status=403)
```

---

## 🚀 Server Sleep Compatibility

### Problem Solved:
Traditional cron jobs **don't work** when Railway server sleeps. This middleware-based approach ensures credits are deducted whenever:
- Server wakes from sleep
- User makes first request of the day
- Any authenticated request occurs

### How It Works with Sleep:

#### Scenario 1: Server Sleeps at Night
```
Day 1, 11:00 PM - Last request, server active
Day 1, 11:01 PM - Server goes to sleep (no activity)
Day 2, 9:00 AM  - User logs in
                  → Server wakes up
                  → Middleware detects new day
                  → Deducts 1 credit automatically
                  → User proceeds with login
```

#### Scenario 2: Multi-Day Sleep
```
Day 1, 6:00 PM  - Last request
Day 1-Day 4     - Server sleeps (no requests)
Day 5, 10:00 AM - User logs in
                  → Middleware checks last update (Day 1)
                  → Deducts 1 credit (only for Day 2)
                  → Subsequent requests won't deduct again today
```

**Note:** Only **1 credit per day** is deducted, even if server sleeps multiple days.

---

## 📊 Management Commands

### 1. Check Credit Status
```bash
# View all tenant credit status
python manage.py check_credits

# Check specific tenant
python manage.py check_credits --tenant-id 1

# Test deduction (actually deduct if due)
python manage.py check_credits --test-deduct

# Clear cache and check
python manage.py check_credits --clear-cache --test-deduct
```

**Output Example:**
```
🟢 Tenant: Acme Corp (ID: 1)
   Status: ACTIVE
   Credits: 15
   Active: True
   Last Updated: 2025-10-31 14:30:00 IST
   Cache Status: ✓ Checked recently
   ✓ Up to date (no deduction needed today)

🟡 Tenant: Demo Inc (ID: 2)
   Status: LOW CREDITS
   Credits: 3
   Active: True
   Last Updated: 2025-10-30 09:15:00 IST
   Cache Status: ✗ Not in cache
   ⚠️  DEDUCTION DUE: Credit will be deducted on next request
```

### 2. Process All Daily Credits (Manual)
```bash
# Manually trigger daily credit processing for all tenants
python manage.py process_daily_credits
```

**Use Case:** If you want to force credit deduction for all tenants at once (not needed with middleware).

---

## 🧪 Testing

### Test Credit Deduction

1. **Check current status:**
```bash
python manage.py check_credits
```

2. **Simulate day change** (for testing):
```python
# In Django shell
python manage.py shell

from excel_data.models import Tenant
from django.utils import timezone
from datetime import timedelta

# Get tenant
tenant = Tenant.objects.get(id=1)

# Set last update to yesterday
tenant.updated_at = timezone.now() - timedelta(days=1)
tenant.save()

# Now trigger deduction
tenant.deduct_daily_credit()
print(f"Credits remaining: {tenant.credits}")
```

3. **Test middleware:**
```bash
# Clear cache
python manage.py check_credits --clear-cache

# Make request (login or any API call)
# Check logs for deduction
tail -f logs/app.log
```

### Test Server Sleep Scenario

1. **Setup:**
   - Deploy to Railway with sleep enabled
   - Note last request time

2. **Let server sleep:**
   - Wait 10+ minutes with no requests
   - Server should go to sleep

3. **Wake server:**
   - Make login request
   - Check response (should succeed if credits available)

4. **Verify deduction:**
```bash
python manage.py check_credits --tenant-id 1
```

---

## 📝 Configuration

### Middleware Settings
**File:** `dashboard/settings.py`

```python
MIDDLEWARE = [
    # ... other middleware ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'excel_data.middleware.tenant_middleware.TenantMiddleware',
    'excel_data.middleware.credit_check_middleware.AutoCreditDeductionMiddleware',  # Credit auto-deduction
    'excel_data.middleware.credit_check_middleware.CreditEnforcementMiddleware',  # Credit warnings
    # ... other middleware ...
]
```

### Cache Settings
**File:** `dashboard/settings.py`

Ensure cache is configured (default: local memory):
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

For production (optional - Redis recommended):
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

### Timezone Settings
Credits are deducted based on **IST (Indian Standard Time)**:
```python
# In tenant.py
def get_ist_time(self):
    ist = pytz.timezone('Asia/Kolkata')
    return timezone.now().astimezone(ist)
```

---

## 🔧 Troubleshooting

### Credits Not Deducting?

1. **Check middleware is installed:**
```bash
python manage.py check
```

2. **Clear cache:**
```bash
python manage.py check_credits --clear-cache
```

3. **Check tenant last update:**
```bash
python manage.py check_credits --tenant-id YOUR_TENANT_ID
```

4. **Check logs:**
```bash
# Look for middleware messages
grep "Auto-deducted credit" logs/app.log
```

### Multiple Deductions in One Day?

**This shouldn't happen!** The system uses:
- Date comparison (only deducts if new day)
- Cache (prevents multiple checks per hour)
- Database locking (prevents race conditions)

If it occurs:
1. Check system timezone settings
2. Check if `updated_at` field is updating correctly
3. Review logs for errors

### Tenant Deactivated But Still Has Credits?

Check if `is_active` was manually set to `False`:
```python
python manage.py shell

from excel_data.models import Tenant
tenant = Tenant.objects.get(id=YOUR_ID)
print(f"Credits: {tenant.credits}")
print(f"Active: {tenant.is_active}")

# Reactivate if needed
tenant.is_active = True
tenant.save()
```

---

## 📈 Monitoring

### Key Metrics to Monitor:

1. **Active Tenants:** `Tenant.objects.filter(is_active=True).count()`
2. **Low Credit Tenants:** `Tenant.objects.filter(credits__lte=5, credits__gt=0).count()`
3. **Zero Credit Tenants:** `Tenant.objects.filter(credits=0).count()`
4. **Daily Deductions:** Check logs for "Auto-deducted credit" entries

### Recommended Monitoring:
```bash
# Daily health check
python manage.py check_credits > /var/log/hrms/credit_status.log

# Alert on low credits
python manage.py check_credits | grep "LOW CREDITS"
```

---

## 🎯 Best Practices

### For Development:
1. Test with multiple tenants
2. Simulate date changes
3. Test cache clearing
4. Verify logs are written

### For Production:
1. Monitor credit levels daily
2. Set up alerts for low credits
3. Keep logs for audit trail
4. Use Redis cache for better performance

### For Railway Deployment:
1. ✅ Enable server sleep (cost savings)
2. ✅ Middleware handles wake-up deductions
3. ✅ No need for external cron services
4. ✅ No additional costs required

---

## 🔐 Security Considerations

1. **Thread Safety:** Uses `select_for_update()` for database locking
2. **Cache Security:** Credit checks cached per tenant (no cross-tenant data)
3. **Login Enforcement:** Final check at login prevents zero-credit access
4. **Audit Trail:** All deductions logged with tenant info

---

## 📚 Related Files

- `excel_data/models/tenant.py` - Credit deduction logic
- `excel_data/middleware/credit_check_middleware.py` - Auto-deduction middleware
- `excel_data/views/auth.py` - Login credit enforcement
- `excel_data/management/commands/check_credits.py` - Status checking
- `excel_data/management/commands/process_daily_credits.py` - Manual processing
- `dashboard/settings.py` - Middleware configuration

---

## ✅ Summary

**The credit system now works seamlessly with Railway's server sleep feature:**

✅ Credits deduct automatically on first request after day change  
✅ No external cron services needed  
✅ No additional costs  
✅ Thread-safe and cached for performance  
✅ Comprehensive logging and monitoring  
✅ Easy to test and debug  

**Result:** Your HRMS can use Railway's free/cheaper sleep-enabled plans while maintaining accurate daily credit deduction!
