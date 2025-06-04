"""
Network scanner for device discovery and monitoring.
"""

import asyncio
import logging
import socket
import struct
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv4Address
import time

try:
    import scapy.all as scapy
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False


@dataclass
class DiscoveredDevice:
    """Discovered network device information."""
    ip_address: str
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    open_ports: List[int] = None
    services: Dict[int, str] = None
    response_time: Optional[float] = None
    device_type: Optional[str] = None
    snmp_community: Optional[str] = None
    
    def __post_init__(self):
        if self.open_ports is None:
            self.open_ports = []
        if self.services is None:
            self.services = {}


class NetworkScanner:
    """
    Cross-platform network scanner for device discovery.
    
    Supports ping sweeps, port scanning, service detection,
    and device fingerprinting.
    """
    
    def __init__(self):
        """Initialize network scanner."""
        self.logger = logging.getLogger(__name__)
        
        # Common ports to scan
        self.common_ports = [
            21,    # FTP
            22,    # SSH
            23,    # Telnet
            25,    # SMTP
            53,    # DNS
            80,    # HTTP
            110,   # POP3
            143,   # IMAP
            161,   # SNMP
            443,   # HTTPS
            993,   # IMAPS
            995,   # POP3S
            3389,  # RDP
            5432,  # PostgreSQL
            3306,  # MySQL
            1433,  # MSSQL
            8080,  # HTTP Alt
            8443,  # HTTPS Alt
        ]
        
        # Network device specific ports
        self.network_device_ports = [
            22,    # SSH
            23,    # Telnet
            80,    # HTTP Management
            161,   # SNMP
            443,   # HTTPS Management
            8080,  # Alt HTTP
            8443,  # Alt HTTPS
            9443,  # UniFi
            4786,  # Cisco Smart Install
        ]
        
        # Service signatures
        self.service_signatures = {
            21: "ftp",
            22: "ssh",
            23: "telnet",
            25: "smtp",
            53: "dns",
            80: "http",
            110: "pop3",
            143: "imap",
            161: "snmp",
            443: "https",
            993: "imaps",
            995: "pop3s",
            3389: "rdp",
            5432: "postgresql",
            3306: "mysql",
            1433: "mssql",
            8080: "http-alt",
            8443: "https-alt",
            9443: "unifi"
        }
        
        if not SCAPY_AVAILABLE:
            self.logger.warning("Scapy not available, some scanning features disabled")
    
    async def ping_host(self, host: str, timeout: float = 3.0) -> Tuple[bool, float]:
        """
        Ping a single host.
        
        Args:
            host: Host IP address or hostname
            timeout: Ping timeout in seconds
            
        Returns:
            Tuple[bool, float]: (is_alive, response_time)
        """
        try:
            start_time = time.time()
            
            # Use platform-specific ping command
            import platform
            system = platform.system().lower()
            
            if system == "windows":
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
            else:  # Linux/macOS
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), host]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout + 1
            )
            
            response_time = time.time() - start_time
            
            if process.returncode == 0:
                return True, response_time
            else:
                return False, 0.0
                
        except asyncio.TimeoutError:
            return False, 0.0
        except Exception as e:
            self.logger.debug(f"Ping failed for {host}: {e}")
            return False, 0.0
    
    async def scan_port(self, host: str, port: int, timeout: float = 3.0) -> bool:
        """
        Scan a single port on a host.
        
        Args:
            host: Host IP address
            port: Port number
            timeout: Connection timeout
            
        Returns:
            bool: True if port is open
        """
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
    
    async def scan_ports(self, host: str, ports: List[int], 
                        timeout: float = 3.0, max_concurrent: int = 50) -> List[int]:
        """
        Scan multiple ports on a host.
        
        Args:
            host: Host IP address
            ports: List of ports to scan
            timeout: Connection timeout per port
            max_concurrent: Maximum concurrent connections
            
        Returns:
            List[int]: List of open ports
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scan_single_port(port):
            async with semaphore:
                return port if await self.scan_port(host, port, timeout) else None
        
        tasks = [scan_single_port(port) for port in ports]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        open_ports = [port for port in results if isinstance(port, int)]
        return sorted(open_ports)
    
    async def detect_service(self, host: str, port: int, timeout: float = 5.0) -> Optional[str]:
        """
        Detect service running on a port.
        
        Args:
            host: Host IP address
            port: Port number
            timeout: Connection timeout
            
        Returns:
            Optional[str]: Service name or None
        """
        try:
            # Try to get service banner
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            
            # Read initial banner
            try:
                banner = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                banner_text = banner.decode('utf-8', errors='ignore').strip()
            except:
                banner_text = ""
            
            writer.close()
            await writer.wait_closed()
            
            # Analyze banner for service identification
            service = self._identify_service_from_banner(port, banner_text)
            return service
            
        except Exception:
            # Fallback to known service mapping
            return self.service_signatures.get(port)
    
    def _identify_service_from_banner(self, port: int, banner: str) -> Optional[str]:
        """Identify service from banner text."""
        banner_lower = banner.lower()
        
        # SSH
        if "ssh" in banner_lower:
            return "ssh"
        
        # HTTP/HTTPS
        if any(x in banner_lower for x in ["http", "server:", "apache", "nginx", "iis"]):
            return "https" if port == 443 else "http"
        
        # FTP
        if "ftp" in banner_lower or "220" in banner:
            return "ftp"
        
        # SMTP
        if "smtp" in banner_lower or "220" in banner and "mail" in banner_lower:
            return "smtp"
        
        # Telnet
        if "telnet" in banner_lower or len(banner) == 0 and port == 23:
            return "telnet"
        
        # SNMP (usually no banner)
        if port == 161:
            return "snmp"
        
        # Fallback to port-based identification
        return self.service_signatures.get(port)
    
    async def get_hostname(self, ip: str, timeout: float = 3.0) -> Optional[str]:
        """
        Get hostname for IP address.
        
        Args:
            ip: IP address
            timeout: DNS lookup timeout
            
        Returns:
            Optional[str]: Hostname or None
        """
        try:
            loop = asyncio.get_event_loop()
            hostname, _, _ = await asyncio.wait_for(
                loop.run_in_executor(None, socket.gethostbyaddr, ip),
                timeout=timeout
            )
            return hostname
        except Exception:
            return None
    
    def get_mac_address(self, ip: str) -> Optional[str]:
        """
        Get MAC address for IP (requires Scapy).
        
        Args:
            ip: IP address
            
        Returns:
            Optional[str]: MAC address or None
        """
        if not SCAPY_AVAILABLE:
            return None
        
        try:
            # Send ARP request
            arp_request = scapy.ARP(pdst=ip)
            broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
            arp_request_broadcast = broadcast / arp_request
            
            answered_list = scapy.srp(arp_request_broadcast, timeout=2, verbose=False)[0]
            
            if answered_list:
                return answered_list[0][1].hwsrc
            
        except Exception as e:
            self.logger.debug(f"MAC address lookup failed for {ip}: {e}")
        
        return None
    
    def get_vendor_from_mac(self, mac: str) -> Optional[str]:
        """
        Get vendor from MAC address OUI.
        
        Args:
            mac: MAC address
            
        Returns:
            Optional[str]: Vendor name or None
        """
        if not mac or len(mac) < 8:
            return None
        
        # Extract OUI (first 3 octets)
        oui = mac.replace(":", "").replace("-", "").upper()[:6]
        
        # Common network equipment vendors
        vendor_map = {
            "000C29": "VMware",
            "005056": "VMware",
            "001B21": "Intel",
            "00E04C": "Realtek",
            "001E58": "WatchGuard",
            "00A0C9": "Intel",
            "000D3A": "Cisco",
            "001F26": "Cisco",
            "0050E4": "Cisco",
            "00907F": "Cisco",
            "001B67": "Cisco",
            "F46D04": "Ubiquiti",
            "04F021": "Ubiquiti",
            "B4FBE4": "Ubiquiti",
            "78A3E4": "Ubiquiti",
            "001DD8": "Mikrotik",
            "4C5E0C": "Mikrotik",
            "6C3B6B": "Mikrotik",
            "E4956E": "Mikrotik",
            "001E2A": "Microsemi",
            "00D0C9": "Intel",
            "001B21": "Intel",
            "7C7A91": "Mikrotik",
            "B827EB": "Raspberry Pi",
            "DCA632": "Raspberry Pi",
            "E45F01": "Raspberry Pi"
        }
        
        return vendor_map.get(oui)
    
    async def discover_network(self, network: str, 
                             ping_scan: bool = True,
                             port_scan: bool = True,
                             service_detection: bool = True,
                             max_concurrent: int = 100) -> List[DiscoveredDevice]:
        """
        Discover devices on a network.
        
        Args:
            network: Network CIDR (e.g., "192.168.1.0/24")
            ping_scan: Whether to perform ping scan
            port_scan: Whether to scan ports
            service_detection: Whether to detect services
            max_concurrent: Maximum concurrent operations
            
        Returns:
            List[DiscoveredDevice]: Discovered devices
        """
        try:
            net = IPv4Network(network, strict=False)
            hosts = list(net.hosts())
            
            self.logger.info(f"Scanning network {network} ({len(hosts)} hosts)")
            
            # Ping scan
            alive_hosts = []
            if ping_scan:
                alive_hosts = await self._ping_scan(hosts, max_concurrent)
                self.logger.info(f"Found {len(alive_hosts)} alive hosts")
            else:
                alive_hosts = [(str(host), 0.0) for host in hosts]
            
            # Detailed scanning
            devices = []
            semaphore = asyncio.Semaphore(max_concurrent // 4)  # Reduce concurrency for detailed scan
            
            async def scan_device(host_info):
                async with semaphore:
                    return await self._scan_device_details(
                        host_info[0], host_info[1], port_scan, service_detection
                    )
            
            tasks = [scan_device(host_info) for host_info in alive_hosts]
            devices = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions
            valid_devices = [dev for dev in devices if isinstance(dev, DiscoveredDevice)]
            
            self.logger.info(f"Completed network scan: {len(valid_devices)} devices discovered")
            return valid_devices
            
        except Exception as e:
            self.logger.error(f"Network discovery failed: {e}")
            return []
    
    async def _ping_scan(self, hosts: List[IPv4Address], max_concurrent: int) -> List[Tuple[str, float]]:
        """Perform ping scan on hosts."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def ping_single_host(host):
            async with semaphore:
                alive, response_time = await self.ping_host(str(host))
                return (str(host), response_time) if alive else None
        
        tasks = [ping_single_host(host) for host in hosts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        alive_hosts = [result for result in results if result is not None and isinstance(result, tuple)]
        return alive_hosts
    
    async def _scan_device_details(self, ip: str, response_time: float,
                                  port_scan: bool, service_detection: bool) -> DiscoveredDevice:
        """Scan detailed information for a device."""
        device = DiscoveredDevice(ip_address=ip, response_time=response_time)
        
        # Get hostname
        device.hostname = await self.get_hostname(ip)
        
        # Get MAC address and vendor
        device.mac_address = self.get_mac_address(ip)
        if device.mac_address:
            device.vendor = self.get_vendor_from_mac(device.mac_address)
        
        # Port scanning
        if port_scan:
            device.open_ports = await self.scan_ports(ip, self.network_device_ports)
            
            # Service detection
            if service_detection and device.open_ports:
                for port in device.open_ports:
                    service = await self.detect_service(ip, port)
                    if service:
                        device.services[port] = service
        
        # Device type detection
        device.device_type = self._detect_device_type(device)
        
        # SNMP community detection
        if 161 in device.open_ports:
            device.snmp_community = await self._detect_snmp_community(ip)
        
        return device
    
    def _detect_device_type(self, device: DiscoveredDevice) -> Optional[str]:
        """Detect device type based on available information."""
        # Check vendor
        if device.vendor:
            vendor_lower = device.vendor.lower()
            if "cisco" in vendor_lower:
                return "router" if 22 in device.open_ports or 23 in device.open_ports else "switch"
            elif "ubiquiti" in vendor_lower:
                return "access_point" if 9443 in device.open_ports else "router"
            elif "mikrotik" in vendor_lower:
                return "router"
            elif "watchguard" in vendor_lower:
                return "firewall"
        
        # Check open ports
        if device.open_ports:
            # Web management interface suggests network device
            if any(port in device.open_ports for port in [80, 443, 8080, 8443]):
                if 161 in device.open_ports:  # SNMP
                    return "network_device"
                elif 9443 in device.open_ports:  # UniFi
                    return "access_point"
            
            # SSH/Telnet suggests managed device
            if any(port in device.open_ports for port in [22, 23]):
                return "network_device"
            
            # Common server ports
            if any(port in device.open_ports for port in [3389, 5432, 3306, 1433]):
                return "server"
        
        return "unknown"
    
    async def _detect_snmp_community(self, ip: str) -> Optional[str]:
        """Detect SNMP community string."""
        common_communities = ["public", "private", "admin", "cisco", "default"]
        
        for community in common_communities:
            try:
                # Simple SNMP test (would need pysnmp for full implementation)
                # This is a placeholder - actual implementation would use SNMP library
                if await self._test_snmp_community(ip, community):
                    return community
            except Exception:
                continue
        
        return None
    
    async def _test_snmp_community(self, ip: str, community: str) -> bool:
        """Test SNMP community string (placeholder)."""
        # This would require pysnmp implementation
        # For now, return False as placeholder
        return False
    
    async def scan_subnet_for_devices(self, subnet: str) -> List[DiscoveredDevice]:
        """
        Quick scan for network devices in subnet.
        
        Args:
            subnet: Network subnet in CIDR notation
            
        Returns:
            List[DiscoveredDevice]: Discovered network devices
        """
        devices = await self.discover_network(
            subnet,
            ping_scan=True,
            port_scan=True,
            service_detection=False,  # Skip for speed
            max_concurrent=50
        )
        
        # Filter for likely network devices
        network_devices = []
        for device in devices:
            if (device.device_type in ["router", "switch", "access_point", "firewall", "network_device"] or
                161 in device.open_ports or  # SNMP
                any(port in device.open_ports for port in [22, 23, 80, 443])):  # Management interfaces
                network_devices.append(device)
        
        return network_devices
    
    def get_local_networks(self) -> List[str]:
        """
        Get local network subnets.
        
        Returns:
            List[str]: List of local network CIDRs
        """
        networks = []
        
        try:
            import psutil
            
            # Get network interfaces
            interfaces = psutil.net_if_addrs()
            
            for interface_name, addresses in interfaces.items():
                # Skip loopback
                if interface_name.startswith('lo'):
                    continue
                
                for addr in addresses:
                    if addr.family == socket.AF_INET:  # IPv4
                        ip = addr.address
                        netmask = addr.netmask
                        
                        if ip and netmask and not ip.startswith('127.'):
                            # Calculate network
                            try:
                                network = IPv4Network(f"{ip}/{netmask}", strict=False)
                                networks.append(str(network))
                            except Exception:
                                continue
        
        except Exception as e:
            self.logger.error(f"Failed to get local networks: {e}")
        
        return networks
    
    async def quick_device_check(self, ip: str) -> Dict[str, Any]:
        """
        Quick check of a device.
        
        Args:
            ip: Device IP address
            
        Returns:
            Dict[str, Any]: Device information
        """
        alive, response_time = await self.ping_host(ip)
        
        if not alive:
            return {"ip": ip, "alive": False}
        
        # Quick port scan
        open_ports = await self.scan_ports(ip, self.network_device_ports, timeout=1.0)
        
        # Get hostname
        hostname = await self.get_hostname(ip)
        
        return {
            "ip": ip,
            "alive": True,
            "response_time": response_time,
            "hostname": hostname,
            "open_ports": open_ports,
            "has_snmp": 161 in open_ports,
            "has_ssh": 22 in open_ports,
            "has_web": any(port in open_ports for port in [80, 443, 8080, 8443])
        }