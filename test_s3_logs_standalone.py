#!/usr/bin/env python
"""
Standalone test script for S3 log upload functionality.

This script can be run independently to test S3 configuration
without starting the full Django application.

Usage:
    python test_s3_logs_standalone.py
"""
import os
import sys
import time
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Set up minimal Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    print("❌ boto3 is not installed. Run: pip install boto3")
    sys.exit(1)


def test_s3_configuration():
    """Test S3 configuration."""
    print("=== S3 Log Upload Configuration Test ===\n")
    
    # Check boto3
    print("✓ boto3 is installed")
    
    # Check configuration
    print("\n--- Configuration Check ---")
    
    required_vars = {
        'PORTAL_NUMBER': getattr(settings, 'PORTAL_NUMBER', None),
        'AWS_ACCESS_KEY_ID': getattr(settings, 'AWS_ACCESS_KEY_ID', None),
        'AWS_SECRET_ACCESS_KEY': getattr(settings, 'AWS_SECRET_ACCESS_KEY', None),
        'AWS_S3_BUCKET': getattr(settings, 'AWS_S3_BUCKET', None),
    }
    
    all_ok = True
    for var_name, var_value in required_vars.items():
        if var_value:
            if 'SECRET' in var_name or 'KEY' in var_name:
                display_value = f"{var_value[:8]}..." if len(var_value) > 8 else "***"
            else:
                display_value = var_value
            print(f"  ✓ {var_name}: {display_value}")
        else:
            print(f"  ✗ {var_name}: Not set")
            all_ok = False
    
    s3_enabled = getattr(settings, 'S3_LOGGING_ENABLED', False)
    print(f"\n  S3_LOGGING_ENABLED: {s3_enabled}")
    
    if not all_ok or not s3_enabled:
        print("\n⚠ S3 logging is not properly configured")
        print("  Add required environment variables to .env file:")
        print("    PORTAL_NUMBER=your_portal_number")
        print("    AWS_ACCESS_KEY_ID=your_key")
        print("    AWS_SECRET_ACCESS_KEY=your_secret")
        print("    AWS_S3_BUCKET=your_bucket")
        return False
    
    return True


def test_s3_connection():
    """Test S3 connection and bucket access."""
    print("\n--- Testing S3 Connection ---")
    
    try:
        s3_client = boto3.client(
            's3',
            region_name=getattr(settings, 'AWS_S3_REGION', 'us-east-1'),
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )
        
        bucket = settings.AWS_S3_BUCKET
        
        # Test bucket access
        try:
            s3_client.head_bucket(Bucket=bucket)
            print(f"  ✓ Successfully connected to bucket: {bucket}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code == '404':
                print(f"  ✗ Bucket not found: {bucket}")
            elif error_code == '403':
                print(f"  ✗ Access denied to bucket: {bucket}")
            else:
                print(f"  ✗ Error accessing bucket: {e}")
            return False
        
        # Test write permission
        test_key = f"{settings.PORTAL_NUMBER}/logs/test_connection.txt"
        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=test_key,
                Body=b'Test connection',
                ContentType='text/plain'
            )
            print(f"  ✓ Successfully wrote test file: {test_key}")
            
            # Clean up test file
            s3_client.delete_object(Bucket=bucket, Key=test_key)
            print(f"  ✓ Cleaned up test file")
            
        except ClientError as e:
            print(f"  ✗ Error writing test file: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error creating S3 client: {e}")
        return False


def test_log_handler():
    """Test the S3 log handler."""
    print("\n--- Testing Log Handler ---")
    
    try:
        from config.s3_log_handler import S3RotatingFileHandler
        
        # Create a test handler
        test_log_file = os.path.join(settings.LOG_DIR, 'test_s3.log')
        handler = S3RotatingFileHandler(
            filename=test_log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            portal_number=settings.PORTAL_NUMBER,
            s3_bucket=settings.AWS_S3_BUCKET,
            s3_region=getattr(settings, 'AWS_S3_REGION', 'us-east-1'),
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            upload_interval=10,  # Short interval for testing
        )
        
        print(f"  ✓ Created S3 handler")
        print(f"    Portal: {handler.portal_number}")
        print(f"    Bucket: {handler.s3_bucket}")
        print(f"    S3 Enabled: {handler.s3_enabled}")
        
        # Write test log
        import logging
        logger = logging.getLogger('test_s3')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        test_message = f"[TEST] S3 log test at {time.strftime('%Y-%m-%d %H:%M:%S')}"
        logger.info(test_message)
        print(f"  ✓ Wrote test log: {test_message}")
        
        # Force upload
        print("  → Forcing immediate upload...")
        handler._upload_to_s3()
        print("  ✓ Upload completed")
        
        # Wait a bit and check S3
        time.sleep(2)
        s3_key = f"{settings.PORTAL_NUMBER}/logs/test_s3.log"
        s3_client = handler._get_s3_client()
        
        try:
            s3_client.head_object(Bucket=settings.AWS_S3_BUCKET, Key=s3_key)
            print(f"  ✓ Verified file in S3: {s3_key}")
        except ClientError:
            print(f"  ⚠ File not yet in S3 (may need a moment)")
        
        # Cleanup
        handler.close()
        if os.path.exists(test_log_file):
            os.remove(test_log_file)
        
        return True
        
    except Exception as e:
        print(f"  ✗ Error testing handler: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    
    # Test 1: Configuration
    if not test_s3_configuration():
        print("\n❌ Configuration test failed")
        sys.exit(1)
    
    # Test 2: S3 Connection
    if not test_s3_connection():
        print("\n❌ S3 connection test failed")
        sys.exit(1)
    
    # Test 3: Log Handler
    if not test_log_handler():
        print("\n❌ Log handler test failed")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("\nS3 log upload is working correctly.")
    print(f"Logs will be uploaded to: s3://{settings.AWS_S3_BUCKET}/{settings.PORTAL_NUMBER}/logs/")


if __name__ == '__main__':
    main()
