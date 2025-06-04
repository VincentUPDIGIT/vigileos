"""
SNMP client for network device monitoring.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

try:
    from pysnmp.hlapi.asyncio import *
    from pysnmp.proto.rfc1902 import Counter32, Counter64, Gauge32, Integer, OctetString
    from pysnmp.error import PySnmpError
    PYSNMP_AVAILABLE = True
except ImportError:
    PYSNMP_AVAILABLE = False
    # Mock classes for when pysnmp is not available
    class SnmpEngine: pass
    class CommunityData: pass
    class UdpTransportTarget: pass
    class ContextData: pass
    class ObjectType: pass
    class ObjectIdentity: pass
    class PySnmpError(Exception): pass


@dataclass
class SNMPConfig:
    """SNMP configuration parameters."""
    host: str
    port: int = 161
    community: str = "public"
    version: str = "2c"  # "1", "2c", "3"
    timeout: int = 5
    retries: int = 3
    
    # SNMPv3 specific
    username: Optional[str] = None
    auth_protocol: Optional[str] = None  # "MD5", "SHA"
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None  # "DES", "AES"
    priv_password: Optional[str] = None
    security_level: str = "noAuthNoPriv"  # "noAuthNoPriv", "authNoPriv", "authPriv"


class SNMPError(Exception):
    """SNMP-related error."""
    pass


class SNMPClient:
    """
    Asynchronous SNMP client for network device monitoring.
    
    Supports SNMPv1, SNMPv2c, and SNMPv3 with authentication and privacy.
    """
    
    def __init__(self):
        """Initialize SNMP client."""
        self.logger = logging.getLogger(__name__)
        self.config: Optional[SNMPConfig] = None
        self.engine = None
        self.is_connected = False
        
        if not PYSNMP_AVAILABLE:
            self.logger.warning("pysnmp not available, SNMP functionality disabled")
    
    async def connect(self, host: str, community: str = "public", version: str = "2c", 
                     port: int = 161, timeout: int = 5, retries: int = 3,
                     username: str = None, auth_protocol: str = None, 
                     auth_password: str = None, priv_protocol: str = None,
                     priv_password: str = None) -> bool:
        """
        Connect to SNMP device.
        
        Args:
            host: Target host IP or hostname
            community: SNMP community string (v1/v2c)
            version: SNMP version ("1", "2c", "3")
            port: SNMP port (default 161)
            timeout: Request timeout in seconds
            retries: Number of retries
            username: SNMPv3 username
            auth_protocol: SNMPv3 auth protocol ("MD5", "SHA")
            auth_password: SNMPv3 auth password
            priv_protocol: SNMPv3 privacy protocol ("DES", "AES")
            priv_password: SNMPv3 privacy password
            
        Returns:
            bool: True if connection successful
            
        Raises:
            SNMPError: If connection fails
        """
        if not PYSNMP_AVAILABLE:
            raise SNMPError("pysnmp not available")
        
        try:
            self.config = SNMPConfig(
                host=host,
                port=port,
                community=community,
                version=version,
                timeout=timeout,
                retries=retries,
                username=username,
                auth_protocol=auth_protocol,
                auth_password=auth_password,
                priv_protocol=priv_protocol,
                priv_password=priv_password
            )
            
            # Create SNMP engine
            self.engine = SnmpEngine()
            
            # Test connection with a simple get
            await self.get('1.3.6.1.2.1.1.1.0')  # sysDescr
            
            self.is_connected = True
            self.logger.info(f"Connected to SNMP device {host}:{port}")
            return True
            
        except Exception as e:
            self.logger.error(f"SNMP connection failed: {e}")
            raise SNMPError(f"Connection failed: {e}")
    
    async def disconnect(self):
        """Disconnect from SNMP device."""
        if self.engine:
            self.engine = None
        self.is_connected = False
        self.config = None
        self.logger.info("Disconnected from SNMP device")
    
    def _get_auth_data(self):
        """Get authentication data based on SNMP version."""
        if not self.config:
            raise SNMPError("Not connected")
        
        if self.config.version in ["1", "2c"]:
            return CommunityData(self.config.community, mpModel=0 if self.config.version == "1" else 1)
        elif self.config.version == "3":
            if not self.config.username:
                raise SNMPError("SNMPv3 requires username")
            
            # Determine security level and create auth data
            if self.config.auth_password and self.config.priv_password:
                # authPriv
                auth_protocol = usmHMACMD5AuthProtocol if self.config.auth_protocol == "MD5" else usmHMACSHAAuthProtocol
                priv_protocol = usmDESPrivProtocol if self.config.priv_protocol == "DES" else usmAesCfb128Protocol
                
                return UsmUserData(
                    self.config.username,
                    authKey=self.config.auth_password,
                    privKey=self.config.priv_password,
                    authProtocol=auth_protocol,
                    privProtocol=priv_protocol
                )
            elif self.config.auth_password:
                # authNoPriv
                auth_protocol = usmHMACMD5AuthProtocol if self.config.auth_protocol == "MD5" else usmHMACSHAAuthProtocol
                
                return UsmUserData(
                    self.config.username,
                    authKey=self.config.auth_password,
                    authProtocol=auth_protocol
                )
            else:
                # noAuthNoPriv
                return UsmUserData(self.config.username)
        else:
            raise SNMPError(f"Unsupported SNMP version: {self.config.version}")
    
    def _get_transport_target(self):
        """Get transport target."""
        if not self.config:
            raise SNMPError("Not connected")
        
        return UdpTransportTarget(
            (self.config.host, self.config.port),
            timeout=self.config.timeout,
            retries=self.config.retries
        )
    
    async def get(self, oid: str) -> Optional[str]:
        """
        Get single SNMP value.
        
        Args:
            oid: Object identifier (e.g., "1.3.6.1.2.1.1.1.0")
            
        Returns:
            str: SNMP value or None if not found
            
        Raises:
            SNMPError: If get operation fails
        """
        if not PYSNMP_AVAILABLE:
            raise SNMPError("pysnmp not available")
        
        if not self.is_connected:
            raise SNMPError("Not connected to SNMP device")
        
        try:
            auth_data = self._get_auth_data()
            transport_target = self._get_transport_target()
            
            iterator = getCmd(
                self.engine,
                auth_data,
                transport_target,
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            
            error_indication, error_status, error_index, var_binds = await iterator
            
            if error_indication:
                raise SNMPError(f"SNMP error indication: {error_indication}")
            
            if error_status:
                raise SNMPError(f"SNMP error status: {error_status.prettyPrint()} at {error_index}")
            
            for var_bind in var_binds:
                return str(var_bind[1])
            
            return None
            
        except PySnmpError as e:
            self.logger.error(f"SNMP get failed for OID {oid}: {e}")
            raise SNMPError(f"Get operation failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SNMP get: {e}")
            raise SNMPError(f"Unexpected error: {e}")
    
    async def get_bulk(self, oids: List[str]) -> Dict[str, Optional[str]]:
        """
        Get multiple SNMP values in a single request.
        
        Args:
            oids: List of object identifiers
            
        Returns:
            Dict[str, Optional[str]]: Mapping of OID to value
            
        Raises:
            SNMPError: If get operation fails
        """
        if not PYSNMP_AVAILABLE:
            raise SNMPError("pysnmp not available")
        
        if not self.is_connected:
            raise SNMPError("Not connected to SNMP device")
        
        try:
            auth_data = self._get_auth_data()
            transport_target = self._get_transport_target()
            
            object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]
            
            iterator = getCmd(
                self.engine,
                auth_data,
                transport_target,
                ContextData(),
                *object_types
            )
            
            error_indication, error_status, error_index, var_binds = await iterator
            
            if error_indication:
                raise SNMPError(f"SNMP error indication: {error_indication}")
            
            if error_status:
                raise SNMPError(f"SNMP error status: {error_status.prettyPrint()} at {error_index}")
            
            results = {}
            for i, var_bind in enumerate(var_binds):
                if i < len(oids):
                    results[oids[i]] = str(var_bind[1])
            
            return results
            
        except PySnmpError as e:
            self.logger.error(f"SNMP get_bulk failed: {e}")
            raise SNMPError(f"Get bulk operation failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SNMP get_bulk: {e}")
            raise SNMPError(f"Unexpected error: {e}")
    
    async def walk(self, oid: str) -> Dict[str, str]:
        """
        Walk SNMP tree starting from given OID.
        
        Args:
            oid: Starting object identifier
            
        Returns:
            Dict[str, str]: Mapping of full OID to value
            
        Raises:
            SNMPError: If walk operation fails
        """
        if not PYSNMP_AVAILABLE:
            raise SNMPError("pysnmp not available")
        
        if not self.is_connected:
            raise SNMPError("Not connected to SNMP device")
        
        try:
            auth_data = self._get_auth_data()
            transport_target = self._get_transport_target()
            
            results = {}
            
            async for (error_indication, error_status, error_index, var_binds) in nextCmd(
                self.engine,
                auth_data,
                transport_target,
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                if error_indication:
                    self.logger.error(f"SNMP walk error indication: {error_indication}")
                    break
                
                if error_status:
                    self.logger.error(f"SNMP walk error status: {error_status.prettyPrint()} at {error_index}")
                    break
                
                for var_bind in var_binds:
                    oid_str = str(var_bind[0])
                    value_str = str(var_bind[1])
                    results[oid_str] = value_str
            
            return results
            
        except PySnmpError as e:
            self.logger.error(f"SNMP walk failed for OID {oid}: {e}")
            raise SNMPError(f"Walk operation failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SNMP walk: {e}")
            raise SNMPError(f"Unexpected error: {e}")
    
    async def get_table(self, table_oid: str, columns: List[str] = None) -> List[Dict[str, str]]:
        """
        Get SNMP table data.
        
        Args:
            table_oid: Table OID (e.g., "1.3.6.1.2.1.2.2")
            columns: List of column OIDs to retrieve (None for all)
            
        Returns:
            List[Dict[str, str]]: List of table rows
            
        Raises:
            SNMPError: If table operation fails
        """
        if not PYSNMP_AVAILABLE:
            raise SNMPError("pysnmp not available")
        
        try:
            # Walk the table
            table_data = await self.walk(table_oid)
            
            # Parse table structure
            rows = {}
            for full_oid, value in table_data.items():
                # Extract column and index from OID
                # Format: table_oid.column.index
                oid_parts = full_oid.split('.')
                table_parts = table_oid.split('.')
                
                if len(oid_parts) > len(table_parts) + 1:
                    column = oid_parts[len(table_parts)]
                    index = '.'.join(oid_parts[len(table_parts) + 1:])
                    
                    if columns is None or column in columns:
                        if index not in rows:
                            rows[index] = {'_index': index}
                        rows[index][column] = value
            
            return list(rows.values())
            
        except Exception as e:
            self.logger.error(f"SNMP get_table failed for {table_oid}: {e}")
            raise SNMPError(f"Table operation failed: {e}")
    
    async def set(self, oid: str, value: Union[str, int], value_type: str = "OctetString") -> bool:
        """
        Set SNMP value.
        
        Args:
            oid: Object identifier
            value: Value to set
            value_type: SNMP value type ("OctetString", "Integer", "Counter32", etc.)
            
        Returns:
            bool: True if set successful
            
        Raises:
            SNMPError: If set operation fails
        """
        if not PYSNMP_AVAILABLE:
            raise SNMPError("pysnmp not available")
        
        if not self.is_connected:
            raise SNMPError("Not connected to SNMP device")
        
        try:
            auth_data = self._get_auth_data()
            transport_target = self._get_transport_target()
            
            # Convert value to appropriate SNMP type
            if value_type == "Integer":
                snmp_value = Integer(value)
            elif value_type == "Counter32":
                snmp_value = Counter32(value)
            elif value_type == "Counter64":
                snmp_value = Counter64(value)
            elif value_type == "Gauge32":
                snmp_value = Gauge32(value)
            else:  # Default to OctetString
                snmp_value = OctetString(str(value))
            
            iterator = setCmd(
                self.engine,
                auth_data,
                transport_target,
                ContextData(),
                ObjectType(ObjectIdentity(oid), snmp_value)
            )
            
            error_indication, error_status, error_index, var_binds = await iterator
            
            if error_indication:
                raise SNMPError(f"SNMP error indication: {error_indication}")
            
            if error_status:
                raise SNMPError(f"SNMP error status: {error_status.prettyPrint()} at {error_index}")
            
            self.logger.info(f"SNMP set successful for OID {oid}")
            return True
            
        except PySnmpError as e:
            self.logger.error(f"SNMP set failed for OID {oid}: {e}")
            raise SNMPError(f"Set operation failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in SNMP set: {e}")
            raise SNMPError(f"Unexpected error: {e}")
    
    async def test_connection(self) -> bool:
        """
        Test SNMP connection.
        
        Returns:
            bool: True if connection is working
        """
        try:
            # Try to get system description
            result = await self.get('1.3.6.1.2.1.1.1.0')
            return result is not None
        except Exception:
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        if not self.config:
            return {'connected': False}
        
        return {
            'connected': self.is_connected,
            'host': self.config.host,
            'port': self.config.port,
            'version': self.config.version,
            'community': self.config.community if self.config.version in ["1", "2c"] else None,
            'username': self.config.username if self.config.version == "3" else None,
            'timeout': self.config.timeout,
            'retries': self.config.retries
        }
    
    # Common SNMP OIDs for network monitoring
    COMMON_OIDS = {
        'sysDescr': '1.3.6.1.2.1.1.1.0',
        'sysObjectID': '1.3.6.1.2.1.1.2.0',
        'sysUpTime': '1.3.6.1.2.1.1.3.0',
        'sysContact': '1.3.6.1.2.1.1.4.0',
        'sysName': '1.3.6.1.2.1.1.5.0',
        'sysLocation': '1.3.6.1.2.1.1.6.0',
        'sysServices': '1.3.6.1.2.1.1.7.0',
        
        # Interface table
        'ifTable': '1.3.6.1.2.1.2.2',
        'ifDescr': '1.3.6.1.2.1.2.2.1.2',
        'ifType': '1.3.6.1.2.1.2.2.1.3',
        'ifMtu': '1.3.6.1.2.1.2.2.1.4',
        'ifSpeed': '1.3.6.1.2.1.2.2.1.5',
        'ifPhysAddress': '1.3.6.1.2.1.2.2.1.6',
        'ifAdminStatus': '1.3.6.1.2.1.2.2.1.7',
        'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',
        'ifInOctets': '1.3.6.1.2.1.2.2.1.10',
        'ifInErrors': '1.3.6.1.2.1.2.2.1.14',
        'ifOutOctets': '1.3.6.1.2.1.2.2.1.16',
        'ifOutErrors': '1.3.6.1.2.1.2.2.1.20',
        
        # IP table
        'ipAddrTable': '1.3.6.1.2.1.4.20',
        'ipAdEntAddr': '1.3.6.1.2.1.4.20.1.1',
        'ipAdEntNetMask': '1.3.6.1.2.1.4.20.1.3',
        
        # TCP/UDP
        'tcpConnTable': '1.3.6.1.2.1.6.13',
        'udpTable': '1.3.6.1.2.1.7.5',
        
        # SNMP statistics
        'snmpInPkts': '1.3.6.1.2.1.11.1.0',
        'snmpOutPkts': '1.3.6.1.2.1.11.2.0',
        'snmpInBadVersions': '1.3.6.1.2.1.11.3.0',
        'snmpInBadCommunityNames': '1.3.6.1.2.1.11.4.0'
    }
    
    async def get_system_info(self) -> Dict[str, str]:
        """Get basic system information."""
        system_oids = [
            'sysDescr', 'sysObjectID', 'sysUpTime', 
            'sysContact', 'sysName', 'sysLocation'
        ]
        
        oids = [self.COMMON_OIDS[oid] for oid in system_oids]
        results = await self.get_bulk(oids)
        
        system_info = {}
        for i, oid_name in enumerate(system_oids):
            oid = oids[i]
            system_info[oid_name] = results.get(oid)
        
        return system_info
    
    async def get_interface_table(self) -> List[Dict[str, str]]:
        """Get interface table information."""
        return await self.get_table(self.COMMON_OIDS['ifTable'])
    
    async def get_interface_stats(self, interface_index: str) -> Dict[str, str]:
        """Get statistics for a specific interface."""
        stats_oids = {
            'ifInOctets': f"{self.COMMON_OIDS['ifInOctets']}.{interface_index}",
            'ifOutOctets': f"{self.COMMON_OIDS['ifOutOctets']}.{interface_index}",
            'ifInErrors': f"{self.COMMON_OIDS['ifInErrors']}.{interface_index}",
            'ifOutErrors': f"{self.COMMON_OIDS['ifOutErrors']}.{interface_index}",
            'ifAdminStatus': f"{self.COMMON_OIDS['ifAdminStatus']}.{interface_index}",
            'ifOperStatus': f"{self.COMMON_OIDS['ifOperStatus']}.{interface_index}"
        }
        
        results = await self.get_bulk(list(stats_oids.values()))
        
        stats = {}
        for stat_name, oid in stats_oids.items():
            stats[stat_name] = results.get(oid)
        
        return stats