"""
Web scraper for monitoring device web interfaces.
"""

import asyncio
import logging
import json
import re
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

try:
    import aiohttp
    from bs4 import BeautifulSoup
    AIOHTTP_AVAILABLE = True
    BS4_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    BS4_AVAILABLE = False
    # Mock classes
    class ClientSession: pass
    class BeautifulSoup: pass


@dataclass
class WebConfig:
    """Web scraper configuration."""
    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    auth_token: Optional[str] = None
    headers: Dict[str, str] = None
    cookies: Dict[str, str] = None
    timeout: int = 30
    verify_ssl: bool = True
    user_agent: str = "NetworkMonitoringAgent/1.0"
    max_redirects: int = 5
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.cookies is None:
            self.cookies = {}


class WebScrapingError(Exception):
    """Web scraping related error."""
    pass


class WebScraper:
    """
    Asynchronous web scraper for device monitoring.
    
    Supports authentication, session management, and data extraction
    from web interfaces of network devices.
    """
    
    def __init__(self):
        """Initialize web scraper."""
        self.logger = logging.getLogger(__name__)
        self.config: Optional[WebConfig] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_configured = False
        
        if not AIOHTTP_AVAILABLE:
            self.logger.warning("aiohttp not available, web scraping functionality disabled")
        if not BS4_AVAILABLE:
            self.logger.warning("beautifulsoup4 not available, HTML parsing limited")
    
    def configure(self, base_url: str, username: str = None, password: str = None,
                 auth_token: str = None, headers: Dict[str, str] = None,
                 cookies: Dict[str, str] = None, timeout: int = 30,
                 verify_ssl: bool = True, user_agent: str = None):
        """
        Configure web scraper.
        
        Args:
            base_url: Base URL of the device web interface
            username: Username for authentication
            password: Password for authentication
            auth_token: Authentication token (Bearer, API key, etc.)
            headers: Additional HTTP headers
            cookies: Initial cookies
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            user_agent: User agent string
        """
        if not AIOHTTP_AVAILABLE:
            raise WebScrapingError("aiohttp not available")
        
        self.config = WebConfig(
            base_url=base_url.rstrip('/'),
            username=username,
            password=password,
            auth_token=auth_token,
            headers=headers or {},
            cookies=cookies or {},
            timeout=timeout,
            verify_ssl=verify_ssl,
            user_agent=user_agent or "NetworkMonitoringAgent/1.0"
        )
        
        # Set default headers
        if 'User-Agent' not in self.config.headers:
            self.config.headers['User-Agent'] = self.config.user_agent
        
        # Set authorization header if token provided
        if self.config.auth_token:
            self.config.headers['Authorization'] = f"Bearer {self.config.auth_token}"
        
        self.is_configured = True
        self.logger.info(f"Web scraper configured for {base_url}")
    
    async def start_session(self):
        """Start HTTP session."""
        if not self.is_configured:
            raise WebScrapingError("Web scraper not configured")
        
        if self.session and not self.session.closed:
            return
        
        # Create SSL context
        ssl_context = None if self.config.verify_ssl else False
        
        # Create timeout
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        
        # Create session
        self.session = aiohttp.ClientSession(
            headers=self.config.headers,
            cookies=self.config.cookies,
            timeout=timeout,
            connector=aiohttp.TCPConnector(ssl=ssl_context)
        )
        
        self.logger.debug("HTTP session started")
    
    async def close_session(self):
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
        self.logger.debug("HTTP session closed")
    
    async def login(self, login_url: str = None, username_field: str = "username",
                   password_field: str = "password", form_selector: str = "form",
                   additional_fields: Dict[str, str] = None) -> bool:
        """
        Perform login to web interface.
        
        Args:
            login_url: Login page URL (relative to base_url)
            username_field: Username field name
            password_field: Password field name
            form_selector: CSS selector for login form
            additional_fields: Additional form fields
            
        Returns:
            bool: True if login successful
            
        Raises:
            WebScrapingError: If login fails
        """
        if not self.config.username or not self.config.password:
            raise WebScrapingError("Username and password required for login")
        
        await self.start_session()
        
        try:
            # Get login page
            login_url = login_url or "/login"
            full_url = urljoin(self.config.base_url, login_url)
            
            async with self.session.get(full_url) as response:
                if response.status != 200:
                    raise WebScrapingError(f"Login page request failed: {response.status}")
                
                html = await response.text()
            
            # Parse login form
            if BS4_AVAILABLE:
                soup = BeautifulSoup(html, 'html.parser')
                form = soup.select_one(form_selector)
                
                if not form:
                    raise WebScrapingError("Login form not found")
                
                # Extract form action and method
                action = form.get('action', login_url)
                method = form.get('method', 'POST').upper()
                
                # Build form data
                form_data = {
                    username_field: self.config.username,
                    password_field: self.config.password
                }
                
                # Add hidden fields
                for input_field in form.find_all('input', type='hidden'):
                    name = input_field.get('name')
                    value = input_field.get('value', '')
                    if name:
                        form_data[name] = value
                
                # Add additional fields
                if additional_fields:
                    form_data.update(additional_fields)
                
            else:
                # Fallback without BeautifulSoup
                action = login_url
                method = 'POST'
                form_data = {
                    username_field: self.config.username,
                    password_field: self.config.password
                }
                if additional_fields:
                    form_data.update(additional_fields)
            
            # Submit login form
            submit_url = urljoin(self.config.base_url, action)
            
            if method == 'GET':
                async with self.session.get(submit_url, params=form_data) as response:
                    login_response = response
            else:
                async with self.session.post(submit_url, data=form_data) as response:
                    login_response = response
            
            # Check if login was successful
            if login_response.status in [200, 302, 303]:
                # Look for success indicators
                response_text = await login_response.text()
                
                # Common failure indicators
                failure_indicators = [
                    'invalid', 'error', 'failed', 'incorrect',
                    'wrong', 'denied', 'unauthorized'
                ]
                
                response_lower = response_text.lower()
                if any(indicator in response_lower for indicator in failure_indicators):
                    # Check if it's actually an error message
                    if 'login' in response_lower and any(indicator in response_lower for indicator in failure_indicators):
                        raise WebScrapingError("Login failed: Invalid credentials")
                
                self.logger.info("Login successful")
                return True
            else:
                raise WebScrapingError(f"Login failed with status: {login_response.status}")
                
        except Exception as e:
            self.logger.error(f"Login failed: {e}")
            raise WebScrapingError(f"Login failed: {e}")
    
    async def get(self, url: str, params: Dict[str, str] = None) -> str:
        """
        Perform GET request.
        
        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            
        Returns:
            str: Response text
            
        Raises:
            WebScrapingError: If request fails
        """
        await self.start_session()
        
        try:
            full_url = urljoin(self.config.base_url, url)
            
            async with self.session.get(full_url, params=params) as response:
                if response.status != 200:
                    raise WebScrapingError(f"GET request failed: {response.status}")
                
                return await response.text()
                
        except Exception as e:
            self.logger.error(f"GET request failed: {e}")
            raise WebScrapingError(f"GET request failed: {e}")
    
    async def post(self, url: str, data: Dict[str, Any] = None,
                  json_data: Dict[str, Any] = None) -> str:
        """
        Perform POST request.
        
        Args:
            url: URL path (relative to base_url)
            data: Form data
            json_data: JSON data
            
        Returns:
            str: Response text
            
        Raises:
            WebScrapingError: If request fails
        """
        await self.start_session()
        
        try:
            full_url = urljoin(self.config.base_url, url)
            
            if json_data:
                async with self.session.post(full_url, json=json_data) as response:
                    result_response = response
            else:
                async with self.session.post(full_url, data=data) as response:
                    result_response = response
            
            if result_response.status not in [200, 201]:
                raise WebScrapingError(f"POST request failed: {result_response.status}")
            
            return await result_response.text()
            
        except Exception as e:
            self.logger.error(f"POST request failed: {e}")
            raise WebScrapingError(f"POST request failed: {e}")
    
    async def get_json(self, url: str, params: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Perform GET request and parse JSON response.
        
        Args:
            url: URL path (relative to base_url)
            params: Query parameters
            
        Returns:
            Dict[str, Any]: Parsed JSON data
            
        Raises:
            WebScrapingError: If request fails or JSON parsing fails
        """
        await self.start_session()
        
        try:
            full_url = urljoin(self.config.base_url, url)
            
            async with self.session.get(full_url, params=params) as response:
                if response.status != 200:
                    raise WebScrapingError(f"GET request failed: {response.status}")
                
                return await response.json()
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed: {e}")
            raise WebScrapingError(f"JSON parsing failed: {e}")
        except Exception as e:
            self.logger.error(f"GET JSON request failed: {e}")
            raise WebScrapingError(f"GET JSON request failed: {e}")
    
    async def post_json(self, url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform POST request with JSON data and parse JSON response.
        
        Args:
            url: URL path (relative to base_url)
            data: JSON data to send
            
        Returns:
            Dict[str, Any]: Parsed JSON response
            
        Raises:
            WebScrapingError: If request fails or JSON parsing fails
        """
        await self.start_session()
        
        try:
            full_url = urljoin(self.config.base_url, url)
            
            async with self.session.post(full_url, json=data) as response:
                if response.status not in [200, 201]:
                    raise WebScrapingError(f"POST request failed: {response.status}")
                
                return await response.json()
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed: {e}")
            raise WebScrapingError(f"JSON parsing failed: {e}")
        except Exception as e:
            self.logger.error(f"POST JSON request failed: {e}")
            raise WebScrapingError(f"POST JSON request failed: {e}")
    
    def parse_html(self, html: str, selector: str = None) -> Union[BeautifulSoup, Any]:
        """
        Parse HTML content.
        
        Args:
            html: HTML content
            selector: CSS selector to find specific elements
            
        Returns:
            BeautifulSoup object or selected elements
            
        Raises:
            WebScrapingError: If parsing fails
        """
        if not BS4_AVAILABLE:
            raise WebScrapingError("BeautifulSoup not available for HTML parsing")
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            if selector:
                return soup.select(selector)
            else:
                return soup
                
        except Exception as e:
            self.logger.error(f"HTML parsing failed: {e}")
            raise WebScrapingError(f"HTML parsing failed: {e}")
    
    def extract_text(self, html: str, selector: str) -> List[str]:
        """
        Extract text content from HTML elements.
        
        Args:
            html: HTML content
            selector: CSS selector
            
        Returns:
            List[str]: Extracted text content
        """
        try:
            elements = self.parse_html(html, selector)
            return [elem.get_text(strip=True) for elem in elements]
        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            return []
    
    def extract_attributes(self, html: str, selector: str, attribute: str) -> List[str]:
        """
        Extract attribute values from HTML elements.
        
        Args:
            html: HTML content
            selector: CSS selector
            attribute: Attribute name
            
        Returns:
            List[str]: Extracted attribute values
        """
        try:
            elements = self.parse_html(html, selector)
            return [elem.get(attribute, '') for elem in elements if elem.get(attribute)]
        except Exception as e:
            self.logger.error(f"Attribute extraction failed: {e}")
            return []
    
    def extract_table_data(self, html: str, table_selector: str = "table") -> List[Dict[str, str]]:
        """
        Extract data from HTML table.
        
        Args:
            html: HTML content
            table_selector: CSS selector for table
            
        Returns:
            List[Dict[str, str]]: Table data as list of dictionaries
        """
        try:
            soup = self.parse_html(html)
            table = soup.select_one(table_selector)
            
            if not table:
                return []
            
            # Extract headers
            headers = []
            header_row = table.select_one('thead tr') or table.select_one('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.select('th, td')]
            
            # Extract data rows
            rows = []
            data_rows = table.select('tbody tr') or table.select('tr')[1:]  # Skip header if no tbody
            
            for row in data_rows:
                cells = [td.get_text(strip=True) for td in row.select('td')]
                if cells and len(cells) == len(headers):
                    row_data = dict(zip(headers, cells))
                    rows.append(row_data)
            
            return rows
            
        except Exception as e:
            self.logger.error(f"Table extraction failed: {e}")
            return []
    
    def extract_form_data(self, html: str, form_selector: str = "form") -> Dict[str, str]:
        """
        Extract form field data.
        
        Args:
            html: HTML content
            form_selector: CSS selector for form
            
        Returns:
            Dict[str, str]: Form field data
        """
        try:
            soup = self.parse_html(html)
            form = soup.select_one(form_selector)
            
            if not form:
                return {}
            
            form_data = {}
            
            # Extract input fields
            for input_field in form.select('input'):
                name = input_field.get('name')
                value = input_field.get('value', '')
                if name:
                    form_data[name] = value
            
            # Extract select fields
            for select_field in form.select('select'):
                name = select_field.get('name')
                selected_option = select_field.select_one('option[selected]')
                if name and selected_option:
                    form_data[name] = selected_option.get('value', '')
            
            # Extract textarea fields
            for textarea in form.select('textarea'):
                name = textarea.get('name')
                if name:
                    form_data[name] = textarea.get_text()
            
            return form_data
            
        except Exception as e:
            self.logger.error(f"Form extraction failed: {e}")
            return {}
    
    def extract_metrics_by_regex(self, text: str, patterns: Dict[str, str]) -> Dict[str, str]:
        """
        Extract metrics using regular expressions.
        
        Args:
            text: Text content to search
            patterns: Dictionary of metric_name -> regex_pattern
            
        Returns:
            Dict[str, str]: Extracted metrics
        """
        metrics = {}
        
        for metric_name, pattern in patterns.items():
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                if match:
                    # Use first group if available, otherwise full match
                    value = match.group(1) if match.groups() else match.group(0)
                    metrics[metric_name] = value.strip()
            except Exception as e:
                self.logger.error(f"Regex extraction failed for {metric_name}: {e}")
        
        return metrics
    
    async def scrape_ubiquiti_unifi(self) -> Dict[str, Any]:
        """
        Scrape Ubiquiti UniFi controller for device metrics.
        
        Returns:
            Dict[str, Any]: Device metrics
        """
        try:
            # Login to UniFi controller
            await self.login('/login', 'username', 'password')
            
            # Get device status
            devices_data = await self.get_json('/api/s/default/stat/device')
            
            metrics = {}
            if 'data' in devices_data:
                for device in devices_data['data']:
                    device_id = device.get('mac', device.get('_id', 'unknown'))
                    metrics[device_id] = {
                        'name': device.get('name', 'Unknown'),
                        'model': device.get('model', 'Unknown'),
                        'version': device.get('version', 'Unknown'),
                        'uptime': device.get('uptime', 0),
                        'clients': device.get('num_sta', 0),
                        'cpu_usage': device.get('system-stats', {}).get('cpu', 0),
                        'memory_usage': device.get('system-stats', {}).get('mem', 0),
                        'satisfaction': device.get('satisfaction', 0)
                    }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"UniFi scraping failed: {e}")
            return {}
    
    async def scrape_pfsense(self) -> Dict[str, Any]:
        """
        Scrape pfSense firewall for system metrics.
        
        Returns:
            Dict[str, Any]: System metrics
        """
        try:
            # Login to pfSense
            await self.login('/index.php', 'usernamefld', 'passwordfld')
            
            # Get system status page
            status_html = await self.get('/status.php')
            
            # Extract metrics using regex patterns
            patterns = {
                'cpu_usage': r'CPU usage:\s*(\d+(?:\.\d+)?)%',
                'memory_usage': r'Memory usage:\s*(\d+(?:\.\d+)?)%',
                'uptime': r'Uptime:\s*(.+?)(?:\n|<)',
                'load_average': r'Load average:\s*(\d+(?:\.\d+)?)',
                'temperature': r'Temperature:\s*(\d+(?:\.\d+)?)\s*°C'
            }
            
            metrics = self.extract_metrics_by_regex(status_html, patterns)
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"pfSense scraping failed: {e}")
            return {}
    
    async def test_connection(self) -> bool:
        """
        Test web connection.
        
        Returns:
            bool: True if connection is working
        """
        try:
            await self.start_session()
            response = await self.get('/')
            return len(response) > 0
        except Exception:
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get configuration information."""
        if not self.config:
            return {'configured': False}
        
        return {
            'configured': self.is_configured,
            'base_url': self.config.base_url,
            'username': self.config.username,
            'has_password': bool(self.config.password),
            'has_auth_token': bool(self.config.auth_token),
            'timeout': self.config.timeout,
            'verify_ssl': self.config.verify_ssl,
            'user_agent': self.config.user_agent
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()