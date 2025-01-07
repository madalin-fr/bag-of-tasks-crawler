# main.py
import logging
import time
from coordinator import Coordinator
from crawler import Crawler
import threading
from config import DATABASE_URL

def run_coordinator():
    coordinator = Coordinator()
    coordinator.run()

def run_crawler():
    crawler = Crawler()
    crawler.run()

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Start coordinator
    coord_thread = threading.Thread(target=run_coordinator)
    coord_thread.start()
    
    # Start multiple crawlers
    crawler_threads = []
    num_crawlers = 3  # Number of crawler instances
    
    for _ in range(num_crawlers):
        crawler_thread = threading.Thread(target=run_crawler)
        crawler_threads.append(crawler_thread)
        crawler_thread.start()
        time.sleep(1)  # Stagger crawler starts
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")

if __name__ == "__main__":
    main()