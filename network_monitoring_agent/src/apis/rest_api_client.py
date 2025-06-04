"""
REST API client for device monitoring via HTTP APIs.
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin
from dataclasses import dataclass

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    # Mock classes
    class ClientSession: pass


@dataclass
class APIConfig:
    """REST API configuration."""
    base_url: str
    auth_token: Optional[str] = None
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    headers: Dict[str, str] = None
    timeout: int = 30
    verify_ssl: bool = True
    auth_type: str = "bearer"  # bearer, basic, api_key, custom
    api_key_header: str = "X-API-Key"
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


class APIError(Exception):
    """REST API related error."""
    pass


class RestAPIClient:
    """
    Asynchronous REST API client for device monitoring.
    
    Supports various authentication methods and provides utilities
    for common API operations.
    """
    
    def __init__(self):
        """Initialize REST API client."""
        self.logger = logging.getLogger(__name__)
        self.config: Optional[APIConfig] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_configured = False
        
        if not AIOHTTP_AVAILABLE:
            self.logger.warning("aiohttp not available, REST API functionality disabled")
    
    def configure(self, base_url: str, auth_token: str = None, api_key: str = None,
                 username: str = None, password: str = None,
                 headers: Dict[str, str] = None, timeout: int = 30,
                 verify_ssl: bool = True, auth_type: str = "bearer",
                 api_key_header: str = "X-API-Key"):
        """
        Configure REST API client.
        
        Args:
            base_url: Base URL of the API
            auth_token: Bearer token for authentication
            api_key: API key for authentication
            username: Username for basic authentication
            password: Password for basic authentication
            headers: Additional HTTP headers
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            auth_type: Authentication type (bearer, basic, api_key, custom)
            api_key_header: Header name for API key
        """
        if not AIOHTTP_AVAILABLE:
            raise APIError("aiohttp not available")
        
        self.config = APIConfig(
            base_url=base_url.rstrip('/'),
            auth_token=auth_token,
            api_key=api_key,
            username=username,
            password=password,
            headers=headers or {},
            timeout=timeout,
            verify_ssl=verify_ssl,
            auth_type=auth_type,
            api_key_header=api_key_header
        )
        
        # Set authentication headers
        self._setup_auth_headers()
        
        self.is_configured = True
        self.logger.info(f"REST API client configured for {base_url}")
    
    def _setup_auth_headers(self):
        """Setup authentication headers based on configuration."""
        if not self.config:
            return
        
        if self.config.auth_type == "bearer" and self.config.auth_token:
            self.config.headers['Authorization'] = f"Bearer {self.config.auth_token}"
        
        elif self.config.auth_type == "api_key" and self.config.api_key:
            self.config.headers[self.config.api_key_header] = self.config.api_key
        
        elif self.config.auth_type == "basic" and self.config.username and self.config.password:
            import base64
            credentials = base64.b64encode(f"{self.config.username}:{self.config.password}".encode()).decode()
            self.config.headers['Authorization'] = f"Basic {credentials}"
        
        # Set default content type
        if 'Content-Type' not in self.config.headers:
            self.config.headers['Content-Type'] = 'application/json'
        
        # Set user agent
        if 'User-Agent' not in self.config.headers:
            self.config.headers['User-Agent'] = 'NetworkMonitoringAgent/1.0'
    
    async def start_session(self):
        """Start HTTP session."""
        if not self.is_configured:
            raise APIError("REST API client not configured")
        
        if self.session and not self.session.closed:
            return
        
        # Create SSL context
        ssl_context = None if self.config.verify_ssl else False
        
        # Create timeout
        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        
        # Create session
        self.session = aiohttp.ClientSession(
            headers=self.config.headers,
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
    
    async def request(self, method: str, endpoint: str, 
                     params: Dict[str, Any] = None,
                     data: Dict[str, Any] = None,
                     json_data: Dict[str, Any] = None,
                     headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Make HTTP request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint (relative to base_url)
            params: Query parameters
            data: Form data
            json_data: JSON data
            headers: Additional headers
            
        Returns:
            Dict[str, Any]: Response data
            
        Raises:
            APIError: If request fails
        """
        await self.start_session()
        
        try:
            url = urljoin(self.config.base_url, endpoint.lstrip('/'))
            
            # Merge headers
            request_headers = self.config.headers.copy()
            if headers:
                request_headers.update(headers)
            
            # Make request
            async with self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                data=data,
                json=json_data,
                headers=request_headers
            ) as response:
                
                # Check status code
                if response.status >= 400:
                    error_text = await response.text()
                    raise APIError(f"HTTP {response.status}: {error_text}")
                
                # Parse response
                content_type = response.headers.get('Content-Type', '')
                
                if 'application/json' in content_type:
                    return await response.json()
                else:
                    text_content = await response.text()
                    return {'content': text_content, 'content_type': content_type}
                
        except aiohttp.ClientError as e:
            self.logger.error(f"HTTP request failed: {e}")
            raise APIError(f"Request failed: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed: {e}")
            raise APIError(f"JSON parsing failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in request: {e}")
            raise APIError(f"Unexpected error: {e}")
    
    async def get(self, endpoint: str, params: Dict[str, Any] = None,
                 headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Perform GET request.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Dict[str, Any]: Response data
        """
        return await self.request('GET', endpoint, params=params, headers=headers)
    
    async def post(self, endpoint: str, data: Dict[str, Any] = None,
                  json_data: Dict[str, Any] = None,
                  headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Perform POST request.
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            headers: Additional headers
            
        Returns:
            Dict[str, Any]: Response data
        """
        return await self.request('POST', endpoint, data=data, json_data=json_data, headers=headers)
    
    async def put(self, endpoint: str, data: Dict[str, Any] = None,
                 json_data: Dict[str, Any] = None,
                 headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Perform PUT request.
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            headers: Additional headers
            
        Returns:
            Dict[str, Any]: Response data
        """
        return await self.request('PUT', endpoint, data=data, json_data=json_data, headers=headers)
    
    async def patch(self, endpoint: str, data: Dict[str, Any] = None,
                   json_data: Dict[str, Any] = None,
                   headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Perform PATCH request.
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            headers: Additional headers
            
        Returns:
            Dict[str, Any]: Response data
        """
        return await self.request('PATCH', endpoint, data=data, json_data=json_data, headers=headers)
    
    async def delete(self, endpoint: str, params: Dict[str, Any] = None,
                    headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Perform DELETE request.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Dict[str, Any]: Response data
        """
        return await self.request('DELETE', endpoint, params=params, headers=headers)
    
    async def paginated_get(self, endpoint: str, page_param: str = 'page',
                           size_param: str = 'size', max_pages: int = 100) -> List[Dict[str, Any]]:
        """
        Perform paginated GET request.
        
        Args:
            endpoint: API endpoint
            page_param: Page parameter name
            size_param: Page size parameter name
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List[Dict[str, Any]]: All paginated data
        """
        all_data = []
        page = 1
        
        while page <= max_pages:
            params = {page_param: page, size_param: 100}
            
            try:
                response = await self.get(endpoint, params=params)
                
                # Extract data based on common response formats
                if 'data' in response:
                    page_data = response['data']
                elif 'items' in response:
                    page_data = response['items']
                elif 'results' in response:
                    page_data = response['results']
                elif isinstance(response, list):
                    page_data = response
                else:
                    page_data = [response]
                
                if not page_data:
                    break
                
                all_data.extend(page_data)
                
                # Check if there are more pages
                if 'has_more' in response and not response['has_more']:
                    break
                elif 'total_pages' in response and page >= response['total_pages']:
                    break
                elif len(page_data) < 100:  # Assuming page size of 100
                    break
                
                page += 1
                
            except APIError:
                break
        
        return all_data
    
    async def upload_file(self, endpoint: str, file_path: str,
                         field_name: str = 'file',
                         additional_data: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Upload file via multipart form data.
        
        Args:
            endpoint: API endpoint
            file_path: Path to file to upload
            field_name: Form field name for file
            additional_data: Additional form fields
            
        Returns:
            Dict[str, Any]: Response data
        """
        await self.start_session()
        
        try:
            url = urljoin(self.config.base_url, endpoint.lstrip('/'))
            
            # Create form data
            data = aiohttp.FormData()
            
            # Add file
            with open(file_path, 'rb') as f:
                data.add_field(field_name, f, filename=file_path)
            
            # Add additional fields
            if additional_data:
                for key, value in additional_data.items():
                    data.add_field(key, value)
            
            # Remove Content-Type header to let aiohttp set it for multipart
            headers = self.config.headers.copy()
            headers.pop('Content-Type', None)
            
            async with self.session.post(url, data=data, headers=headers) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise APIError(f"HTTP {response.status}: {error_text}")
                
                return await response.json()
                
        except Exception as e:
            self.logger.error(f"File upload failed: {e}")
            raise APIError(f"File upload failed: {e}")
    
    async def stream_get(self, endpoint: str, chunk_size: int = 8192) -> bytes:
        """
        Stream GET request for large responses.
        
        Args:
            endpoint: API endpoint
            chunk_size: Chunk size for streaming
            
        Returns:
            bytes: Response content
        """
        await self.start_session()
        
        try:
            url = urljoin(self.config.base_url, endpoint.lstrip('/'))
            
            async with self.session.get(url) as response:
                if response.status >= 400:
                    error_text = await response.text()
                    raise APIError(f"HTTP {response.status}: {error_text}")
                
                content = b''
                async for chunk in response.content.iter_chunked(chunk_size):
                    content += chunk
                
                return content
                
        except Exception as e:
            self.logger.error(f"Stream GET failed: {e}")
            raise APIError(f"Stream GET failed: {e}")
    
    async def health_check(self, endpoint: str = '/health') -> bool:
        """
        Perform API health check.
        
        Args:
            endpoint: Health check endpoint
            
        Returns:
            bool: True if API is healthy
        """
        try:
            response = await self.get(endpoint)
            return response.get('status') == 'ok' or response.get('healthy') is True
        except Exception:
            return False
    
    async def get_api_info(self, endpoint: str = '/info') -> Dict[str, Any]:
        """
        Get API information.
        
        Args:
            endpoint: Info endpoint
            
        Returns:
            Dict[str, Any]: API information
        """
        try:
            return await self.get(endpoint)
        except Exception as e:
            return {'error': str(e)}
    
    # Device-specific API methods
    
    async def get_cisco_device_info(self, device_ip: str) -> Dict[str, Any]:
        """
        Get device information from Cisco DNA Center API.
        
        Args:
            device_ip: Device IP address
            
        Returns:
            Dict[str, Any]: Device information
        """
        try:
            # Get device by IP
            devices = await self.get('/dna/intent/api/v1/network-device', 
                                   params={'managementIpAddress': device_ip})
            
            if devices.get('response'):
                device = devices['response'][0]
                device_id = device['id']
                
                # Get detailed device info
                detail = await self.get(f'/dna/intent/api/v1/network-device/{device_id}')
                
                # Get device health
                health = await self.get(f'/dna/intent/api/v1/device-health', 
                                      params={'deviceId': device_id})
                
                return {
                    'device_info': detail.get('response', {}),
                    'health_info': health.get('response', {})
                }
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Cisco API request failed: {e}")
            return {'error': str(e)}
    
    async def get_meraki_device_info(self, network_id: str) -> Dict[str, Any]:
        """
        Get device information from Cisco Meraki API.
        
        Args:
            network_id: Meraki network ID
            
        Returns:
            Dict[str, Any]: Device information
        """
        try:
            # Get network devices
            devices = await self.get(f'/api/v1/networks/{network_id}/devices')
            
            # Get device statuses
            statuses = await self.get(f'/api/v1/networks/{network_id}/devices/statuses')
            
            return {
                'devices': devices,
                'statuses': statuses
            }
            
        except Exception as e:
            self.logger.error(f"Meraki API request failed: {e}")
            return {'error': str(e)}
    
    async def get_ubiquiti_device_info(self, site: str = 'default') -> Dict[str, Any]:
        """
        Get device information from Ubiquiti UniFi API.
        
        Args:
            site: UniFi site name
            
        Returns:
            Dict[str, Any]: Device information
        """
        try:
            # Login first (if not using token auth)
            if self.config.username and self.config.password:
                await self.post('/api/login', json_data={
                    'username': self.config.username,
                    'password': self.config.password
                })
            
            # Get device status
            devices = await self.get(f'/api/s/{site}/stat/device')
            
            # Get client information
            clients = await self.get(f'/api/s/{site}/stat/sta')
            
            return {
                'devices': devices.get('data', []),
                'clients': clients.get('data', [])
            }
            
        except Exception as e:
            self.logger.error(f"UniFi API request failed: {e}")
            return {'error': str(e)}
    
    async def get_palo_alto_device_info(self) -> Dict[str, Any]:
        """
        Get device information from Palo Alto Networks API.
        
        Returns:
            Dict[str, Any]: Device information
        """
        try:
            # Get system info
            system_info = await self.get('/api/', params={
                'type': 'op',
                'cmd': '<show><system><info></info></system></show>'
            })
            
            # Get interface info
            interface_info = await self.get('/api/', params={
                'type': 'op',
                'cmd': '<show><interface>all</interface></show>'
            })
            
            return {
                'system_info': system_info,
                'interface_info': interface_info
            }
            
        except Exception as e:
            self.logger.error(f"Palo Alto API request failed: {e}")
            return {'error': str(e)}
    
    async def test_connection(self) -> bool:
        """
        Test API connection.
        
        Returns:
            bool: True if connection is working
        """
        try:
            # Try health check first
            if await self.health_check():
                return True
            
            # Fallback to basic GET request
            await self.get('/')
            return True
        except Exception:
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get configuration information."""
        if not self.config:
            return {'configured': False}
        
        return {
            'configured': self.is_configured,
            'base_url': self.config.base_url,
            'auth_type': self.config.auth_type,
            'has_auth_token': bool(self.config.auth_token),
            'has_api_key': bool(self.config.api_key),
            'username': self.config.username,
            'has_password': bool(self.config.password),
            'timeout': self.config.timeout,
            'verify_ssl': self.config.verify_ssl,
            'api_key_header': self.config.api_key_header
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()