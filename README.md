
# Academic Publication Crawler

## Project Description

This project implements a distributed web crawling system designed to collect academic publication data from Google Scholar and DBLP. The system demonstrates principles of dependable systems design through features such as fault tolerance, monitoring, and recovery mechanisms. The architecture follows a coordinator-worker pattern, utilizing RabbitMQ for robust task distribution and a PostgreSQL database for persistent data storage.

## Architecture Overview

The system comprises the following key components:

1. **Coordinator**: A central process that manages the task queue, distributes crawling tasks to worker nodes, processes results, and handles retries.
2. **Crawler Nodes**: Multiple worker processes that perform the actual web crawling of Google Scholar and DBLP, utilizing proxy rotation for robustness.
3. **Proxy Manager**: A component responsible for managing a list of proxies, handling proxy rotation, and implementing IP blocking prevention mechanisms.
4. **Database Manager**: Encapsulates all interactions with the PostgreSQL database, providing an interface for storing and retrieving author and publication data.
5. **RabbitMQ**: A message broker that implements the task queue, enabling reliable and asynchronous communication between the coordinator and crawler nodes.

## Prerequisites

*   Python 3.8+
*   PostgreSQL 12+
*   RabbitMQ 3.8+
*   Required Python packages (listed in `requirements.txt`)

## Installation

1. **Clone the Repository:**

    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2. **Create and Activate a Virtual Environment:**

    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install Required Packages:**

    ```bash
    pip install -r requirements.txt
    ```

4. **Set up PostgreSQL Database:**
    *   Create a database named `publication_db`.
    *   Create a user named `publication_user` with password `project`.
    *   Grant necessary privileges to the user. You can use the provided `schema.sql` script to set up the database and user:
        ```bash
        psql -U postgres -f schema.sql
        ```
     **Note:** It is good practice to change the default user and password for the database.

