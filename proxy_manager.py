# proxy_manager.py
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, NamedTuple
import os
from config import IP_BLOCK_DURATION, MIN_REQUEST_INTERVAL

class ProxyInfo(NamedTuple):
    """Structure for storing proxy information"""
    host: str
    port: str
    username: Optional[str] = None
    password: Optional[str] = None

class ProxyManager:
    """Single source of truth for proxy/IP management with authentication support"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.blocked_ips: Dict[str, datetime] = {}
            self.ip_last_used: Dict[str, datetime] = {}
            self.proxy_list = self._load_proxies()
            self.initialized = True
    
    def _parse_proxy_line(self, line: str) -> Optional[ProxyInfo]:
        """Parse a proxy line in format IP:PORT or IP:PORT:USERNAME:PASSWORD"""
        try:
            parts = line.strip().split(':')
            if len(parts) == 2:
                return ProxyInfo(host=parts[0], port=parts[1])
            elif len(parts) == 4:
                return ProxyInfo(
                    host=parts[0],
                    port=parts[1],
                    username=parts[2],
                    password=parts[3]
                )
            else:
                logging.error(f"Invalid proxy format: {line}")
                return None
        except Exception as e:
            logging.error(f"Error parsing proxy line {line}: {e}")
            return None
    
    def _load_proxies(self) -> List[ProxyInfo]:
        """Load proxies from file, supporting both authenticated and non-authenticated formats"""
        try:
            proxy_file = os.getenv('PROXY_FILE', 'ips.txt')
            proxies = []
            with open(proxy_file, 'r') as f:
                for line in f:
                    proxy_info = self._parse_proxy_line(line)
                    if proxy_info:
                        proxies.append(proxy_info)
            return proxies
        except FileNotFoundError:
            logging.error(f"Proxy file {proxy_file} not found")
            return []
        except Exception as e:
            logging.error(f"Error loading proxies: {e}")
            return []

    def _format_proxy_url(self, proxy: ProxyInfo) -> str:
        """Format proxy information into a URL"""
        if proxy.username and proxy.password:
            return f"http://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        return f"http://{proxy.host}:{proxy.port}"

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """Get next available proxy with rate limiting"""
        current_time = datetime.now()
        
        for proxy in self.proxy_list:
            # Use host as the IP for tracking
            ip = proxy.host
            
            # Skip blocked IPs
            if ip in self.blocked_ips:
                if current_time - self.blocked_ips[ip] < timedelta(seconds=IP_BLOCK_DURATION):
                    continue
                del self.blocked_ips[ip]
            
            # Check rate limiting
            if ip in self.ip_last_used:
                if current_time - self.ip_last_used[ip] < timedelta(seconds=MIN_REQUEST_INTERVAL):
                    continue
            
            self.ip_last_used[ip] = current_time
            proxy_url = self._format_proxy_url(proxy)
            return {'http': proxy_url, 'https': proxy_url}
        
        return None

    def mark_blocked(self, proxy_url: str) -> None:
        """Mark an IP as blocked"""
        try:
            # Extract IP from proxy URL
            ip = proxy_url.split('@')[-1].split(':')[0]
            self.blocked_ips[ip] = datetime.now()
            logging.info(f"Marked IP {ip} as blocked")
        except Exception as e:
            logging.error(f"Error marking IP as blocked: {e}")
        
    def release_proxy(self, proxy_url: str) -> None:
        """Release a proxy back to the pool"""
        try:
            ip = proxy_url.split('@')[-1].split(':')[0]
            if ip in self.ip_last_used:
                del self.ip_last_used[ip]
        except Exception as e:
            logging.error(f"Error releasing proxy: {e}")