-- Connect to database
\c publication_db publication_user

-- Insert test authors
INSERT INTO authors (author_name, source, url) VALUES 
('Geoffrey Hinton', 'google', 'https://scholar.google.com/citations?user=JicYPdAAAAAJ'),
('Yann LeCun', 'google', 'https://scholar.google.com/citations?user=WLN3QrAAAAAJ');