# coordinator.py
import pika
import logging
import json
from datetime import datetime
from typing import Dict, List, Any
from db_manager import DBManager
from config import (
    RABBITMQ_HOST, QUEUE_NAME, MAX_RETRIES,
    BASE_RETRY_DELAY, MAX_RETRY_DELAY, HEARTBEAT_INTERVAL
)

logger = logging.getLogger('coordinator')

class Coordinator:
    """Manages task distribution and result processing"""
    def __init__(self):
        try:
            self.db = DBManager()
            self.active_nodes: Dict[str, datetime] = {}
            self.setup_rabbitmq()
        except Exception as e:
            logger.error(f"Failed to initialize Coordinator: {e}")
            raise

    def setup_rabbitmq(self) -> None:
        """Initialize RabbitMQ connection with retry logic"""
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
        logger.info("Connected to RabbitMQ")

    def check_node_health(self) -> None:
        """Remove inactive nodes"""
        current_time = datetime.now()
        inactive_nodes = [
            node_id for node_id, last_seen in self.active_nodes.items()
            if (current_time - last_seen).total_seconds() > HEARTBEAT_INTERVAL * 2
        ]
        for node_id in inactive_nodes:
            logging.warning(f"Node {node_id} inactive - removing")
            del self.active_nodes[node_id]

    def process_result(self, data: Dict[str, Any]) -> None:
        """Process crawl results"""
        try:
            if data.get("heartbeat"):
                node_id = data.get("node_id")
                if node_id:
                    self.active_nodes[node_id] = datetime.now()
                return

            status = data.get("status")
            task_data = data.get("task_data", {})
            
            if status == "success":
                self.db.update_publications(
                    task_data["author_id"],
                    data.get("publications", [])
                )
                logging.info(f"Successfully processed publications for {task_data.get('author')}")
            elif status == "error":
                self.handle_error(task_data, data.get("error"))
                # Update last_crawl even on error to prevent continuous retries
                self.db.update_last_crawl(task_data["author_id"])

        except Exception as e:
            logging.error(f"Error processing result: {e}")

    def handle_error(self, task_data: Dict[str, Any], error_msg: str) -> None:
        """Handle task errors and retries"""
        retry_count = task_data.get("retry_count", 0)
        if retry_count < MAX_RETRIES:
            task_data["retry_count"] = retry_count + 1
            task_data["status"] = "pending"
            self.publish_task(task_data)
            logging.info(f"Retrying task for {task_data['author']}, attempt {retry_count + 1}")
        else:
            logging.error(f"Task failed after {MAX_RETRIES} retries: {error_msg}")

    def publish_task(self, task: Dict[str, Any]) -> None:
        """Publish task to queue"""
        self.channel.basic_publish(
            exchange='',
            routing_key=QUEUE_NAME,
            body=json.dumps(task),
            properties=pika.BasicProperties(delivery_mode=2)
        )

    def generate_tasks(self) -> List[Dict[str, Any]]:
        """Generate new crawling tasks"""
        tasks = []
        try:
            # Only get authors that haven't been queued recently
            authors = self.db.get_authors_for_crawling()
            
            # Check if tasks are already in queue
            method_frame = self.channel.basic_get(queue=QUEUE_NAME, auto_ack=False)
            existing_tasks = set()
            if method_frame:
                # Put the message back
                self.channel.basic_nack(method_frame[0].delivery_tag, requeue=True)
                # Extract author_id from the message
                try:
                    msg = json.loads(method_frame[2])
                    if isinstance(msg, dict):
                        existing_tasks.add(msg.get('author_id'))
                except:
                    pass

            for author in authors:
                # Skip if already queued
                if author['author_id'] not in existing_tasks:
                    task = {
                        "author_id": author["author_id"],
                        "url": author["url"],
                        "author": author["author_name"],
                        "source": author["source"],
                        "status": "pending",
                        "retry_count": 0,
                        "created_at": datetime.now().isoformat()
                    }
                    tasks.append(task)
                    logging.info(f"Generated task for {author['author_name']}")
                    
                    # Mark as queued by updating last_crawl
                    self.db.update_last_crawl(author['author_id'])
            
        except Exception as e:
            logging.error(f"Error generating tasks: {e}")
        return tasks


    
    def run_once(self) -> None:
        """Run one iteration of the coordinator loop"""
        try:
            self.check_node_health()
            
            # Generate and publish new tasks
            for task in self.generate_tasks():
                self.publish_task(task)
            
            # Process results
            method_frame, _, body = self.channel.basic_get(
                queue=QUEUE_NAME,
                auto_ack=True
            )
            
            if method_frame:
                self.process_result(json.loads(body))
                
        except Exception as e:
            logging.error(f"Error in coordinator loop: {e}")

    
    def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                logging.info("Coordinator: RabbitMQ connection closed")
        except Exception as e:
            logging.error(f"Error during coordinator cleanup: {e}")