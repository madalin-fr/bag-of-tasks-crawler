# db_manager.py
from sqlalchemy import create_engine, text
from datetime import datetime
import logging
from typing import List, Dict, Any
from contextlib import contextmanager
from config import DATABASE_URL, GOOGLE_SCHOLAR_INTERVAL, DBLP_INTERVAL

class DBManager:
    """Database manager with singleton pattern"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            try:
                cls._instance._initialize()
            except Exception as e:
                cls._instance = None  # Reset instance if initialization fails
                raise
        return cls._instance
    
    def _initialize(self):
        """Initialize the database connection"""
        try:
            self.engine = create_engine(DATABASE_URL)
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.initialized = True
            logging.info("Database connection initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize database: {e}")
            raise

    def __init__(self):
        """Ensure initialization happened"""
        if not hasattr(self, 'initialized') or not self.initialized:
            raise RuntimeError("DBManager not properly initialized")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with better error handling"""
        if not hasattr(self, 'engine') or not self.initialized:
            raise RuntimeError("Database not initialized")
            
        conn = None
        try:
            conn = self.engine.connect()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logging.error(f"Database operation failed: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def get_authors_for_crawling(self) -> List[Dict[str, Any]]:
        """Get authors that need to be crawled"""
        try:
            query = text("""
                SELECT 
                    author_id,
                    author_name,
                    source,
                    url,
                    last_crawl
                FROM authors
                WHERE last_crawl IS NULL
                OR (source = 'google' AND last_crawl < NOW() - :google_interval)
                OR (source = 'dblp' AND last_crawl < NOW() - :dblp_interval)
            """)
            
            with self.get_connection() as conn:
                result = conn.execute(query, {
                    "google_interval": GOOGLE_SCHOLAR_INTERVAL,
                    "dblp_interval": DBLP_INTERVAL
                })
                
                return [
                    {
                        "author_id": row.author_id,
                        "author_name": row.author_name,
                        "source": row.source,
                        "url": row.url,
                        "last_crawl": row.last_crawl
                    }
                    for row in result
                ]
        except Exception as e:
            logging.error(f"Error getting authors for crawling: {e}")
            return []
    
    def update_publications(self, author_id: int, publications: List[Dict[str, Any]]) -> None:
        """Update author's publications in a single transaction"""
        try:
            with self.get_connection() as conn:
                # Update last crawl time
                self.update_last_crawl(author_id)
                
                # Insert/update publications
                insert_query = text("""
                    INSERT INTO publications (author_id, title, year, source)
                    VALUES (:author_id, :title, :year, :source)
                    ON CONFLICT (author_id, title) DO UPDATE
                    SET year = EXCLUDED.year, 
                        updated_at = NOW()
                """)
                
                for pub in publications:
                    try:
                        conn.execute(insert_query, {
                            "author_id": author_id,
                            "title": pub["title"],
                            "year": pub.get("year"),
                            "source": pub.get("source", "unknown")
                        })
                    except Exception as e:
                        logging.error(f"Error saving publication: {e}")
        except Exception as e:
            logging.error(f"Error updating publications: {e}")
            raise

    def update_last_crawl(self, author_id: int) -> None:
        """Update author's last_crawl timestamp"""
        try:
            with self.get_connection() as conn:
                update_query = text("""
                    UPDATE authors 
                    SET last_crawl = NOW() 
                    WHERE author_id = :author_id
                """)
                conn.execute(update_query, {"author_id": author_id})
                logging.info(f"Updated last_crawl for author {author_id}")
        except Exception as e:
            logging.error(f"Error updating last_crawl: {e}")
            raise