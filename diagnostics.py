#diagnostics.py
import psycopg2
import logging
from datetime import datetime
import pika
import json
from bs4 import BeautifulSoup
import requests
import random
from config import USER_AGENTS

def run_diagnostics():
    print("\n=== Running Publication Crawler Diagnostics ===\n")
    
    # 1. Check Database Connection and Authors
    try:
        conn = psycopg2.connect(
            dbname="publication_db",
            user="publication_user",
            password="project",
            host="localhost"
        )
        cur = conn.cursor()
        
        # Check authors table
        print("Checking authors table...")
        cur.execute("SELECT COUNT(*) FROM authors")
        author_count = cur.fetchone()[0]
        print(f"Found {author_count} authors in database")
        
        if author_count == 0:
            print("\nAdding example authors...")
            cur.execute("""
                INSERT INTO authors (author_name, source, url)
                VALUES 
                ('Ciprian Dobre', 'dblp', 'https://dblp.uni-trier.de/pers/hd/d/Dobre:Ciprian'),
                ('Ciprian Dobre', 'google', 'https://scholar.google.ro/citations?user=_44USrIAAAAJ')
                ON CONFLICT (author_name, source) DO NOTHING
                RETURNING author_id;
            """)
            conn.commit()
            print("Example authors added successfully")
        
        # Check publications table
        print("\nChecking publications table...")
        cur.execute("SELECT COUNT(*) FROM publications")
        pub_count = cur.fetchone()[0]
        print(f"Found {pub_count} publications in database")
        
        # Check last_crawl status
        print("\nChecking author crawl status...")
        cur.execute("""
            SELECT author_name, source, last_crawl 
            FROM authors 
            ORDER BY last_crawl DESC NULLS FIRST
        """)
        crawl_status = cur.fetchall()
        for author in crawl_status:
            print(f"Author: {author[0]}, Source: {author[1]}, Last Crawl: {author[2]}")
            
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

    # 2. Check RabbitMQ Connection and Queue
    print("\nChecking RabbitMQ connection...")
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        
        # Check queue status
        queue = channel.queue_declare(queue='crawl_queue', durable=True)
        print(f"Messages in queue: {queue.method.message_count}")
        
        connection.close()
        print("RabbitMQ connection successful")
    except Exception as e:
        print(f"RabbitMQ Error: {e}")

    print("\n=== Diagnostic Complete ===")


def debug_crawl_detailed():
    """Enhanced debugging for crawler issues"""
    print("\n=== Enhanced Crawler Debugging Session ===\n")
    
    # 1. Check queue content
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        channel = connection.channel()
        
        # Sample multiple messages
        messages = []
        for _ in range(3):  # Check 3 messages
            method_frame, _, body = channel.basic_get('crawl_queue', auto_ack=False)
            if method_frame:
                messages.append(json.loads(body))
                # Put message back
                channel.basic_nack(method_frame.delivery_tag, requeue=True)
        
        if messages:
            print("Queue Content Analysis:")
            for idx, msg in enumerate(messages, 1):
                print(f"\nMessage {idx}:")
                print(json.dumps(msg, indent=2))
                
                # Test crawl if it's a crawl task
                if not msg.get('heartbeat') and msg.get('url'):
                    print(f"\nTesting crawl for URL: {msg['url']}")
                    
                    headers = {
                        'User-Agent': random.choice(USER_AGENTS),
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5'
                    }
                    
                    try:
                        response = requests.get(msg['url'], headers=headers, timeout=10)
                        print(f"Response status code: {response.status_code}")
                        
                        if response.status_code == 200:
                            soup = BeautifulSoup(response.text, 'lxml')
                            
                            # Check for blocking indicators
                            page_text = soup.get_text().lower()
                            if any(term in page_text for term in ['robot', 'captcha', 'automated', 'blocked']):
                                print("WARNING: Possible crawler detection in response")
                            
                            # Try to find publication elements
                            if msg.get('source') == 'google':
                                articles = soup.select('.gs_r.gs_or.gs_scl')
                                print(f"Found {len(articles)} potential Google Scholar publications")
                                if articles:
                                    print("\nSample publication titles:")
                                    for article in articles[:2]:
                                        title = article.select_one('.gs_rt')
                                        if title:
                                            print(f"- {title.text.strip()}")
                            elif msg.get('source') == 'dblp':
                                articles = soup.select('.entry.article')
                                print(f"Found {len(articles)} potential DBLP publications")
                                if articles:
                                    print("\nSample publication titles:")
                                    for article in articles[:2]:
                                        title = article.select_one('.title')
                                        if title:
                                            print(f"- {title.text.strip()}")
                                            
                    except Exception as e:
                        print(f"Error during test crawl: {e}")
        else:
            print("No crawl task messages found in queue (only heartbeats?)")
            
        connection.close()
        
    except Exception as e:
        print(f"Error accessing RabbitMQ: {e}")
    
    print("\n=== Enhanced Debug Session Complete ===")



if __name__ == "__main__":
    run_diagnostics()
    debug_crawl_detailed()