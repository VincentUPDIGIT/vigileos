"""
Authentication and authorization manager for multi-client support.
"""

import json
import time
import secrets
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from utils.platform_utils import PlatformPaths
from utils.encryption import EncryptionManager


class AuthMethod(Enum):
    """Authentication method enumeration."""
    JWT = "jwt"
    OAUTH2 = "oauth2"
    MTLS = "mtls"
    API_KEY = "api_key"


class TokenType(Enum):
    """Token type enumeration."""
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"


@dataclass
class AuthToken:
    """Authentication token data structure."""
    token: str
    token_type: TokenType
    client_id: str
    expires_at: datetime
    permissions: List[str]
    metadata: Dict[str, Any]
    
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if the token is valid (not expired)."""
        return not self.is_expired()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['expires_at'] = self.expires_at.isoformat()
        data['token_type'] = self.token_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuthToken':
        """Create from dictionary."""
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        data['token_type'] = TokenType(data['token_type'])
        return cls(**data)


@dataclass
class ClientInfo:
    """Client information data structure."""
    client_id: str
    client_name: str
    auth_method: AuthMethod
    permissions: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['auth_method'] = self.auth_method.value
        data['created_at'] = self.created_at.isoformat()
        data['last_login'] = self.last_login.isoformat() if self.last_login else None
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClientInfo':
        """Create from dictionary."""
        data['auth_method'] = AuthMethod(data['auth_method'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data['last_login']:
            data['last_login'] = datetime.fromisoformat(data['last_login'])
        return cls(**data)


class AuthenticationError(Exception):
    """Authentication-related error."""
    pass


class AuthorizationError(Exception):
    """Authorization-related error."""
    pass


class AuthManager:
    """
    Authentication and authorization manager.
    
    Supports multiple authentication methods:
    - JWT tokens
    - OAuth2
    - Mutual TLS (mTLS)
    - API keys
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the authentication manager.
        
        Args:
            config: Authentication configuration
        """
        self.config = config or {}
        self.encryption_manager = EncryptionManager()
        
        # Configuration
        self.jwt_secret = self.config.get('jwt_secret', self._generate_jwt_secret())
        self.jwt_algorithm = self.config.get('jwt_algorithm', 'HS256')
        self.token_expiry = self.config.get('token_expiry', 3600)  # 1 hour
        self.refresh_token_expiry = self.config.get('refresh_token_expiry', 86400 * 7)  # 7 days
        
        # Storage paths
        self.config_dir = PlatformPaths.get_config_dir()
        self.clients_db_path = self.config_dir / 'clients.json'
        self.tokens_db_path = self.config_dir / 'tokens.json'
        
        # Ensure directories exist
        PlatformPaths.ensure_directory_exists(self.config_dir, mode=0o700)
        
        # Load existing data
        self.clients: Dict[str, ClientInfo] = self._load_clients()
        self.active_tokens: Dict[str, AuthToken] = self._load_tokens()
        
        # Default permissions
        self.default_permissions = [
            'metrics:read', 'metrics:write',
            'devices:read', 'tunnels:read'
        ]
        
        self.admin_permissions = [
            'metrics:read', 'metrics:write', 'metrics:delete',
            'devices:read', 'devices:write', 'devices:delete',
            'tunnels:read', 'tunnels:write', 'tunnels:delete',
            'clients:read', 'clients:write', 'clients:delete',
            'system:admin'
        ]
    
    def _generate_jwt_secret(self) -> str:
        """Generate a secure JWT secret."""
        return secrets.token_urlsafe(32)
    
    def _load_clients(self) -> Dict[str, ClientInfo]:
        """Load clients from encrypted storage."""
        try:
            if self.clients_db_path.exists():
                with open(self.clients_db_path, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = self.encryption_manager.decrypt(encrypted_data)
                clients_data = json.loads(decrypted_data)
                
                clients = {}
                for client_id, client_data in clients_data.items():
                    clients[client_id] = ClientInfo.from_dict(client_data)
                
                return clients
        except Exception as e:
            print(f"Warning: Failed to load clients database: {e}")
        
        return {}
    
    def _save_clients(self):
        """Save clients to encrypted storage."""
        try:
            clients_data = {}
            for client_id, client_info in self.clients.items():
                clients_data[client_id] = client_info.to_dict()
            
            json_data = json.dumps(clients_data, indent=2)
            encrypted_data = self.encryption_manager.encrypt(json_data.encode())
            
            with open(self.clients_db_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions
            self.clients_db_path.chmod(0o600)
        except Exception as e:
            raise AuthenticationError(f"Failed to save clients database: {e}")
    
    def _load_tokens(self) -> Dict[str, AuthToken]:
        """Load active tokens from storage."""
        try:
            if self.tokens_db_path.exists():
                with open(self.tokens_db_path, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = self.encryption_manager.decrypt(encrypted_data)
                tokens_data = json.loads(decrypted_data)
                
                tokens = {}
                for token_id, token_data in tokens_data.items():
                    token = AuthToken.from_dict(token_data)
                    if token.is_valid():  # Only load valid tokens
                        tokens[token_id] = token
                
                return tokens
        except Exception as e:
            print(f"Warning: Failed to load tokens database: {e}")
        
        return {}
    
    def _save_tokens(self):
        """Save active tokens to encrypted storage."""
        try:
            # Clean expired tokens before saving
            self._cleanup_expired_tokens()
            
            tokens_data = {}
            for token_id, token in self.active_tokens.items():
                tokens_data[token_id] = token.to_dict()
            
            json_data = json.dumps(tokens_data, indent=2)
            encrypted_data = self.encryption_manager.encrypt(json_data.encode())
            
            with open(self.tokens_db_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions
            self.tokens_db_path.chmod(0o600)
        except Exception as e:
            raise AuthenticationError(f"Failed to save tokens database: {e}")
    
    def _cleanup_expired_tokens(self):
        """Remove expired tokens from memory."""
        expired_tokens = [
            token_id for token_id, token in self.active_tokens.items()
            if token.is_expired()
        ]
        
        for token_id in expired_tokens:
            del self.active_tokens[token_id]
    
    def create_client(self, client_id: str, client_name: str, 
                     auth_method: AuthMethod = AuthMethod.JWT,
                     permissions: List[str] = None) -> ClientInfo:
        """
        Create a new client.
        
        Args:
            client_id: Unique client identifier
            client_name: Human-readable client name
            auth_method: Authentication method to use
            permissions: List of permissions (uses default if None)
            
        Returns:
            ClientInfo: Created client information
            
        Raises:
            AuthenticationError: If client already exists
        """
        if client_id in self.clients:
            raise AuthenticationError(f"Client {client_id} already exists")
        
        if permissions is None:
            permissions = self.default_permissions.copy()
        
        client_info = ClientInfo(
            client_id=client_id,
            client_name=client_name,
            auth_method=auth_method,
            permissions=permissions,
            created_at=datetime.utcnow()
        )
        
        self.clients[client_id] = client_info
        self._save_clients()
        
        return client_info
    
    def get_client(self, client_id: str) -> Optional[ClientInfo]:
        """Get client information."""
        return self.clients.get(client_id)
    
    def list_clients(self) -> List[ClientInfo]:
        """List all clients."""
        return list(self.clients.values())
    
    def update_client(self, client_id: str, **updates) -> bool:
        """Update client information."""
        if client_id not in self.clients:
            return False
        
        client = self.clients[client_id]
        
        for key, value in updates.items():
            if hasattr(client, key):
                setattr(client, key, value)
        
        self._save_clients()
        return True
    
    def delete_client(self, client_id: str) -> bool:
        """Delete a client."""
        if client_id not in self.clients:
            return False
        
        # Revoke all tokens for this client
        self.revoke_client_tokens(client_id)
        
        del self.clients[client_id]
        self._save_clients()
        
        return True
    
    def authenticate_client(self, client_id: str, credentials: Dict[str, Any]) -> AuthToken:
        """
        Authenticate a client and return an access token.
        
        Args:
            client_id: Client identifier
            credentials: Authentication credentials
            
        Returns:
            AuthToken: Access token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        client = self.get_client(client_id)
        if not client or not client.is_active:
            raise AuthenticationError(f"Client {client_id} not found or inactive")
        
        # Authenticate based on method
        if client.auth_method == AuthMethod.JWT:
            return self._authenticate_jwt(client, credentials)
        elif client.auth_method == AuthMethod.API_KEY:
            return self._authenticate_api_key(client, credentials)
        elif client.auth_method == AuthMethod.OAUTH2:
            return self._authenticate_oauth2(client, credentials)
        elif client.auth_method == AuthMethod.MTLS:
            return self._authenticate_mtls(client, credentials)
        else:
            raise AuthenticationError(f"Unsupported auth method: {client.auth_method}")
    
    def _authenticate_jwt(self, client: ClientInfo, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate using JWT."""
        password = credentials.get('password')
        if not password:
            raise AuthenticationError("Password required for JWT authentication")
        
        # In a real implementation, you would verify the password against a hash
        # For this example, we'll use a simple check
        expected_password = credentials.get('expected_password', 'default_password')
        if password != expected_password:
            raise AuthenticationError("Invalid password")
        
        return self._create_access_token(client)
    
    def _authenticate_api_key(self, client: ClientInfo, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate using API key."""
        api_key = credentials.get('api_key')
        if not api_key:
            raise AuthenticationError("API key required")
        
        # Verify API key (in real implementation, this would be hashed and stored)
        expected_api_key = client.metadata.get('api_key')
        if not expected_api_key or api_key != expected_api_key:
            raise AuthenticationError("Invalid API key")
        
        return self._create_access_token(client)
    
    def _authenticate_oauth2(self, client: ClientInfo, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate using OAuth2."""
        # Simplified OAuth2 implementation
        access_token = credentials.get('access_token')
        if not access_token:
            raise AuthenticationError("OAuth2 access token required")
        
        # In real implementation, verify token with OAuth2 provider
        # For now, just create our internal token
        return self._create_access_token(client)
    
    def _authenticate_mtls(self, client: ClientInfo, credentials: Dict[str, Any]) -> AuthToken:
        """Authenticate using mutual TLS."""
        client_cert = credentials.get('client_cert')
        if not client_cert:
            raise AuthenticationError("Client certificate required for mTLS")
        
        # In real implementation, verify certificate against stored cert/CA
        # For now, just create token
        return self._create_access_token(client)
    
    def _create_access_token(self, client: ClientInfo) -> AuthToken:
        """Create an access token for a client."""
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=self.token_expiry)
        
        # JWT payload
        payload = {
            'client_id': client.client_id,
            'permissions': client.permissions,
            'iat': int(now.timestamp()),
            'exp': int(expires_at.timestamp()),
            'type': TokenType.ACCESS.value
        }
        
        # Create JWT token
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        
        # Create AuthToken object
        auth_token = AuthToken(
            token=token,
            token_type=TokenType.ACCESS,
            client_id=client.client_id,
            expires_at=expires_at,
            permissions=client.permissions,
            metadata={'created_at': now.isoformat()}
        )
        
        # Store token
        token_id = hashlib.sha256(token.encode()).hexdigest()[:16]
        self.active_tokens[token_id] = auth_token
        self._save_tokens()
        
        # Update client last login
        client.last_login = now
        self._save_clients()
        
        return auth_token
    
    def validate_token(self, token: str) -> bool:
        """
        Validate a token.
        
        Args:
            token: Token to validate
            
        Returns:
            bool: True if token is valid
        """
        try:
            auth_token = self.get_token_info(token)
            return auth_token is not None and auth_token.is_valid()
        except Exception:
            return False
    
    def get_token_info(self, token: str) -> Optional[AuthToken]:
        """
        Get token information.
        
        Args:
            token: Token to get info for
            
        Returns:
            AuthToken: Token information or None if invalid
        """
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Find token in active tokens
            token_id = hashlib.sha256(token.encode()).hexdigest()[:16]
            auth_token = self.active_tokens.get(token_id)
            
            if auth_token and auth_token.is_valid():
                return auth_token
            
        except jwt.InvalidTokenError:
            pass
        
        return None
    
    def get_client_permissions(self, client_id: str) -> List[str]:
        """Get permissions for a client."""
        client = self.get_client(client_id)
        return client.permissions if client else []
    
    def check_permission(self, token: str, permission: str) -> bool:
        """
        Check if a token has a specific permission.
        
        Args:
            token: Token to check
            permission: Permission to check for
            
        Returns:
            bool: True if token has permission
        """
        auth_token = self.get_token_info(token)
        if not auth_token:
            return False
        
        return permission in auth_token.permissions
    
    def refresh_token(self, refresh_token: str) -> AuthToken:
        """
        Refresh an access token.
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            AuthToken: New access token
            
        Raises:
            AuthenticationError: If refresh token is invalid
        """
        # In a full implementation, you would have separate refresh tokens
        # For simplicity, we'll just create a new token for the same client
        
        try:
            payload = jwt.decode(refresh_token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            client_id = payload.get('client_id')
            
            if not client_id:
                raise AuthenticationError("Invalid refresh token")
            
            client = self.get_client(client_id)
            if not client:
                raise AuthenticationError("Client not found")
            
            return self._create_access_token(client)
            
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid refresh token")
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a specific token."""
        token_id = hashlib.sha256(token.encode()).hexdigest()[:16]
        
        if token_id in self.active_tokens:
            del self.active_tokens[token_id]
            self._save_tokens()
            return True
        
        return False
    
    def revoke_client_tokens(self, client_id: str) -> int:
        """Revoke all tokens for a client."""
        revoked_count = 0
        
        tokens_to_revoke = [
            token_id for token_id, token in self.active_tokens.items()
            if token.client_id == client_id
        ]
        
        for token_id in tokens_to_revoke:
            del self.active_tokens[token_id]
            revoked_count += 1
        
        if revoked_count > 0:
            self._save_tokens()
        
        return revoked_count
    
    def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens and return count of removed tokens."""
        initial_count = len(self.active_tokens)
        self._cleanup_expired_tokens()
        removed_count = initial_count - len(self.active_tokens)
        
        if removed_count > 0:
            self._save_tokens()
        
        return removed_count
    
    def get_auth_stats(self) -> Dict[str, Any]:
        """Get authentication statistics."""
        active_tokens_count = len(self.active_tokens)
        clients_count = len(self.clients)
        active_clients_count = len([c for c in self.clients.values() if c.is_active])
        
        # Count tokens by client
        tokens_by_client = {}
        for token in self.active_tokens.values():
            client_id = token.client_id
            tokens_by_client[client_id] = tokens_by_client.get(client_id, 0) + 1
        
        return {
            'total_clients': clients_count,
            'active_clients': active_clients_count,
            'active_tokens': active_tokens_count,
            'tokens_by_client': tokens_by_client,
            'auth_methods': [client.auth_method.value for client in self.clients.values()]
        }