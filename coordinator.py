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
            try:
                self.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=RABBITMQ_HOST)
                )
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=QUEUE_NAME, durable=True)
                logger.info("Connected to RabbitMQ")
            except pika.exceptions.AMQPConnectionError as e:
                logger.error(f"Error connecting to RabbitMQ: {e}")
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred during RabbitMQ setup: {e}")
                raise

    


    def check_node_health(self) -> None:
        """Remove inactive nodes"""
        try:
            current_time = datetime.now()
            inactive_nodes = [
                node_id for node_id, last_seen in self.active_nodes.items()
                if (current_time - last_seen).total_seconds() > HEARTBEAT_INTERVAL * 2
            ]
            for node_id in inactive_nodes:
                logging.warning(f"Node {node_id} inactive - removing")
                del self.active_nodes[node_id]
        except Exception as e:
            logger.error(f"Error during node health check: {e}")

    def process_result(self, data: Dict[str, Any]) -> None:
        """Process crawl results"""
        logging.info(f"Coordinator: Received result: {data}")
        try:
            if data is None:
                logging.warning("Received a None result, likely due to a malformed task. Acknowledging the message.")
                return  # Acknowledge and exit early
            
            if data.get("heartbeat"):
                node_id = data.get("node_id")
                if node_id:
                    self.active_nodes[node_id] = datetime.now()
                    logger.info(f"Heartbeat received from {node_id}")
                return

            status = data.get("status")
            task_data = data.get("task_data", {})

            # Handle malformed tasks
            if status == "success" and "url" not in task_data:
                logging.warning(f"Skipping processing of malformed task_data: {task_data}")
                return
            
            # Handle successful results
            if status == "success":
                # Correctly access author_id and publications
                author_id = task_data.get("author_id") 
                publications = data.get("publications", [])

                if author_id is not None:
                    logging.info(f"Coordinator: Processing successful result for author ID: {author_id}")
                    logging.info(f"Coordinator: Publications found: {publications}")
                    self.db.update_publications(author_id, publications)
                    logging.info(f"Successfully processed publications for {task_data.get('author')}")
                else:
                    logging.error("Error processing result: 'author_id' not found in task_data")

            elif status == "error":
                self.handle_error(task_data, data.get("error"))
                # Update last_crawl even on error to prevent continuous retries
                if task_data and "author_id" in task_data:
                    self.db.update_last_crawl(task_data["author_id"])

        except Exception as e:
            logging.error(f"Error processing result: {e}")

    def handle_error(self, task_data: Dict[str, Any], error_msg: str) -> None:
        """Handle task errors and retries"""
        try:
            # Check if it's a heartbeat/error message, or a malformed task
            if 'url' not in task_data:
                logging.warning(f"Skipping error handling for malformed task_data: {task_data}")
                return
            
            retry_count = task_data.get("retry_count", 0)
            if retry_count < MAX_RETRIES:
                task_data["retry_count"] = retry_count + 1
                task_data["status"] = "pending"
                self.publish_task(task_data)
                logging.info(f"Retrying task for {task_data['author']}, attempt {retry_count + 1}")
            else:
                logging.error(f"Task failed after {MAX_RETRIES} retries: {error_msg}")
        except Exception as e:
            logger.error(f"Error handling error: {e}")

    def publish_task(self, task: Dict[str, Any]) -> None:
        """Publish task to queue"""
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=QUEUE_NAME,
                body=json.dumps(task),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            logger.info(f"Task published: {task}")
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Error publishing task to RabbitMQ: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during task publishing: {e}")

    def generate_tasks(self) -> List[Dict[str, Any]]:
        """Generate new crawling tasks"""
        tasks = []
        try:
            # Only get authors that haven't been queued recently
            authors = self.db.get_authors_for_crawling()

            # Check queue length
            queue = self.channel.queue_declare(queue=QUEUE_NAME, durable=True, passive=True)
            queue_length = queue.method.message_count
            logging.info(f"Current queue length: {queue_length}")

            # Generate tasks only if the queue is not too long
            if queue_length < 500:  # Less restrictive

                
                for author in authors:
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

                    # Mark as queued only if tasks were generated
                    if tasks:
                        for author in authors:
                            self.db.update_last_crawl(author['author_id'])
            else:
                logging.warning(f"Queue too long ({queue_length} messages), skipping task generation")

            if not tasks:
                logging.warning("No tasks generated in this iteration.")

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
            try:
                method_frame, header_frame, body = self.channel.basic_get(
                    queue=QUEUE_NAME,
                    auto_ack=False
                )
                
                if method_frame:
                    try:
                        data = json.loads(body)
                        self.process_result(data)
                        self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                        logging.info(f"Coordinator: Acknowledged message: {method_frame.delivery_tag}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from queue: {e}")
                        self.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=False)
            except pika.exceptions.AMQPConnectionError as e:
                logger.error(f"Error accessing RabbitMQ queue: {e}")
                
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