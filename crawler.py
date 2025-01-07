# crawler.py
import requests
import logging
import json
import os
import time
import random
import re
from bs4 import BeautifulSoup
import pika
from datetime import datetime
from typing import List, Dict, Optional, Any 
from proxy_manager import ProxyManager
from config import (
    RABBITMQ_HOST, QUEUE_NAME, DEFAULT_TIMEOUT, USER_AGENTS,
    GOOGLE_SCHOLAR_SELECTORS, DBLP_SELECTORS,
    ERROR_RATE_LIMIT, ERROR_IP_BLOCKED, ERROR_PARSING,
    HEARTBEAT_INTERVAL
)

class Crawler:
    """Worker node for crawling publication data"""
    def __init__(self):
        self.node_id = os.urandom(8).hex()
        self.proxy_manager = ProxyManager()
        self.session = requests.Session()
        self.setup_rabbitmq()

    def setup_rabbitmq(self) -> None:
        """Initialize RabbitMQ connection"""
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        self.channel.basic_qos(prefetch_count=1)

    def crawl(self, url: str, source: str) -> List[Dict[str, Any]]:
        """Perform crawl with proxy rotation"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            proxies = self.proxy_manager.get_proxy()
            if not proxies:
                raise Exception("No proxies available")

            try:
                response = self.session.get(
                    url,
                    proxies=proxies,
                    timeout=DEFAULT_TIMEOUT,
                    headers=self.get_headers()
                )
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                if source == 'google':
                    return self.parse_google_scholar(soup)
                elif source == 'dblp':
                    return self.parse_dblp(soup)
                else:
                    raise ValueError(f"Unknown source: {source}")

            except requests.exceptions.RequestException as e:
                retry_count += 1
                proxy_str = proxies.get('http', '')
                self.handle_request_error(e, proxy_str)
                time.sleep(retry_count * 2)
            except ValueError as e:
                raise e
            except Exception as e:
                logging.error(f"Error during crawling: {e}")
                retry_count += 1
                time.sleep(retry_count * 2)
            finally:
                if proxies and 'http' in proxies:
                    self.proxy_manager.release_proxy(proxies['http'])
    
    def get_headers(self):
        """Generate random headers for requests"""
        return {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

    def parse_google_scholar(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse Google Scholar page"""
        publications = []
        for article in soup.select(GOOGLE_SCHOLAR_SELECTORS['article']):
            try:
                title_elem = article.select_one(GOOGLE_SCHOLAR_SELECTORS['title'])
                
                # Find the first element that matches the year pattern
                year_elem = None
                for element in article.descendants:
                    if isinstance(element, str):
                        match = re.search(GOOGLE_SCHOLAR_SELECTORS['year'], element)
                        if match:
                            year_elem = match
                            break
                
                if title_elem:
                    publications.append({
                        'title': title_elem.text.strip(),
                        'year': int(year_elem.group(0)) if year_elem else None,
                        'source': 'google'
                    })
            except Exception as e:
                logging.error(f"Error parsing Google Scholar article: {e}")
                raise Exception(f"{ERROR_PARSING}: {e}")
        return publications

    def parse_dblp(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse DBLP page"""
        publications = []
        for article in soup.select(DBLP_SELECTORS['article']):
            try:
                title_elem = article.select_one(DBLP_SELECTORS['title'])

                # Find the first element that matches the year pattern
                year_elem = None
                for element in article.descendants:
                    if isinstance(element, str):
                        match = re.search(DBLP_SELECTORS['year'], element)
                        if match:
                            year_elem = match
                            break
                
                if title_elem:
                    publications.append({
                        'title': title_elem.text.strip(),
                        'year': int(year_elem.group(0)) if year_elem else None,
                        'source': 'dblp'
                    })
            except Exception as e:
                logging.error(f"Error parsing DBLP article: {e}")
                raise Exception(f"{ERROR_PARSING}: {e}")
        return publications

    def handle_request_error(self, error: Exception, proxy: str) -> None:
        """Handle request errors and proxy blocking"""
        if "429" in str(error):
            self.proxy_manager.mark_blocked(proxy)
            raise Exception(ERROR_RATE_LIMIT)
        elif "403" in str(error):
            self.proxy_manager.mark_blocked(proxy)
            raise Exception(ERROR_IP_BLOCKED)
        else:
            raise Exception(f"Request failed: {str(error)}")

    def send_heartbeat(self) -> None:
        """Send heartbeat to coordinator"""
        heartbeat = {
            "heartbeat": True,
            "node_id": self.node_id,
            "timestamp": datetime.now().isoformat()
        }
        
        self.channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=json.dumps(heartbeat),
            properties=pika.BasicProperties(delivery_mode=2)
        )

    def process_task(self, task: Dict[str, Any]) -> None:
        """Process a single crawling task"""
        try:
            logging.info(f"Processing task for {task.get('author')} from {task.get('source')}")
            publications = self.crawl(task["url"], task["source"])
            
            result = {
                "status": "success",
                "task_data": task,
                "publications": publications,
                "node_id": self.node_id
            }
            logging.info(f"Successfully crawled {len(publications)} publications for {task.get('author')}")
            
        except Exception as e:
            result = {
                "status": "error",
                "task_data": task,
                "error": str(e),
                "node_id": self.node_id
            }
            logging.error(f"Task error for {task.get('author')}: {e}")
        
        # Ensure we're publishing the result
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=QUEUE_NAME,
                body=json.dumps(result),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            logging.info(f"Published result for {task.get('author')}")
        except Exception as e:
            logging.error(f"Error publishing result: {e}")

    def run(self) -> None:
        """Main crawler loop"""
        def callback(ch, method, properties, body):
            task = json.loads(body.decode())
            if not task.get("heartbeat"):
                self.process_task(task)
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_consume(
            queue=QUEUE_NAME,
            on_message_callback=callback
        )
        
        logging.info(f"Crawler node {self.node_id} started")
        
        # Send heartbeats periodically
        while True:
            try:
                self.send_heartbeat()
                self.connection.process_data_events(time_limit=HEARTBEAT_INTERVAL)
            except Exception as e:
                logging.error(f"Error sending heartbeat or processing events: {e}")
                # Attempt to reconnect or handle the error as needed
                time.sleep(5)  # Wait for a bit before retrying
                self.setup_rabbitmq()

    def run_once(self) -> None:
        """Run one iteration of the crawler loop"""
        try:
            self.send_heartbeat()
            self.connection.process_data_events(time_limit=1)
        except Exception as e:
            logging.error(f"Error in crawler loop: {e}")

    def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logging.info(f"Crawler {self.node_id}: RabbitMQ connection closed")
        except Exception as e:
            logging.error(f"Error during crawler cleanup: {e}")
