import logging
from main import main
import sys
import os

if __name__ == "__main__":
    # Ensure the crawler.log file exists and is writable
    log_file = 'crawler.log'
    try:
        with open(log_file, 'a') as f:
            pass
    except IOError as e:
        print(f"Error: Cannot write to {log_file}: {e}")
        sys.exit(1)

    # Create an ips.txt file with some example proxies if it doesn't exist
    if not os.path.exists('ips.txt'):
        example_proxies = [
            "127.0.0.1:8080",
            "127.0.0.1:8081",
            "127.0.0.1:8082"
        ]
        with open('ips.txt', 'w') as f:
            f.write('\n'.join(example_proxies))
        print("Created example ips.txt file")

    print("Starting crawler system...")
    print("Press Ctrl+C to stop")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down crawler system...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)