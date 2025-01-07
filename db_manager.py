# db_manager.py
from sqlalchemy import create_engine, text
from datetime import datetime
import logging

class DBManager:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        
    def get_authors_for_crawling(self):
        """Get authors that need to be crawled"""
        query = text("""
            SELECT author_id, author_name, source, url, last_crawl
            FROM authors 
            WHERE last_crawl IS NULL
            OR (source = 'google' AND last_crawl < NOW() - INTERVAL '7 days')
            OR (source = 'dblp' AND last_crawl < NOW() - INTERVAL '30 days')
        """)
        
        with self.engine.connect() as conn:
            results = conn.execute(query)
            return [dict(row) for row in results]
            
    def update_author_crawl_time(self, author_id):
        """Update last crawl time for an author"""
        query = text("""
            UPDATE authors 
            SET last_crawl = NOW()
            WHERE author_id = :author_id
        """)
        
        with self.engine.connect() as conn:
            conn.execute(query, {"author_id": author_id})
            conn.commit()

    def save_publications(self, author_id, publications):
        """Save crawled publications"""
        insert_query = text("""
            INSERT INTO publications (author_id, title, year, source)
            VALUES (:author_id, :title, :year, :source)
            ON CONFLICT (author_id, title) DO UPDATE 
            SET year = EXCLUDED.year
        """)
        
        with self.engine.connect() as conn:
            for pub in publications:
                try:
                    conn.execute(insert_query, {
                        "author_id": author_id,
                        "title": pub["title"],
                        "year": pub.get("year"),
                        "source": pub.get("source")
                    })
                except Exception as e:
                    logging.error(f"Error saving publication: {e}")
            conn.commit()
