"""
Management command to check credit system status and test deduction
Usage: python manage.py check_credits
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from excel_data.models import Tenant
from django.core.cache import cache
import pytz


class Command(BaseCommand):
    help = 'Check credit system status and show which tenants need credit deduction'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Check specific tenant by ID',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear credit check cache before checking',
        )
        parser.add_argument(
            '--test-deduct',
            action='store_true',
            help='Test credit deduction (will actually deduct if due)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CREDIT SYSTEM STATUS CHECK'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')

        # Clear cache if requested
        if options['clear_cache']:
            self.stdout.write(self.style.WARNING('🧹 Clearing credit check cache...'))
            cache_keys = cache.keys('credit_checked_*')
            if cache_keys:
                cache.delete_many(cache_keys)
                self.stdout.write(self.style.SUCCESS(f'   Cleared {len(cache_keys)} cache entries'))
            else:
                self.stdout.write(self.style.SUCCESS('   No cache entries to clear'))
            self.stdout.write('')

        # Get tenants to check
        if options['tenant_id']:
            tenants = Tenant.objects.filter(id=options['tenant_id'])
            if not tenants.exists():
                self.stdout.write(self.style.ERROR(f'❌ Tenant with ID {options["tenant_id"]} not found'))
                return
        else:
            tenants = Tenant.objects.all().order_by('-is_active', '-credits', 'name')

        # Show current time info
        now_utc = timezone.now()
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = now_utc.astimezone(ist)
        
        self.stdout.write(self.style.SUCCESS(f'🕐 Current Time:'))
        self.stdout.write(f'   UTC: {now_utc.strftime("%Y-%m-%d %H:%M:%S %Z")}')
        self.stdout.write(f'   IST: {now_ist.strftime("%Y-%m-%d %H:%M:%S %Z")}')
        self.stdout.write('')

        # Display tenant information
        self.stdout.write(self.style.SUCCESS(f'📊 Total Tenants: {tenants.count()}'))
        self.stdout.write('')

        for tenant in tenants:
            # Check if deduction is due based on last_credit_deducted
            should_deduct = (
                tenant.last_credit_deducted is None or 
                tenant.last_credit_deducted < now_ist.date()
            )
            
            # Status icon
            if not tenant.is_active:
                status_icon = '🔴'
                status = 'INACTIVE'
            elif tenant.credits == 0:
                status_icon = '⚫'
                status = 'NO CREDITS'
            elif tenant.credits <= 5:
                status_icon = '🟡'
                status = 'LOW CREDITS'
            else:
                status_icon = '🟢'
                status = 'ACTIVE'
            
            self.stdout.write(self.style.WARNING(f'{status_icon} Tenant: {tenant.name} (ID: {tenant.id})'))
            self.stdout.write(f'   Status: {status}')
            self.stdout.write(f'   Credits: {tenant.credits}')
            self.stdout.write(f'   Active: {tenant.is_active}')
            
            # Show last credit deduction date
            if tenant.last_credit_deducted:
                self.stdout.write(f'   Last Credit Deducted: {tenant.last_credit_deducted.strftime("%Y-%m-%d")}')
            else:
                self.stdout.write(f'   Last Credit Deducted: Never')
            
            # Check cache status
            cache_key = f'credit_checked_{tenant.id}'
            cached = cache.get(cache_key)
            if cached:
                self.stdout.write(f'   Cache Status: ✓ Checked recently (within last hour)')
            else:
                self.stdout.write(f'   Cache Status: ✗ Not in cache')
            
            # Show if deduction is due
            if should_deduct and tenant.credits > 0:
                self.stdout.write(self.style.WARNING(f'   ⚠️  DEDUCTION DUE: Credit will be deducted on next request'))
            elif should_deduct and tenant.credits == 0:
                self.stdout.write(f'   ℹ️  No credits to deduct')
            else:
                self.stdout.write(f'   ✓ Up to date (no deduction needed today)')
            
            # Test deduction if requested
            if options['test_deduct'] and should_deduct and tenant.credits > 0:
                self.stdout.write(self.style.WARNING(f'   🧪 Testing credit deduction...'))
                was_deducted = tenant.deduct_daily_credit()
                if was_deducted:
                    # Refresh from DB
                    tenant.refresh_from_db()
                    self.stdout.write(self.style.SUCCESS(
                        f'   ✅ Successfully deducted 1 credit. Remaining: {tenant.credits}'
                    ))
                    if tenant.credits == 0:
                        self.stdout.write(self.style.ERROR(
                            f'   🔴 Tenant deactivated due to zero credits'
                        ))
                else:
                    self.stdout.write(f'   ℹ️  No deduction performed')
            
            self.stdout.write('')

        # Summary
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        active_tenants = tenants.filter(is_active=True, credits__gt=0).count()
        inactive_tenants = tenants.filter(is_active=False).count()
        low_credit_tenants = tenants.filter(is_active=True, credits__lte=5, credits__gt=0).count()
        zero_credit_tenants = tenants.filter(credits=0).count()
        
        self.stdout.write(f'🟢 Active Tenants: {active_tenants}')
        self.stdout.write(f'🟡 Low Credit Tenants (≤5): {low_credit_tenants}')
        self.stdout.write(f'⚫ Zero Credit Tenants: {zero_credit_tenants}')
        self.stdout.write(f'🔴 Inactive Tenants: {inactive_tenants}')
        self.stdout.write('')
        
        if not options['test_deduct']:
            self.stdout.write(self.style.SUCCESS('💡 Tip: Use --test-deduct to actually deduct credits for tenants that are due'))
            self.stdout.write(self.style.SUCCESS('💡 Tip: Use --clear-cache to force re-check on next request'))
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
