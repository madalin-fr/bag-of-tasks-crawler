#utils.py
import json
import logging
import pika
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_database_connection():
    """
    Returns the database connection
    """
    engine = create_engine('postgresql://publication_user:project@localhost/publication_db') # Replace with your actual credentials
    return engine

def normalize_task(task):
    """
    Normalize task structure to ensure consistent format.
    
    Args:
        task (dict): Original task dictionary
    
    Returns:
        dict: Normalized task with consistent structure
    """
    # If task is already in correct format, return as-is
    if isinstance(task, dict) and "status" in task and "task_data" in task:
        return task
    
    # Normalize the task
    normalized_task = {
        "status": "pending",
        "task_data": task if isinstance(task, dict) else {},
        "retry_count": task.get("retry_count", 0) if isinstance(task, dict) else 0
    }
    
    return normalized_task


def publish_task(queue_name, task, connection, channel):
    """
    Publish a task to the specified queue with a consistent structure.
   
    Args:
        queue_name (str): Name of the RabbitMQ queue
        task (dict): Task details to be published
        connection (pika.BlockingConnection): RabbitMQ connection
        channel (pika.channel.Channel): RabbitMQ channel
    """
    try:
        # Normalize the task structure
        structured_task = normalize_task(task)
        
        # Convert the task to JSON
        message = json.dumps(structured_task)
        
        # Publish the message to the queue
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            )
        )
        logging.info(f"Published normalized task: {structured_task}")
    except Exception as e:
        logging.error(f"Error publishing task: {e}")
        logging.error(traceback.format_exc())


def retry_task(task_data, retry_count, max_retries, queue_name, base_delay=5):
    """
    Retries a task by publishing to the task queue, using an exponential backoff strategy.
    """
    if retry_count >= max_retries:
        logging.error(f"Task failed after max retries: {task_data}")
        return

    delay = base_delay * (2 ** retry_count)
    logging.info(f"Retrying task in {delay} seconds: {task_data}")
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue=queue_name, durable=True)
    task_data["retry_count"] = retry_count
    channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(task_data).encode())
    connection.close()