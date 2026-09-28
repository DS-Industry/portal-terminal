"""
S3 Log Handler for Django

This handler extends RotatingFileHandler to also upload logs to S3 periodically.
It maintains local file logging as backup and uploads to S3 in the background.
"""
import os
import sys
import logging
import threading
import time
import atexit
from logging.handlers import RotatingFileHandler
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


class S3RotatingFileHandler(RotatingFileHandler):
    """
    A logging handler that writes to a local file (with rotation) and
    periodically uploads the current log file to S3.
    
    The handler maintains all the functionality of RotatingFileHandler
    for local logging, and adds S3 upload capability in the background.
    """
    
    def __init__(
        self,
        filename,
        mode='a',
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
        portal_number: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_region: str = 'us-east-1',
        s3_endpoint_url: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        upload_interval: int = 65,
        errors=None
    ):
        """
        Initialize the handler.
        
        Args:
            filename: Log file path (same as RotatingFileHandler)
            mode: File mode (same as RotatingFileHandler)
            maxBytes: Max file size before rotation (same as RotatingFileHandler)
            backupCount: Number of backup files (same as RotatingFileHandler)
            encoding: File encoding (same as RotatingFileHandler)
            delay: Delay file creation (same as RotatingFileHandler)
            portal_number: Portal/terminal identifier for S3 path
            s3_bucket: S3 bucket name
            s3_region: AWS region (default: us-east-1)
            s3_endpoint_url: Custom S3 endpoint URL (optional, for S3-compatible services)
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            upload_interval: Upload interval in seconds (default: 65 = 1 minute 5 seconds)
            errors: Error handling (same as RotatingFileHandler)
        """
        # Initialize parent RotatingFileHandler for local file logging
        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
            errors=errors
        )
        
        # S3 configuration
        self.portal_number = portal_number
        self.s3_bucket = s3_bucket
        self.s3_region = s3_region
        self.s3_endpoint_url = s3_endpoint_url
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.upload_interval = upload_interval
        
        # S3 client (initialized lazily)
        self._s3_client = None
        self._upload_thread = None
        self._stop_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()
        
        # Check if S3 upload should be enabled
        self.s3_enabled = self._check_s3_config()
        
        if self.s3_enabled:
            # Register shutdown handler
            atexit.register(self._shutdown_handler)
            self._start_upload_thread()
    
    def _check_s3_config(self) -> bool:
        """Check if S3 upload is properly configured."""
        if not BOTO3_AVAILABLE:
            return False
        
        if not all([self.portal_number, self.s3_bucket, 
                   self.aws_access_key_id, self.aws_secret_access_key]):
            return False
        
        return True
    
    def _get_s3_client(self):
        """Get or create S3 client (lazy initialization)."""
        if self._s3_client is None and self.s3_enabled:
            try:
                client_kwargs = {
                    'region_name': self.s3_region,
                    'aws_access_key_id': self.aws_access_key_id,
                    'aws_secret_access_key': self.aws_secret_access_key
                }
                
                # Add custom endpoint URL if provided (for S3-compatible services)
                if self.s3_endpoint_url:
                    client_kwargs['endpoint_url'] = self.s3_endpoint_url
                
                self._s3_client = boto3.client('s3', **client_kwargs)
            except Exception as e:
                # Log error but don't break logging
                self._log_s3_error(f"Failed to create S3 client: {e}")
                return None
        
        return self._s3_client
    
    def _get_s3_key(self, filename: str) -> str:
        """Generate S3 key path: {portal_number}/logs/{filename}"""
        # Extract just the filename from the full path
        base_filename = os.path.basename(filename)
        return f"{self.portal_number}/logs/{base_filename}"
    
    def _upload_to_s3(self):
        """Upload current log file to S3."""
        # Don't upload during shutdown
        if not self.s3_enabled or self._shutdown_event.is_set():
            return
        
        # Check if interpreter is shutting down
        if sys.is_finalizing():
            return
        
        s3_client = self._get_s3_client()
        if s3_client is None:
            return
        
        # Get the current log file path
        log_file = self.baseFilename
        
        # Check if file exists and has content
        if not os.path.exists(log_file) or os.path.getsize(log_file) == 0:
            return
        
        try:
            s3_key = self._get_s3_key(log_file)
            
            # Upload file to S3
            with open(log_file, 'rb') as f:
                s3_client.upload_fileobj(
                    f,
                    self.s3_bucket,
                    s3_key,
                    ExtraArgs={'ContentType': 'text/plain'}
                )
            
        except FileNotFoundError:
            # File doesn't exist yet, skip this upload
            pass
        except (ClientError, BotoCoreError) as e:
            # Don't log during shutdown to avoid recursion
            if not self._shutdown_event.is_set():
                self._log_s3_error(f"S3 upload error: {e}")
        except RuntimeError as e:
            # Handle "cannot schedule new futures after interpreter shutdown"
            if "shutdown" in str(e).lower() or "interpreter" in str(e).lower():
                # Silently skip during shutdown
                pass
            elif not self._shutdown_event.is_set():
                self._log_s3_error(f"Runtime error during S3 upload: {e}")
        except Exception as e:
            # Don't log during shutdown to avoid recursion
            if not self._shutdown_event.is_set():
                self._log_s3_error(f"Unexpected error during S3 upload: {e}")
    
    def _log_s3_error(self, message: str):
        """Log S3 errors to the root logger (to avoid recursion)."""
        # Use root logger to avoid circular logging
        root_logger = logging.getLogger()
        root_logger.error(f"[S3-LOG-HANDLER] {message}")
    
    def _upload_worker(self):
        """Background thread worker that periodically uploads logs to S3."""
        while not self._stop_event.wait(self.upload_interval):
            # Check if we're shutting down
            if self._shutdown_event.is_set() or sys.is_finalizing():
                break
            
            try:
                with self._lock:
                    # Double-check shutdown before uploading
                    if not self._shutdown_event.is_set() and not sys.is_finalizing():
                        self._upload_to_s3()
            except RuntimeError as e:
                # Handle shutdown-related errors silently
                if "shutdown" in str(e).lower() or "interpreter" in str(e).lower():
                    break
                elif not self._shutdown_event.is_set():
                    self._log_s3_error(f"Runtime error in upload worker: {e}")
            except Exception as e:
                if not self._shutdown_event.is_set():
                    self._log_s3_error(f"Error in upload worker: {e}")
    
    def _start_upload_thread(self):
        """Start the background upload thread."""
        if self._upload_thread is None or not self._upload_thread.is_alive():
            self._stop_event.clear()
            self._upload_thread = threading.Thread(
                target=self._upload_worker,
                daemon=True,
                name="S3LogUploadThread"
            )
            self._upload_thread.start()
    
    def emit(self, record):
        """
        Emit a log record.
        Override to ensure S3 upload thread is running.
        """
        # Call parent emit to write to local file
        super().emit(record)
        
        # Ensure upload thread is running (in case it died)
        if self.s3_enabled and (self._upload_thread is None or not self._upload_thread.is_alive()):
            try:
                self._start_upload_thread()
            except Exception:
                # If thread start fails, continue with local logging only
                pass
    
    def _shutdown_handler(self):
        """Handler called during interpreter shutdown."""
        self._shutdown_event.set()
        self._stop_event.set()
    
    def close(self):
        """Close the handler and perform final S3 upload."""
        # Mark as shutting down
        self._shutdown_event.set()
        
        # Stop the upload thread
        if self._upload_thread is not None:
            self._stop_event.set()
            if self._upload_thread.is_alive():
                self._upload_thread.join(timeout=2)  # Shorter timeout during shutdown
        
        # Perform final upload before closing (only if not shutting down)
        if self.s3_enabled and not sys.is_finalizing():
            try:
                with self._lock:
                    # Check one more time before uploading
                    if not sys.is_finalizing():
                        self._upload_to_s3()
            except (RuntimeError, Exception):
                # Silently ignore errors during shutdown
                pass
        
        # Close parent handler
        super().close()
