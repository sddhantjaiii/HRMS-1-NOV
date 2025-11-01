"""
Credit Deduction Scheduler
Runs credit deduction checks:
1. On application startup
2. Every hour
3. At midnight (00:00:00 IST) daily
"""

import threading
import time
import logging
from datetime import datetime, time as datetime_time
from django.utils import timezone
import pytz
from django.db import connection

logger = logging.getLogger(__name__)


class CreditScheduler:
    """
    Background scheduler for credit deduction.
    Runs in a separate daemon thread.
    """
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.last_hourly_check = None
        self.last_midnight_check = None
        
    def process_all_credits(self):
        """Process credits for all active tenants"""
        try:
            # Import here to avoid circular imports
            from excel_data.models import Tenant
            
            # Close old connections
            connection.close()
            
            tenants = Tenant.objects.filter(is_active=True, credits__gt=0)
            total = tenants.count()
            processed = 0
            deducted = 0
            
            logger.info(f"🔄 Credit scheduler: Processing {total} active tenants")
            
            for tenant in tenants:
                try:
                    was_deducted = tenant.deduct_daily_credit()
                    processed += 1
                    if was_deducted:
                        deducted += 1
                except Exception as e:
                    logger.error(f"Error processing tenant {tenant.id}: {str(e)}")
            
            if deducted > 0:
                logger.info(f"✅ Credit scheduler: Processed {processed}/{total} tenants, {deducted} credits deducted")
            else:
                logger.debug(f"Credit scheduler: Processed {processed}/{total} tenants, no deductions needed")
                
            return processed, deducted
            
        except Exception as e:
            logger.error(f"Error in credit scheduler: {str(e)}", exc_info=True)
            return 0, 0
    
    def should_run_midnight_check(self):
        """Check if we should run the midnight check"""
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = timezone.now().astimezone(ist)
        current_time = now_ist.time()
        current_date = now_ist.date()
        
        # Check if it's between 00:00:00 and 00:05:00 (5 minute window)
        midnight_start = datetime_time(0, 0, 0)
        midnight_end = datetime_time(0, 5, 0)
        
        is_midnight_window = midnight_start <= current_time <= midnight_end
        
        # Check if we haven't run today
        already_ran_today = (
            self.last_midnight_check is not None and 
            self.last_midnight_check >= current_date
        )
        
        return is_midnight_window and not already_ran_today
    
    def should_run_hourly_check(self):
        """Check if we should run the hourly check"""
        if self.last_hourly_check is None:
            return True
        
        # Run if more than 1 hour has passed
        now = timezone.now()
        time_diff = (now - self.last_hourly_check).total_seconds()
        return time_diff >= 3600  # 1 hour = 3600 seconds
    
    def run(self):
        """Main scheduler loop"""
        ist = pytz.timezone('Asia/Kolkata')
        logger.info("🚀 Credit scheduler started")
        
        # Run immediately on startup
        logger.info("🌟 Running credit check on startup...")
        self.process_all_credits()
        self.last_hourly_check = timezone.now()
        self.last_midnight_check = timezone.now().astimezone(ist).date()
        
        while self.running:
            try:
                # Check if we should run midnight check
                if self.should_run_midnight_check():
                    ist_now = timezone.now().astimezone(ist)
                    logger.info(f"🌙 Running midnight credit check at {ist_now.strftime('%H:%M:%S IST')}")
                    processed, deducted = self.process_all_credits()
                    self.last_midnight_check = ist_now.date()
                    
                    if deducted > 0:
                        logger.info(f"🌙 Midnight check complete: {deducted} credits deducted")
                
                # Check if we should run hourly check
                elif self.should_run_hourly_check():
                    logger.info("⏰ Running hourly credit check...")
                    processed, deducted = self.process_all_credits()
                    self.last_hourly_check = timezone.now()
                    
                    if deducted > 0:
                        logger.info(f"⏰ Hourly check complete: {deducted} credits deducted")
                
                # Sleep for 1 minute before next check
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in credit scheduler loop: {str(e)}", exc_info=True)
                time.sleep(60)  # Wait a minute before retrying
    
    def start(self):
        """Start the scheduler in a daemon thread"""
        if self.running:
            logger.warning("Credit scheduler is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        logger.info("Credit scheduler thread started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Credit scheduler stopped")


# Global scheduler instance
_scheduler = None


def get_scheduler():
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CreditScheduler()
    return _scheduler


def start_credit_scheduler():
    """Start the credit scheduler (call this on app startup)"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_credit_scheduler():
    """Stop the credit scheduler"""
    scheduler = get_scheduler()
    scheduler.stop()
