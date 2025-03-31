"""
config.py - Configuration settings for the Syllabus Calendar Generator
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import tempfile

# Application settings
APP_NAME = "Syllabus Calendar Generator"
APP_VERSION = "0.1.0"
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
TESTING = os.environ.get('TESTING', 'False').lower() in ('true', '1', 't')

# API settings
API_HOST = os.environ.get('API_HOST', '0.0.0.0')
API_PORT = int(os.environ.get('API_PORT', 5000))

# File handling
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', tempfile.mkdtemp())
ALLOWED_EXTENSIONS = {'pdf'}

# Calendar settings
GOOGLE_CREDENTIALS_PATH = os.environ.get('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
GOOGLE_TOKEN_PATH = os.environ.get('GOOGLE_TOKEN_PATH', 'token.json')

# Email settings (for notifications - future feature)
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'noreply@example.com')

# Logging configuration
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def setup_logging():
    """Configure logging for the application."""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # Create handlers
    console_handler = logging.StreamHandler()
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
    
    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Set library logging levels
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('googleapiclient').setLevel(logging.WARNING)
    logging.getLogger('google_auth_oauthlib').setLevel(logging.WARNING)
    
    return root_logger