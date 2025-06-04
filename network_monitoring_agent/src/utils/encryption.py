"""
Encryption utilities for secure data storage and transmission.
"""

import os
import secrets
import hashlib
from pathlib import Path
from typing import Union, Optional, Dict, Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

from utils.platform_utils import PlatformPaths


class EncryptionError(Exception):
    """Encryption-related error."""
    pass


class EncryptionManager:
    """
    Encryption manager for secure data handling.
    
    Provides symmetric and asymmetric encryption capabilities
    with secure key management.
    """
    
    def __init__(self, key_file: Optional[Path] = None):
        """
        Initialize the encryption manager.
        
        Args:
            key_file: Path to the master key file (auto-generated if None)
        """
        self.backend = default_backend()
        
        # Encryption settings
        self.key_length = 32  # 256 bits
        self.iv_length = 16   # 128 bits
        self.salt_length = 16 # 128 bits
        self.tag_length = 16  # 128 bits for GCM
        
        # Key storage
        if key_file is None:
            config_dir = PlatformPaths.get_config_dir()
            PlatformPaths.ensure_directory_exists(config_dir, mode=0o700)
            key_file = config_dir / '.master_key'
        
        self.key_file = Path(key_file)
        self.master_key = self._load_or_generate_master_key()
    
    def _load_or_generate_master_key(self) -> bytes:
        """Load existing master key or generate a new one."""
        try:
            if self.key_file.exists():
                with open(self.key_file, 'rb') as f:
                    return f.read()
            else:
                # Generate new master key
                master_key = secrets.token_bytes(self.key_length)
                
                # Save with secure permissions
                with open(self.key_file, 'wb') as f:
                    f.write(master_key)
                
                # Set secure file permissions
                self.key_file.chmod(0o600)
                
                return master_key
        except Exception as e:
            raise EncryptionError(f"Failed to load/generate master key: {e}")
    
    def _derive_key(self, password: Union[str, bytes], salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if isinstance(password, str):
            password = password.encode('utf-8')
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.key_length,
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
            backend=self.backend
        )
        
        return kdf.derive(password)
    
    def _derive_key_scrypt(self, password: Union[str, bytes], salt: bytes) -> bytes:
        """Derive encryption key from password using Scrypt (more secure but slower)."""
        if isinstance(password, str):
            password = password.encode('utf-8')
        
        kdf = Scrypt(
            algorithm=hashes.SHA256(),
            length=self.key_length,
            salt=salt,
            n=2**14,  # CPU/memory cost parameter
            r=8,      # Block size parameter
            p=1,      # Parallelization parameter
            backend=self.backend
        )
        
        return kdf.derive(password)
    
    def encrypt(self, data: Union[str, bytes], password: Optional[str] = None) -> bytes:
        """
        Encrypt data using AES-GCM.
        
        Args:
            data: Data to encrypt
            password: Optional password (uses master key if None)
            
        Returns:
            bytes: Encrypted data with salt, IV, and tag
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            # Generate random salt and IV
            salt = secrets.token_bytes(self.salt_length)
            iv = secrets.token_bytes(self.iv_length)
            
            # Derive encryption key
            if password:
                key = self._derive_key(password, salt)
            else:
                key = self.master_key
                salt = b''  # No salt needed for master key
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=self.backend
            )
            
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(data) + encryptor.finalize()
            
            # Combine salt, IV, tag, and ciphertext
            encrypted_data = salt + iv + encryptor.tag + ciphertext
            
            return encrypted_data
            
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_data: bytes, password: Optional[str] = None) -> bytes:
        """
        Decrypt data using AES-GCM.
        
        Args:
            encrypted_data: Encrypted data with salt, IV, and tag
            password: Optional password (uses master key if None)
            
        Returns:
            bytes: Decrypted data
            
        Raises:
            EncryptionError: If decryption fails
        """
        try:
            if password:
                # Extract salt, IV, tag, and ciphertext
                salt = encrypted_data[:self.salt_length]
                iv = encrypted_data[self.salt_length:self.salt_length + self.iv_length]
                tag = encrypted_data[self.salt_length + self.iv_length:self.salt_length + self.iv_length + self.tag_length]
                ciphertext = encrypted_data[self.salt_length + self.iv_length + self.tag_length:]
                
                # Derive decryption key
                key = self._derive_key(password, salt)
            else:
                # Extract IV, tag, and ciphertext (no salt for master key)
                iv = encrypted_data[:self.iv_length]
                tag = encrypted_data[self.iv_length:self.iv_length + self.tag_length]
                ciphertext = encrypted_data[self.iv_length + self.tag_length:]
                
                key = self.master_key
            
            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=self.backend
            )
            
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext
            
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")
    
    def encrypt_file(self, file_path: Path, password: Optional[str] = None) -> Path:
        """
        Encrypt a file in place.
        
        Args:
            file_path: Path to file to encrypt
            password: Optional password
            
        Returns:
            Path: Path to encrypted file (.enc extension added)
            
        Raises:
            EncryptionError: If file encryption fails
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            encrypted_data = self.encrypt(data, password)
            
            encrypted_file_path = file_path.with_suffix(file_path.suffix + '.enc')
            with open(encrypted_file_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions
            encrypted_file_path.chmod(0o600)
            
            return encrypted_file_path
            
        except Exception as e:
            raise EncryptionError(f"File encryption failed: {e}")
    
    def decrypt_file(self, encrypted_file_path: Path, password: Optional[str] = None) -> Path:
        """
        Decrypt a file.
        
        Args:
            encrypted_file_path: Path to encrypted file
            password: Optional password
            
        Returns:
            Path: Path to decrypted file
            
        Raises:
            EncryptionError: If file decryption fails
        """
        try:
            with open(encrypted_file_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self.decrypt(encrypted_data, password)
            
            # Remove .enc extension
            decrypted_file_path = encrypted_file_path
            if encrypted_file_path.suffix == '.enc':
                decrypted_file_path = encrypted_file_path.with_suffix('')
            else:
                decrypted_file_path = encrypted_file_path.with_suffix('.dec')
            
            with open(decrypted_file_path, 'wb') as f:
                f.write(decrypted_data)
            
            return decrypted_file_path
            
        except Exception as e:
            raise EncryptionError(f"File decryption failed: {e}")
    
    def generate_rsa_keypair(self, key_size: int = 2048) -> tuple[bytes, bytes]:
        """
        Generate RSA key pair.
        
        Args:
            key_size: RSA key size in bits
            
        Returns:
            tuple: (private_key_pem, public_key_pem)
        """
        try:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=self.backend
            )
            
            public_key = private_key.public_key()
            
            # Serialize keys to PEM format
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            return private_pem, public_pem
            
        except Exception as e:
            raise EncryptionError(f"RSA key generation failed: {e}")
    
    def rsa_encrypt(self, data: Union[str, bytes], public_key_pem: bytes) -> bytes:
        """
        Encrypt data using RSA public key.
        
        Args:
            data: Data to encrypt
            public_key_pem: RSA public key in PEM format
            
        Returns:
            bytes: Encrypted data
        """
        try:
            if isinstance(data, str):
                data = data.encode('utf-8')
            
            public_key = serialization.load_pem_public_key(
                public_key_pem,
                backend=self.backend
            )
            
            encrypted_data = public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return encrypted_data
            
        except Exception as e:
            raise EncryptionError(f"RSA encryption failed: {e}")
    
    def rsa_decrypt(self, encrypted_data: bytes, private_key_pem: bytes) -> bytes:
        """
        Decrypt data using RSA private key.
        
        Args:
            encrypted_data: Encrypted data
            private_key_pem: RSA private key in PEM format
            
        Returns:
            bytes: Decrypted data
        """
        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=None,
                backend=self.backend
            )
            
            decrypted_data = private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return decrypted_data
            
        except Exception as e:
            raise EncryptionError(f"RSA decryption failed: {e}")
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
        """
        Hash a password using PBKDF2.
        
        Args:
            password: Password to hash
            salt: Optional salt (generated if None)
            
        Returns:
            tuple: (hash, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(self.salt_length)
        
        password_hash = self._derive_key(password, salt)
        return password_hash, salt
    
    def verify_password(self, password: str, password_hash: bytes, salt: bytes) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            password: Password to verify
            password_hash: Stored password hash
            salt: Salt used for hashing
            
        Returns:
            bool: True if password is correct
        """
        try:
            computed_hash = self._derive_key(password, salt)
            return secrets.compare_digest(password_hash, computed_hash)
        except Exception:
            return False
    
    def generate_api_key(self, length: int = 32) -> str:
        """
        Generate a secure API key.
        
        Args:
            length: Length of the API key in bytes
            
        Returns:
            str: Base64-encoded API key
        """
        return secrets.token_urlsafe(length)
    
    def hash_data(self, data: Union[str, bytes], algorithm: str = 'sha256') -> str:
        """
        Hash data using specified algorithm.
        
        Args:
            data: Data to hash
            algorithm: Hash algorithm (sha256, sha512, etc.)
            
        Returns:
            str: Hexadecimal hash
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        hash_obj = hashlib.new(algorithm)
        hash_obj.update(data)
        return hash_obj.hexdigest()
    
    def secure_delete_file(self, file_path: Path, passes: int = 3) -> bool:
        """
        Securely delete a file by overwriting it multiple times.
        
        Args:
            file_path: Path to file to delete
            passes: Number of overwrite passes
            
        Returns:
            bool: True if file was securely deleted
        """
        try:
            if not file_path.exists():
                return True
            
            file_size = file_path.stat().st_size
            
            with open(file_path, 'r+b') as f:
                for _ in range(passes):
                    # Overwrite with random data
                    f.seek(0)
                    f.write(secrets.token_bytes(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            # Finally delete the file
            file_path.unlink()
            return True
            
        except Exception:
            return False
    
    def get_encryption_info(self) -> Dict[str, Any]:
        """Get encryption configuration information."""
        return {
            'key_length': self.key_length,
            'iv_length': self.iv_length,
            'salt_length': self.salt_length,
            'tag_length': self.tag_length,
            'key_file_exists': self.key_file.exists(),
            'algorithms': {
                'symmetric': 'AES-256-GCM',
                'asymmetric': 'RSA-2048',
                'kdf': 'PBKDF2-SHA256',
                'hash': 'SHA-256'
            }
        }