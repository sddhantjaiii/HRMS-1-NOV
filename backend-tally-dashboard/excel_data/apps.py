from django.apps import AppConfig
from django.conf import settings
import os


class ExcelDataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'excel_data'

    def ready(self):
        # Import signals
        import excel_data.signals  # noqa
        
        # Start credit scheduler (only in main process, not in reloader)
        # Check if we're in the main process (not the reloader process)
        if os.environ.get('RUN_MAIN') != 'true' and not settings.DEBUG:
            # Production mode - start scheduler
            from excel_data.credit_scheduler import start_credit_scheduler
            start_credit_scheduler()
        elif os.environ.get('RUN_MAIN') == 'true' and settings.DEBUG:
            # Development mode with reloader - start in reloaded process
            from excel_data.credit_scheduler import start_credit_scheduler
            start_credit_scheduler()
