"""
Django management command to test S3 log upload functionality.

Usage:
    python manage.py test_s3_logs
    python manage.py test_s3_logs --force-upload  # Force immediate upload
    python manage.py test_s3_logs --check-config  # Only check configuration
"""
import os
import time
import logging
from django.core.management.base import BaseCommand
from django.conf import settings

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class Command(BaseCommand):
    help = 'Test S3 log upload functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-upload',
            action='store_true',
            help='Force immediate upload to S3 (bypasses interval)',
        )
        parser.add_argument(
            '--check-config',
            action='store_true',
            help='Only check configuration without testing upload',
        )
        parser.add_argument(
            '--wait',
            type=int,
            default=10,
            help='Wait time in seconds before checking S3 (default: 10)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== S3 Log Upload Test ===\n'))
        
        # Check boto3 availability
        if not BOTO3_AVAILABLE:
            self.stdout.write(self.style.ERROR('❌ boto3 is not installed'))
            self.stdout.write('   Run: pip install boto3')
            return
        
        self.stdout.write(self.style.SUCCESS('✓ boto3 is installed'))
        
        # Check configuration
        config_ok = self.check_configuration()
        
        if not config_ok:
            self.stdout.write(self.style.WARNING('\n⚠ S3 logging is not configured'))
            self.stdout.write('   Add required environment variables to .env file')
            return
        
        if options['check_config']:
            self.stdout.write(self.style.SUCCESS('\n✓ Configuration is valid'))
            return
        
        # Test logging
        self.stdout.write('\n--- Testing Logging ---')
        test_logger = logging.getLogger('test_s3_logs')
        test_logger.setLevel(logging.INFO)
        
        # Get file handler if available
        file_handler = None
        for handler in logging.root.handlers:
            if hasattr(handler, 's3_enabled') and handler.s3_enabled:
                file_handler = handler
                break
        
        if not file_handler:
            # Try to find it in loggers
            for logger_name in ['django', 'orders', 'FILTERED_CONSOLE']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers:
                    if hasattr(handler, 's3_enabled') and handler.s3_enabled:
                        file_handler = handler
                        break
                if file_handler:
                    break
        
        if file_handler and hasattr(file_handler, 's3_enabled') and file_handler.s3_enabled:
            self.stdout.write(f'✓ Found S3 handler: {file_handler.__class__.__name__}')
            self.stdout.write(f'  Portal Number: {file_handler.portal_number}')
            self.stdout.write(f'  S3 Bucket: {file_handler.s3_bucket}')
            self.stdout.write(f'  S3 Region: {file_handler.s3_region}')
            self.stdout.write(f'  Upload Interval: {file_handler.upload_interval}s')
            
            # Write test log entries
            self.stdout.write('\n--- Writing Test Log Entries ---')
            test_messages = [
                f'[TEST-S3] Test log entry {i+1} at {time.strftime("%Y-%m-%d %H:%M:%S")}'
                for i in range(5)
            ]
            
            for msg in test_messages:
                test_logger.info(msg)
                self.stdout.write(f'  ✓ {msg}')
            
            # Force upload if requested
            if options['force_upload']:
                self.stdout.write('\n--- Forcing Immediate Upload ---')
                try:
                    file_handler._upload_to_s3()
                    self.stdout.write(self.style.SUCCESS('✓ Upload triggered'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'✗ Upload error: {e}'))
            else:
                wait_time = options['wait']
                self.stdout.write(f'\n--- Waiting {wait_time}s for automatic upload ---')
                self.stdout.write('  (Upload happens in background thread)')
                time.sleep(wait_time)
            
            # Check S3
            self.stdout.write('\n--- Checking S3 ---')
            self.check_s3_upload(file_handler)
        else:
            self.stdout.write(self.style.WARNING('⚠ S3 handler not found in logging configuration'))
            self.stdout.write('   Make sure S3 credentials are set in .env file')
    
    def check_configuration(self):
        """Check if S3 configuration is valid."""
        self.stdout.write('\n--- Configuration Check ---')
        
        required_vars = {
            'PORTAL_NUMBER': getattr(settings, 'PORTAL_NUMBER', None),
            'AWS_ACCESS_KEY_ID': getattr(settings, 'AWS_ACCESS_KEY_ID', None),
            'AWS_SECRET_ACCESS_KEY': getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
            'AWS_S3_BUCKET': getattr(settings, 'AWS_S3_BUCKET', None),
        }
        
        optional_vars = {
            'AWS_S3_REGION': getattr(settings, 'AWS_S3_REGION', 'us-east-1'),
            'S3_LOG_UPLOAD_INTERVAL': getattr(settings, 'S3_LOG_UPLOAD_INTERVAL', 300),
            'ENABLE_S3_LOGS': getattr(settings, 'ENABLE_S3_LOGS', True),
        }
        
        all_ok = True
        
        for var_name, var_value in required_vars.items():
            if var_value:
                # Mask sensitive values
                if 'SECRET' in var_name or 'KEY' in var_name:
                    display_value = f"{var_value[:8]}..." if len(var_value) > 8 else "***"
                else:
                    display_value = var_value
                self.stdout.write(f'  ✓ {var_name}: {display_value}')
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ {var_name}: Not set'))
                all_ok = False
        
        self.stdout.write('\n  Optional variables:')
        for var_name, var_value in optional_vars.items():
            self.stdout.write(f'    {var_name}: {var_value}')
        
        s3_enabled = getattr(settings, 'S3_LOGGING_ENABLED', False)
        if s3_enabled:
            self.stdout.write(self.style.SUCCESS(f'\n  ✓ S3_LOGGING_ENABLED: {s3_enabled}'))
        else:
            self.stdout.write(self.style.WARNING(f'\n  ⚠ S3_LOGGING_ENABLED: {s3_enabled}'))
        
        return all_ok and s3_enabled
    
    def check_s3_upload(self, handler):
        """Check if logs were uploaded to S3."""
        try:
            s3_client = handler._get_s3_client()
            if not s3_client:
                self.stdout.write(self.style.ERROR('✗ S3 client not available'))
                return
            
            bucket = handler.s3_bucket
            portal_number = handler.portal_number
            
            # Check for log files
            log_files = ['django.log', 'console.log', 'errors.log']
            found_files = []
            
            for log_file in log_files:
                s3_key = f"{portal_number}/logs/{log_file}"
                try:
                    s3_client.head_object(Bucket=bucket, Key=s3_key)
                    found_files.append(log_file)
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Found: {s3_key}'))
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code == '404':
                        self.stdout.write(self.style.WARNING(f'  ⚠ Not found: {s3_key} (may not be uploaded yet)'))
                    else:
                        self.stdout.write(self.style.ERROR(f'  ✗ Error checking {s3_key}: {e}'))
            
            if found_files:
                self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully found {len(found_files)} log file(s) in S3'))
                self.stdout.write(f'  Bucket: s3://{bucket}')
                self.stdout.write(f'  Path: {portal_number}/logs/')
            else:
                self.stdout.write(self.style.WARNING('\n⚠ No log files found in S3 yet'))
                self.stdout.write('  This is normal if:')
                self.stdout.write('    - Upload interval has not elapsed yet')
                self.stdout.write('    - No logs have been written yet')
                self.stdout.write('  Try: python manage.py test_s3_logs --force-upload')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error checking S3: {e}'))
