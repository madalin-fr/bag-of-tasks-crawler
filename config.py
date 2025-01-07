#config.py
from datetime import timedelta
import logging
import time
import sys

# RabbitMQ Configuration
RABBITMQ_HOST = 'localhost'
QUEUE_NAME = 'crawl_queue'

# Database Configuration
DB_USER = 'publication_user'
DB_PASS = 'project'
DB_HOST = 'localhost'
DB_NAME = 'publication_db'
DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}'

# Crawler Configuration
MAX_RETRIES = 3
BASE_RETRY_DELAY = 5  # seconds
NUM_CRAWLERS = 3  # Number of crawler instances
MAX_RETRY_DELAY = 3600  # 1 hour
HEARTBEAT_INTERVAL = 60  # seconds

# IP Management
IP_BLOCK_DURATION = 3600  # 1 hour
MIN_REQUEST_INTERVAL = 2  # seconds between requests from same IP

# Crawling Intervals
GOOGLE_SCHOLAR_INTERVAL = timedelta(days=7)  # Re-crawl every 7 days
DBLP_INTERVAL = timedelta(days=30)  # Re-crawl every 30 days

# Page Selectors
GOOGLE_SCHOLAR_SELECTORS = {
    'article': '.gs_r.gs_or.gs_scl',  # Main article container
    'title': '.gs_rt a',              # Article title
    'year': r'\b(19|20)\d{2}\b'      # Year pattern
}

DBLP_SELECTORS = {
    'article': '.entry.article',      # Main article container
    'title': '.title',                # Article title
    'year': r'\b(19|20)\d{2}\b'      # Year pattern
}

# Logging Configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_THROTTLE_INTERVAL = 5

# Error Messages
ERROR_IP_BLOCKED = "IP blocked by service"
ERROR_RATE_LIMIT = "Rate limit exceeded"
ERROR_PARSING = "Error parsing page content"

# HTTP Configuration
DEFAULT_TIMEOUT = 10
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
]

class ThrottledConsoleHandler(logging.StreamHandler):
    """Custom handler that throttles identical log messages"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_log = {}
        self.throttle_interval = LOG_THROTTLE_INTERVAL

    def emit(self, record):
        current_time = time.time()
        # Create a unique key for each type of message
        msg_key = f"{record.levelno}:{record.getMessage()}"
        
        # Only emit if enough time has passed since last similar message
        if msg_key not in self.last_log or \
           (current_time - self.last_log[msg_key]) >= self.throttle_interval:
            self.last_log[msg_key] = current_time
            super().emit(record)

def setup_logging():
    """Configure logging with throttling for console output"""
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    
    # Clear any existing handlers
    root_logger.handlers = []
    
    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    
    # File handler - no throttling, keeps all logs
    file_handler = logging.FileHandler('crawler.log')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler - with throttling
    console_handler = ThrottledConsoleHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)