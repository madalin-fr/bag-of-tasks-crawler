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
        try:
            self.node_id = os.urandom(8).hex()
            self.proxy_manager = ProxyManager()
            self.session = requests.Session()
            self.setup_rabbitmq()
        except Exception as e:
            logging.error(f"Failed to initialize crawler: {e}")
            raise

          
    def setup_rabbitmq(self) -> None:
        """Initialize RabbitMQ connection"""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
            self.channel.basic_qos(prefetch_count=1)
            logging.info(f"Crawler {self.node_id}: Connected to RabbitMQ")
            logging.info(f"Crawler {self.node_id}: Prefetch count set to 1") 
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Crawler {self.node_id}: Error connecting to RabbitMQ: {e}")
            raise
        except Exception as e:
            logging.error(f"Crawler {self.node_id}: An unexpected error occurred during RabbitMQ setup: {e}")
            raise

    

    def crawl(self, url: str, source: str) -> List[Dict[str, Any]]:
        """Perform crawl with proxy rotation"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            proxies = self.proxy_manager.get_proxy()
            if not proxies:
                logging.error("No proxies available") # Added logging
                raise Exception("No proxies available")

            try:
                logging.info(f"Crawler {self.node_id}: Fetching URL: {url} with proxy: {proxies.get('http')}") # Added logging
                response = self.session.get(
                    url,
                    proxies=proxies,
                    timeout=DEFAULT_TIMEOUT,
                    headers=self.get_headers()
                )
                response.raise_for_status()
                logging.info(f"Crawler {self.node_id}: Fetched content for {source}: {len(response.text)} bytes, Status Code: {response.status_code}") # Added logging
                
                soup = BeautifulSoup(response.text, 'lxml')
                if source == 'google':
                    publications =  self.parse_google_scholar(soup)
                elif source == 'dblp':
                    publications = self.parse_dblp(soup)
                else:
                    raise ValueError(f"Unknown source: {source}")
                logging.info(f"Parsed publications: {publications}")
                return publications

            except requests.exceptions.RequestException as e:
                retry_count += 1
                proxy_str = proxies.get('http', '')
                self.handle_request_error(e, proxy_str)
                time.sleep(retry_count * 2)
            except ValueError as e:
                logging.error(f"ValueError during crawling: {e}")
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
        try:
            return {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
        except Exception as e:
            logging.error(f"Error generating headers: {e}")
            return {}

    def parse_google_scholar(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse Google Scholar page"""
        publications = []
        try:
            articles = soup.select(GOOGLE_SCHOLAR_SELECTORS['article'])
            logging.info(f"Crawler {self.node_id}: Found {len(articles)} articles on Google Scholar page")
            for i, article in enumerate(articles):
                try:
                    title_elem = article.select_one(GOOGLE_SCHOLAR_SELECTORS['title'])
                    if title_elem:
                        title = title_elem.text.strip()
                    else:
                        logging.warning(f"Crawler {self.node_id}: Title not found for article {i+1}")
                        title = None

                    year_elem = article.select_one(GOOGLE_SCHOLAR_SELECTORS['year'])
                    if year_elem:
                        year_text = year_elem.text.strip()
                        # Handle cases where the year might be empty or non-numeric
                        if year_text.isdigit():
                            year = int(year_text)
                        else:
                            logging.warning(f"Crawler {self.node_id}: Non-numeric year found for article {i+1}: '{year_text}'")
                            year = None
                    else:
                        logging.warning(f"Crawler {self.node_id}: Year not found for article {i+1}")
                        year = None

                    if title and year:
                        publications.append({
                            'title': title,
                            'year': year,
                            'source': 'google'
                        })
                        logging.info(f"Crawler {self.node_id}: Found title: {title}, year: {year}")
                    else:
                        logging.warning(f"Crawler {self.node_id}: Skipping article {i+1}: title or year missing")

                except Exception as e:
                    logging.error(f"Crawler {self.node_id}: Error parsing article {i+1}: {e}")
        except Exception as e:
            logging.error(f"Crawler {self.node_id}: Error parsing Google Scholar page: {e}")
            logging.error(f"Crawler {self.node_id}: Snippet of problematic HTML: {soup.prettify()[:1000]}") # Log more HTML
        return publications

    def parse_dblp(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse DBLP page"""
        publications = []
        try:
            articles = soup.select(DBLP_SELECTORS['article'])
            logging.info(f"Found articles: {len(articles)}")
            for article in articles:
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
                    else:
                        logging.warning("Skipping article: title not found")
                except Exception as e:
                    logging.error(f"Error parsing DBLP article: {e}")
        except Exception as e:
            logging.error(f"Error parsing DBLP page: {e}")
        return publications

    def handle_request_error(self, error: Exception, proxy: str) -> None:
        """Handle request errors and proxy blocking"""
        if "429" in str(error):
            self.proxy_manager.mark_blocked(proxy)
            logging.error(f"Rate limit exceeded with proxy {proxy}")
            raise Exception(ERROR_RATE_LIMIT)
        elif "403" in str(error):
            self.proxy_manager.mark_blocked(proxy)
            logging.error(f"IP {proxy} blocked")
            raise Exception(ERROR_IP_BLOCKED)
        else:
            logging.error(f"Request failed with proxy {proxy}: {str(error)}")
            raise Exception(f"Request failed: {str(error)}")

    def send_heartbeat(self) -> None:
        """Send heartbeat to coordinator"""
        try:
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
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Crawler {self.node_id}: Error sending heartbeat: {e}")
        except Exception as e:
            logging.error(f"Crawler {self.node_id}: An unexpected error occurred while sending heartbeat: {e}")

    def process_task(self, task: Dict[str, Any]) -> None:
        """Process a single crawling task"""
        logging.info(f"Crawler {self.node_id}: Received task: {task}")

        # Check for heartbeat first
        if task.get("heartbeat"):
            logging.info(f"Crawler {self.node_id}: Heartbeat received, skipping processing")
            return

        # Explicitly check for malformed tasks
        if not isinstance(task, dict) or "url" not in task or "author" not in task or "source" not in task:
            logging.error(f"Crawler {self.node_id}: Received malformed task: {task}")
            return  # Skip processing and do not create an error result

        result = None  # Initialize result

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
            logging.error(f"Task error for {task.get('author', 'Unknown Author')}: {e}")
            logging.error(f"Task details: {task}")  # Log the task details for debugging
            # Create error result only if the task is well-formed
            result = {
                "status": "error",
                "task_data": task,
                "error": str(e),
                "node_id": self.node_id
            }

        # Ensure we're publishing the result only if it was created
        if result:
            try:
                self.channel.basic_publish(
                    exchange='',
                    routing_key=QUEUE_NAME,
                    body=json.dumps(result),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                logging.info(f"Published result for {task.get('author')}")
            except pika.exceptions.AMQPConnectionError as e:
                logging.error(f"Crawler {self.node_id}: Error publishing result: {e}")
            except Exception as e:
                logging.error(f"Crawler {self.node_id}: An unexpected error occurred while publishing result: {e}")


    def run_once(self) -> None:
        """Run one iteration of the crawler loop"""
        try:
            self.send_heartbeat()
            # Process a message from the queue
            method_frame, header_frame, body = self.channel.basic_get(queue=QUEUE_NAME, auto_ack=False)
            if method_frame:
                logging.info(f"Crawler {self.node_id}: Received message: {body.decode()}")
                try:
                    task = json.loads(body)
                    logging.info(f"Crawler {self.node_id}: Received task: {task.get('author')}")
                    self.process_task(task)
                    self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                except json.JSONDecodeError as e:
                    logging.error(f"Error decoding JSON from queue: {e}")
                    self.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=False)
                except Exception as e:
                    logging.error(f"Error processing task: {e}")
                    self.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
            else:
                logging.info(f"Crawler {self.node_id}: No message received")

            self.connection.process_data_events(time_limit=1)
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f"Crawler {self.node_id}: Error in run_once: {e}")
            # Attempt to reconnect
            time.sleep(5)
            self.setup_rabbitmq()
        except Exception as e:
            logging.error(f"Crawler {self.node_id}: An unexpected error occurred in run_once: {e}")

    def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logging.info(f"Crawler {self.node_id}: RabbitMQ connection closed")
        except Exception as e:
            logging.error(f"Crawler {self.node_id}: Error during cleanup: {e}")