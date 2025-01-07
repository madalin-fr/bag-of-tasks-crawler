import logging
import time
import threading
import signal
from typing import List
from coordinator import Coordinator
from crawler import Crawler
from config import NUM_CRAWLERS

def setup_logging() -> None:
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('crawler.log'),
            logging.StreamHandler()
        ]
    )

# Global flag for shutdown
shutdown_flag = threading.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logging.info("Shutdown signal received, stopping gracefully...")
    shutdown_flag.set()

def run_coordinator(shutdown_flag: threading.Event) -> None:
    """Run coordinator process"""
    coordinator = Coordinator()
    try:
        while not shutdown_flag.is_set():
            coordinator.run_once()  # Modified to run one iteration
            time.sleep(1)
    except Exception as e:
        logging.error(f"Coordinator error: {e}")
    finally:
        coordinator.cleanup()
        logging.info("Coordinator stopped")

def run_crawler(shutdown_flag: threading.Event) -> None:
    """Run crawler process"""
    crawler = Crawler()
    try:
        while not shutdown_flag.is_set():
            crawler.run_once()  # Modified to run one iteration
            time.sleep(1)
    except Exception as e:
        logging.error(f"Crawler error: {e}")
    finally:
        crawler.cleanup()
        logging.info("Crawler stopped")

def main() -> None:
    """Main entry point"""
    setup_logging()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start coordinator
    coord_thread = threading.Thread(target=run_coordinator, args=(shutdown_flag,))
    coord_thread.daemon = True
    coord_thread.start()
    
    # Start crawler nodes
    crawler_threads: List[threading.Thread] = []
    for _ in range(NUM_CRAWLERS):
        crawler_thread = threading.Thread(target=run_crawler, args=(shutdown_flag,))
        crawler_thread.daemon = True
        crawler_threads.append(crawler_thread)
        crawler_thread.start()
        time.sleep(1)  # Stagger crawler starts
    
    try:
        # Keep main thread alive and handle shutdown
        while not shutdown_flag.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received...")
    finally:
        # Set shutdown flag and wait for threads
        shutdown_flag.set()
        logging.info("Waiting for threads to stop...")
        
        # Wait for threads with timeout
        coord_thread.join(timeout=5)
        for thread in crawler_threads:
            thread.join(timeout=5)
            
        logging.info("Shutdown complete")

if __name__ == "__main__":
    main()