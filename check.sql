-- Check crawling status
SELECT author_name, source, last_crawl 
FROM authors 
ORDER BY last_crawl DESC;

-- Check publication counts
SELECT a.author_name, COUNT(p.publication_id) as pub_count 
FROM authors a 
LEFT JOIN publications p ON a.author_id = p.author_id 
GROUP BY a.author_name;