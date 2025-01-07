# Academic Publication Crawler

A distributed web crawling system designed to collect publication data from Google Scholar and DBLP. The system uses a coordinator-worker architecture with RabbitMQ for task distribution and PostgreSQL for data storage.

## Architecture Overview

The system consists of several key components:

1. **Coordinator**: Manages task distribution and result processing
2. **Crawler Nodes**: Worker processes that perform the actual web crawling
3. **Proxy Manager**: Handles proxy rotation and IP blocking prevention
4. **Database Manager**: Manages PostgreSQL database operations
5. **RabbitMQ**: Message queue for task distribution

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- RabbitMQ 3.8+
- Required Python packages (see Installation section)

## Installation

1. Clone the repository:


2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

4. Set up PostgreSQL database:
**Note:** These instructions are for the stable RabbitMQ 3.x release series (3.8 - 3.12). If you are using a pre-release version of RabbitMQ 4.x, consult the specific documentation for that version as there might be changes.

### Linux (Ubuntu/Debian)

```bash
# Install RabbitMQ
sudo apt-get install rabbitmq-server

# Start RabbitMQ service
sudo systemctl start rabbitmq-server

# Enable the management plugin (optional, but recommended)
sudo rabbitmq-plugins enable rabbitmq_management
```

### Windows

1.  **Install Erlang:**
    *   Download and install the latest Erlang/OTP release for Windows from [https://www.erlang.org/downloads](https://www.erlang.org/downloads).
    *   Add the Erlang `bin` directory (e.g., `C:\Program Files\erl-<version>\bin`) to your system's `PATH` environment variable.

2.  **Install RabbitMQ:**
    *   Download and install the latest RabbitMQ server release for Windows from [https://www.rabbitmq.com/download.html](https://www.rabbitmq.com/download.html).
    *   It's recommended to install RabbitMQ as a service (default option).

3.  **Enable the Management Plugin:**
    *   Open a **command prompt as administrator**.
    *   Navigate to the RabbitMQ `sbin` directory (e.g., `C:\Program Files\RabbitMQ Server\rabbitmq_server-<version>\sbin`).
    *   Run the following command:

        ```bash
        rabbitmq-plugins enable rabbitmq_management
        ```

4.  **Start the RabbitMQ Service:**

    *   If installed as a service, it should be running. You can manage it via the Windows Services manager (search for "Services" in the Start menu).
    *   To start/stop from the command line (as administrator):

        ```bash
        net start RabbitMQ  # To start
        net stop RabbitMQ   # To stop
        ```

5.  **Access the Management Interface:**

    *   Open your web browser and go to `http://localhost:15672/`.
    *   Log in with the default credentials:
        *   Username: `guest`
        *   Password: `guest`
    *   **Important:** Change the default `guest` user's password or create a new administrator user immediately for security reasons.


6. Configure proxy list:
Create a file named `ips.txt` in the project root with your proxy list in the following format:
```
ip:port
ip:port:username:password
```

## Configuration

The system can be configured through environment variables or by modifying `config.py`. Key configuration options include:

```python
# RabbitMQ Configuration
RABBITMQ_HOST = 'localhost'
QUEUE_NAME = 'crawl_queue'

# Database Configuration
DB_USER = 'publication_user'
DB_PASS = 'project'
DB_HOST = 'localhost'
DB_NAME = 'publication_db'

# Crawler Configuration
MAX_RETRIES = 3
NUM_CRAWLERS = 3
```

## Usage

1. Start the system:
```bash
python main.py
```

This will start:
- 1 coordinator process
- 3 crawler nodes (configurable via NUM_CRAWLERS)
- RabbitMQ message queue
- Database connection pool

2. Adding authors to crawl:

Insert authors into the database using SQL:
```sql
INSERT INTO authors (author_name, source, url) VALUES 
('John Doe', 'google', 'https://scholar.google.com/citations?user=xxx'),
('Jane Smith', 'dblp', 'https://dblp.org/pid/xxx');
```

3. Monitor the system:

Check crawling status:
```sql
SELECT author_name, source, last_crawl
FROM authors
ORDER BY last_crawl DESC;
```

Check publication counts:
```sql
SELECT a.author_name, COUNT(p.publication_id) as pub_count
FROM authors a
LEFT JOIN publications p ON a.author_id = p.author_id
GROUP BY a.author_name;
```

## System Features

### Fault Tolerance
- Automatic retry mechanism for failed tasks
- Proxy rotation to prevent IP blocking
- Heartbeat monitoring of crawler nodes
- Transaction-safe database operations

### Rate Limiting
- Configurable delays between requests
- IP-based rate limiting
- Automatic IP blocking detection

### Scalability
- Multiple crawler nodes can run simultaneously
- Distributed task queue using RabbitMQ
- Connection pooling for database operations

## Monitoring and Maintenance

### Logging
The system logs important events to both console and `crawler.log`:
```bash
tail -f crawler.log
```

### Database Maintenance
Regular maintenance tasks:
```sql
-- Clean up old data
DELETE FROM publications WHERE updated_at < NOW() - INTERVAL '1 year';

-- Vacuum the database
VACUUM ANALYZE authors, publications;
```

### RabbitMQ Monitoring
Monitor the RabbitMQ queue:
```bash
# View queue status
rabbitmqctl list_queues

# View connections
rabbitmqctl list_connections
```

## Troubleshooting

1. **Connection Issues**
   - Check if RabbitMQ service is running
   - Verify database credentials and connection
   - Ensure proxy list is properly formatted

2. **Crawling Issues**
   - Check for IP blocking in logs
   - Verify proxy list is valid and accessible
   - Ensure target URLs are correctly formatted

3. **Performance Issues**
   - Monitor database indexes
   - Check RabbitMQ queue size
   - Adjust number of crawler nodes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request
