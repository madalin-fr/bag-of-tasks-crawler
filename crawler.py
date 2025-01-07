# crawler.py
import requests
import logging
import json
import os
from bs4 import BeautifulSoup
import pika
from datetime import datetime
from typing import List, Dict, Optional
from proxy_manager import ProxyManager
from config import (
    RABBITMQ_HOST, QUEUE_NAME, DEFAULT_TIMEOUT,
    GOOGLE_SCHOLAR_SELECTORS, DBLP_SELECTORS,
    ERROR_RATE_LIMIT, ERROR_IP_BLOCKED
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
                    proxies=proxies,  # This will be {'http': 'http://ip:port', 'https': 'http://ip:port'}
                    timeout=DEFAULT_TIMEOUT,
                    headers=self.get_headers()
                )
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                if source == 'google':
                    return self.parse_google_scholar(soup)
                return self.parse_dblp(soup)

            except requests.exceptions.RequestException as e:
                retry_count += 1
                proxy_str = proxies.get('http', '')  # Get the proxy string for marking blocked
                self.handle_request_error(e, proxy_str)
                time.sleep(retry_count * 2)  # Exponential backoff
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
                year_elem = article.select_one(GOOGLE_SCHOLAR_SELECTORS['year'])
                
                if title_elem:
                    publications.append({
                        'title': title_elem.text.strip(),
                        'year': int(year_elem.text) if year_elem else None,
                        'source': 'google'
                    })
            except Exception as e:
                logging.error(f"Error parsing Google Scholar article: {e}")
        return publications

    def parse_dblp(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse DBLP page"""
        publications = []
        for article in soup.select(DBLP_SELECTORS['article']):
            try:
                title_elem = article.select_one(DBLP_SELECTORS['title'])
                year_elem = article.select_one(DBLP_SELECTORS['year'])
                
                if title_elem:
                    publications.append({
                        'title': title_elem.text.strip(),
                        'year': int(year_elem.text) if year_elem else None,
                        'source': 'dblp'
                    })
            except Exception as e:
                logging.error(f"Error parsing DBLP article: {e}")
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
            publications = self.crawl(task["url"], task["source"])
            
            result = {
                "status": "success",
                "task_data": task,
                "publications": publications
            }
            
        except Exception as e:
            result = {
                "status": "error",
                "task_data": task,
                "error": str(e)
            }
            logging.error(f"Task error: {e}")
        
        self.channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=json.dumps(result),
            properties=pika.BasicProperties(delivery_mode=2)
        )

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
        self.channel.start_consuming()