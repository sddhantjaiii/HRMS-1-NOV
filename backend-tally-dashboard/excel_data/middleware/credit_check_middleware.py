"""
Credit Check Middleware
Automatically checks and deducts missed credits when the server wakes up or on any request.
This ensures credits are deducted even when the server sleeps (e.g., Railway sleep mode).
"""

import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache

logger = logging.getLogger(__name__)


class AutoCreditDeductionMiddleware(MiddlewareMixin):
    """
    Middleware to automatically check and deduct credits for tenants on user requests.
    
    This provides immediate credit checks when users access the system,
    working alongside the background scheduler for comprehensive coverage.
    
    How it works:
    1. On each authenticated request, checks if the tenant needs credit deduction
    2. Attempts to deduct credit (will only succeed if not already deducted today)
    3. Uses brief cache (5 min) to prevent excessive checks during request bursts
    """
    
    CACHE_PREFIX = 'credit_checked_'
    CACHE_TIMEOUT = 300  # 5 minutes - just to prevent excessive DB queries
    
    def process_request(self, request):
        """
        Process incoming request and check credits if needed.
        """
        try:
            # Only check credits for authenticated users
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return None
            
            # Get tenant from user
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                return None
            
            tenant = request.user.tenant
            
            # Check cache to prevent excessive DB hits in quick succession
            cache_key = f"{self.CACHE_PREFIX}{tenant.id}"
            recently_checked = cache.get(cache_key)
            
            if recently_checked:
                # Already checked in last 5 minutes, skip
                return None
            
            # Attempt to deduct credit (will check last_credit_deducted internally)
            was_deducted = tenant.deduct_daily_credit()
            
            if was_deducted:
                logger.info(
                    f"✅ [Middleware] Auto-deducted credit for tenant '{tenant.name}' (ID: {tenant.id}). "
                    f"Remaining credits: {tenant.credits}"
                )
            
            # Mark as checked in cache
            cache.set(cache_key, True, self.CACHE_TIMEOUT)
            
        except Exception as e:
            # Log error but don't block the request
            logger.error(f"Error in AutoCreditDeductionMiddleware: {str(e)}", exc_info=True)
        
        return None


class CreditEnforcementMiddleware(MiddlewareMixin):
    """
    Additional middleware to enforce credit checks on critical operations.
    
    This provides an extra layer of protection by checking credits before
    allowing access to tenant-specific resources.
    """
    
    # URLs that don't require credit checks
    EXEMPT_PATHS = [
        '/admin/',
        '/api/auth/login/',
        '/api/auth/register/',
        '/api/auth/logout/',
        '/api/auth/password/',
        '/api/health/',
        '/static/',
        '/media/',
    ]
    
    def process_request(self, request):
        """
        Check if the current path requires credit enforcement.
        """
        try:
            # Check if path is exempt
            path = request.path
            if any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS):
                return None
            
            # Only enforce for authenticated users
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return None
            
            # Check if user has tenant
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                return None
            
            tenant = request.user.tenant
            
            # Log warning if credits are low
            if tenant.credits <= 5 and tenant.credits > 0:
                logger.warning(
                    f"Low credits warning for tenant '{tenant.name}' (ID: {tenant.id}). "
                    f"Only {tenant.credits} credits remaining."
                )
            
            # Note: We don't block requests here because the tenant.is_active check
            # is already enforced at login (in auth.py). This middleware just logs warnings.
            
        except Exception as e:
            logger.error(f"Error in CreditEnforcementMiddleware: {str(e)}", exc_info=True)
        
        return None
