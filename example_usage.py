from db_manager import DBManager
import logging
import time
from datetime import datetime
from sqlalchemy import text

def setup_example_authors():
    """Add example authors to the database"""
    db = DBManager()
    
    example_authors = [
        {
            "name": "Ciprian Dobre",
            "source": "dblp",
            "url": "https://dblp.uni-trier.de/pers/hd/d/Dobre:Ciprian"
        },
        {
            "name": "Ciprian Dobre 2",
            "source": "google",
            "url": "https://scholar.google.ro/citations?user=_44USrIAAAAJ"
        }
    ]
    
    with db.get_connection() as conn:
        for author in example_authors:
            try:
                insert_query = text("""
                    INSERT INTO authors (author_name, source, url)
                    VALUES (:name, :source, :url)
                    ON CONFLICT (author_name, source) DO NOTHING
                """)
                conn.execute(insert_query, author)
                print(f"Added or verified author: {author['name']}")
            except Exception as e:
                print(f"Error adding author {author['name']}: {e}")

def monitor_crawling_progress():
    """Monitor the crawling progress"""
    db = DBManager()
    
    while True:
        with db.get_connection() as conn:
            # Get author statistics
            query = text("""
                SELECT 
                    a.author_name,
                    a.source,
                    a.last_crawl,
                    COUNT(p.publication_id) as publication_count
                FROM authors a
                LEFT JOIN publications p ON a.author_id = p.author_id
                GROUP BY a.author_id, a.author_name, a.source, a.last_crawl
            """)
            
            author_stats = conn.execute(query).fetchall()
            
            print("\nCrawling Progress Report:")
            print("=" * 80)
            print(f"Time: {datetime.now()}")
            print("-" * 80)
            print(f"{'Author':<30} {'Source':<10} {'Last Crawl':<20} {'Publications':<10}")
            print("-" * 80)
            
            for stat in author_stats:
                last_crawl = stat.last_crawl if stat.last_crawl else 'Never'
                print(f"{stat.author_name:<30} {stat.source:<10} "
                      f"{str(last_crawl):<20} {stat.publication_count:<10}")
            
            print("=" * 80)
            time.sleep(10)  # Update every 10 seconds

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    print("Setting up example authors...")
    setup_example_authors()
    
    print("\nStarting crawling monitor...")
    print("(Press Ctrl+C to stop)")
    try:
        monitor_crawling_progress()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")