5. **Install and Configure RabbitMQ:**

    **Linux (Ubuntu/Debian):**

    ```bash
    # Install RabbitMQ
    sudo apt-get install rabbitmq-server

    # Start RabbitMQ service
    sudo systemctl start rabbitmq-server

    # Enable the management plugin (optional, but recommended)
    sudo rabbitmq-plugins enable rabbitmq_management
    ```

    **Windows:**

    1. **Install Erlang:**
        *   Download and install the latest Erlang/OTP release for Windows from [https://www.erlang.org/downloads](https://www.erlang.org/downloads).
        *   Add the Erlang `bin` directory (e.g., `C:\Program Files\erl-<version>\bin`) to your system's `PATH` environment variable.

    2. **Install RabbitMQ:**
        *   Download and install the latest RabbitMQ server release for Windows from [https://www.rabbitmq.com/download.html](https://www.rabbitmq.com/download.html).
        *   It's recommended to install RabbitMQ as a service (default option).

    3. **Enable the Management Plugin:**
        *   Open a **command prompt as administrator**.
        *   Navigate to the RabbitMQ `sbin` directory (e.g., `C:\Program Files\RabbitMQ Server\rabbitmq_server-<version>\sbin`).
        *   Run the following command:

            ```bash
            rabbitmq-plugins enable rabbitmq_management
            ```

    4. **Start the RabbitMQ Service:**

        *   If installed as a service, it should be running. You can manage it via the Windows Services manager (search for "Services" in the Start menu).
        *   To start/stop from the command line (as administrator):

            ```bash
            net start RabbitMQ  # To start
            net stop RabbitMQ   # To stop
            ```

    5. **Access the Management Interface:**

        *   Open your web browser and go to `http://localhost:15672/`.
        *   Log in with the default credentials:
            *   Username: `guest`
            *   Password: `guest`
        *   **Important:** Change the default `guest` user's password or create a new administrator user immediately for security reasons.

6. **Configure Proxy List (Optional):**

    *   Create a file named `ips.txt` in the project root directory.
    *   Add your proxy list to `ips.txt` in the following format (one proxy per line):

        ```
        ip:port
        ip:port:username:password
        ```

## Configuration

The system can be configured through environment variables or by modifying the `config.py` file. Key configuration options include:

```python
# RabbitMQ Configuration
RABBITMQ_HOST = 'localhost'  # Hostname or IP address of the RabbitMQ server
QUEUE_NAME = 'crawl_queue'    # Name of the RabbitMQ queue

# Database Configuration
DB_USER = 'publication_user'  # PostgreSQL database user
DB_PASS = 'project'           # PostgreSQL database password
DB_HOST = 'localhost'         # PostgreSQL database host
DB_NAME = 'publication_db'    # PostgreSQL database name

# Crawler Configuration
MAX_RETRIES = 3               # Maximum number of retries for failed tasks
NUM_CRAWLERS = 3              # Number of crawler instances to run concurrently
```

## Usage

1. **Start the System:**

    ```bash
    python main.py
    ```

    This will start:

    *   1 coordinator process
    *   3 crawler nodes (configurable via `NUM_CRAWLERS` in `config.py`)

2. **Adding Authors to Crawl:**

    Insert authors into the `authors` table of the `publication_db` database using SQL `INSERT` statements. For example:

    ```sql
    INSERT INTO authors (author_name, source, url) VALUES
    ('Ciprian Dobre', 'google', 'https://scholar.google.ro/citations?user=_44USrIAAAAJ'),
    ('Fatos Xhafa', 'google', 'https://scholar.google.com/citations?user=R--Cy5cAAAAJ&hl=en');
    ```

    **Important:** Ensure the `source` is either 'google' or 'dblp' (currently, only Google Scholar is fully implemented). The `url` should be the complete URL to the author's profile page on the respective platform.

## System Features (Dependability Focus)

This project demonstrates several features relevant to dependable systems:

### Fault Tolerance

*   **Automatic Retries:** The coordinator implements a retry mechanism for failed crawling tasks. If a crawler encounters an error (e.g., network issue, parsing error), the task is re-queued for a configurable number of retries (`MAX_RETRIES`).
*   **Proxy Rotation:** The `ProxyManager` component handles proxy rotation. If a proxy is blocked or fails, the crawler automatically switches to a different proxy, preventing a single point of failure.
*   **Heartbeat Monitoring:** The coordinator monitors the status of crawler nodes through periodic heartbeats. If a crawler becomes inactive (no heartbeat received within a timeout), the coordinator can take action (e.g., log a warning, potentially restart the crawler in a more advanced implementation).
*   **Transaction-Safe Database Operations:** The `DBManager` uses database transactions to ensure that data is updated atomically. If an error occurs during an update, the transaction is rolled back, preventing data corruption.

### Rate Limiting

*   **Configurable Delays:** The system allows you to configure delays between requests to avoid overloading target websites (Google Scholar, DBLP).
*   **IP-Based Rate Limiting:** The `ProxyManager` can track the last usage time of each IP and enforce a minimum interval between requests from the same IP.
*   **Automatic Blocking Detection:** The crawler attempts to identify potential IP blocks by inspecting HTTP status codes (e.g., 403, 429) and can mark proxies as blocked.

### Scalability

*   **Multiple Crawler Nodes:** The system supports running multiple crawler instances concurrently, distributing the workload and improving crawling speed.
*   **Distributed Task Queue:** RabbitMQ provides a robust and scalable message queue, allowing for efficient task distribution among multiple crawlers.
*   **Connection Pooling:** The `DBManager` uses connection pooling to efficiently manage database connections, reducing overhead and improving performance.

## Monitoring and Maintenance

### Logging

The system logs important events, including:

*   Task generation and publishing
*   Task processing by crawlers
*   Successful crawls and database updates
*   Errors and warnings
*   Heartbeat messages
*   Proxy-related events

Logs are written to both the console and the `crawler.log` file. You can monitor the system's activity using:

```bash
tail -f crawler.log
```

### Database Maintenance

Regular database maintenance is recommended for optimal performance:

```sql
-- Clean up old data (e.g., publications older than a year)
DELETE FROM publications WHERE updated_at < NOW() - INTERVAL '1 year';

-- Vacuum the database to reclaim space and improve performance
VACUUM ANALYZE authors, publications;
```

### RabbitMQ Monitoring

You can monitor the RabbitMQ queue and connections using the RabbitMQ management interface (if enabled):

1. Open your web browser and go to `http://localhost:15672/`.
2. Log in with your RabbitMQ credentials.

You can also use the command-line tools:

```bash
# View queue status
rabbitmqctl list_queues

# View connections
rabbitmqctl list_connections
```

## Diagnostics

The project includes `diagnostics.py` to help troubleshoot common issues. This script performs the following checks:

1. **Database Connection and Authors:**
    *   Verifies that a connection to the PostgreSQL database can be established.
    *   Checks for the existence of the `authors` and `publications` tables.
    *   Prints the number of authors and publications found.
    *   If no authors are found, it provides instructions on how to add them using SQL.
    *   Checks the `last_crawl` status of authors.

2. **RabbitMQ Connection and Queue:**
    *   Verifies that a connection to RabbitMQ can be established.
    *   Checks the status of the `crawl_queue` and prints the number of messages in it.

3. **Enhanced Crawler Debugging:**
    *   Retrieves sample messages (including heartbeats and potential crawl tasks) from the queue without removing them.
    *   Prints the content of these messages for analysis.
    *   If a crawl task is found, it attempts a test crawl of the specified URL.
    *   Checks for signs of crawler detection in the response.
    *   Tries to find publication elements on the page using the configured selectors.

To run the diagnostics:

```bash
python diagnostics.py
```

This script will provide valuable information about the system's health and help identify potential problems.

## Troubleshooting

1. **Connection Issues:**
    *   Ensure the RabbitMQ service is running.
    *   Verify the database credentials (`DB_USER`, `DB_PASS`) and connection details (`DB_HOST`, `DB_NAME`) in `config.py`.
    *   Check if the proxy list (`ips.txt`) is properly formatted and the proxies are working.

2. **Crawling Issues:**
    *   Examine the `crawler.log` for error messages related to IP blocking, rate limiting, or parsing errors.
    *   Inspect the raw HTML source of the target websites (Google Scholar, DBLP) to ensure that the CSS selectors in `config.py` are still valid.
    *   Verify that the proxy list is up-to-date and the proxies are functional.
    *   If pages are heavily JavaScript-dependent, consider using a headless browser.

3. **Performance Issues:**
    *   Monitor database performance and ensure indexes are properly configured (see Database Maintenance).
    *   Check the RabbitMQ queue length. If it's consistently high, consider increasing the number of crawler nodes or optimizing task processing time.
    *   Adjust the `MIN_REQUEST_INTERVAL` and other relevant parameters in `config.py` to fine-tune the crawling rate.

## Future Improvements

*   **DBLP Support:** Implement crawling for DBLP, including parsing logic and data storage.
*   **Enhanced Error Handling:** Add more specific error handling and retry mechanisms for different types of exceptions.
*   **Dynamic Task Generation:** Implement logic to dynamically discover new authors to crawl based on existing data.
*   **User Interface:** Create a web interface to manage authors, view crawl status, and visualize results.
*   **JavaScript Rendering:** Integrate a headless browser (e.g., Selenium, Playwright) to handle websites that heavily rely on JavaScript.

## Contributing

Contributions to this project are welcome. To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them with clear and concise messages.
4. Submit a pull request to the main repository.
