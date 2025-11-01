from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from ..utils.utils import get_current_tenant
import logging
import pytz

logger = logging.getLogger(__name__)


class Tenant(models.Model):
    """
    Tenant model for multi-tenant support
    """
    name = models.CharField(max_length=255, help_text="Organization/Company name")
    subdomain = models.CharField(max_length=100, unique=True, blank=True, null=True, help_text="Unique subdomain identifier (optional)")
    custom_domain = models.CharField(max_length=255, blank=True, null=True, help_text="Custom domain if any")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tenant settings
    max_employees = models.IntegerField(default=1000, help_text="Maximum number of employees allowed")
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Credit and Billing Information
    credits = models.PositiveIntegerField(default=0, help_text="Available credits for this tenant")
    is_active = models.BooleanField(default=True, help_text="Whether the tenant is active (has credits > 0 and is not manually deactivated)")
    last_credit_deducted = models.DateField(null=True, blank=True, help_text="Date when the last credit was deducted (IST)")
    
    # Billing information (for future use)
    plan = models.CharField(max_length=50, default='free', choices=[
        ('free', 'Free'),
        ('premium', 'Premium'),
        ('enterprise', 'Enterprise')
    ])
    
    # Auto-calculate payroll setting
    auto_calculate_payroll = models.BooleanField(
        default=False,
        help_text="Automatically calculate payroll on 1st of each month for previous month"
    )
    
    class Meta:
        app_label = 'excel_data'
        verbose_name = _('tenant')
        verbose_name_plural = _('tenants')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.subdomain}) - Credits: {self.credits}"
        
    def get_ist_time(self):
        """Get current time in Indian Standard Time"""
        ist = pytz.timezone('Asia/Kolkata')
        return timezone.now().astimezone(ist)
        
    def deduct_daily_credit(self):
        """Deduct credits for all missed days since last deduction"""
        from excel_data.models.auth import CustomUser
        from datetime import timedelta
        
        now_ist = self.get_ist_time()
        today_ist = now_ist.date()
        
        # Check if we've already deducted credit today
        if self.last_credit_deducted and self.last_credit_deducted >= today_ist:
            # Already deducted today
            logger.debug(f"Tenant {self.name} (ID: {self.id}) - Credit already deducted today ({self.last_credit_deducted})")
            return False
        
        if self.credits > 0:
            # Calculate number of days to deduct
            if self.last_credit_deducted is None:
                # First time deduction - only deduct 1 credit for today
                days_to_deduct = 1
            else:
                # Calculate days between last deduction and today
                days_diff = (today_ist - self.last_credit_deducted).days
                days_to_deduct = days_diff  # Deduct for all missed days
            
            logger.info(
                f"Tenant {self.name} (ID: {self.id}) - Attempting credit deduction. "
                f"Last deducted: {self.last_credit_deducted}, Today: {today_ist}, "
                f"Days to deduct: {days_to_deduct}"
            )
            
            with transaction.atomic():
                # Use select_for_update to prevent race conditions
                tenant = Tenant.objects.select_for_update().get(pk=self.pk)
                
                # Double-check after acquiring lock
                if tenant.last_credit_deducted and tenant.last_credit_deducted >= today_ist:
                    logger.debug(f"Tenant {tenant.name} (ID: {tenant.id}) - Race condition avoided, already deducted")
                    return False
                
                if tenant.credits > 0 and days_to_deduct > 0:
                    # Deduct credits (but don't go below 0)
                    credits_to_deduct = min(days_to_deduct, tenant.credits)
                    tenant.credits -= credits_to_deduct
                    tenant.last_credit_deducted = today_ist
                    
                    # Deactivate tenant if no credits left
                    if tenant.credits == 0:
                        tenant.is_active = False
                        # Deactivate all users for this tenant
                        CustomUser.objects.filter(tenant=tenant).update(is_active=False)
                        logger.warning(
                            f"🔴 Tenant {tenant.name} (ID: {tenant.id}) deactivated due to zero credits. "
                            f"Deducted {credits_to_deduct} credits for {days_to_deduct} days"
                        )
                    
                    tenant.save(update_fields=['credits', 'is_active', 'last_credit_deducted'])
                    logger.info(
                        f"✅ Deducted {credits_to_deduct} credit(s) from tenant {tenant.name} (ID: {tenant.id}) "
                        f"for {days_to_deduct} day(s). Remaining: {tenant.credits}"
                    )
                    return True
        else:
            logger.debug(f"Tenant {self.name} (ID: {self.id}) - No credits available to deduct")
        
        return False
    
    def add_credits(self, amount):
        """Add credits to tenant and reactivate if needed"""
        if amount <= 0:
            return False
            
        with transaction.atomic():
            # Use select_for_update to prevent race conditions
            tenant = Tenant.objects.select_for_update().get(pk=self.pk)
            was_inactive = not tenant.is_active
            
            tenant.credits += amount
            
            # Reactivate tenant if credits were added to a deactivated account
            if was_inactive and tenant.credits > 0:
                tenant.is_active = True
                from excel_data.models.auth import CustomUser
                # Reactivate all users for this tenant
                CustomUser.objects.filter(tenant=tenant).update(is_active=True)
                logger.info(f"Tenant {tenant.name} reactivated with {amount} credits")
            
            tenant.save(update_fields=['credits', 'is_active'])
            logger.info(f"Added {amount} credits to tenant {tenant.name}. Total: {tenant.credits}")
            return True


class TenantAwareManager(models.Manager):
    """
    Manager that automatically filters by current tenant
    """
    def get_queryset(self):
        tenant = get_current_tenant()
        if tenant:
            return super().get_queryset().filter(tenant=tenant)
        return super().get_queryset()


class TenantAwareModel(models.Model):
    """
    Abstract base model that automatically adds tenant to all models
    """
    tenant = models.ForeignKey('excel_data.Tenant', on_delete=models.CASCADE, related_name='%(class)s_set')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = TenantAwareManager()
    all_objects = models.Manager()  # Access all objects regardless of tenant
    
    class Meta:
        abstract = True
        app_label = 'excel_data'
    
    def save(self, *args, **kwargs):
        if not self.tenant_id:
            self.tenant = get_current_tenant()
        super().save(*args, **kwargs)