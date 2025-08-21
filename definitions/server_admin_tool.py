#!/usr/bin/env python3
"""
Chat Server Administration Tool
=============================

This tool provides administrative capabilities for the TCP chat server:
- Monitor server statistics
- Manage connected clients
- Configure network simulation
- View logs and performance metrics
"""

import socket
import json
import time
import argparse
import sys
import threading
from typing import Dict, Any, Optional

class ServerAdminClient:
    """Administration client for chat server management"""
    
    def __init__(self, server_host: str = 'localhost', server_port: int = 8889):
        self.server_host = server_host
        self.server_port = server_port  # Admin port (different from chat port)
        self.socket: Optional[socket.socket] = None
        self.connected = False
    
    def connect(self) -> bool:
        """Connect to server admin interface"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((self.server_host, self.server_port))
            self.connected = True
            print(f"Connected to server admin interface at {self.server_host}:{self.server_port}")
            return True
        except Exception as e:
            print(f"Failed to connect to admin interface: {e}")
            return False
    
    def send_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send admin command to server"""
        if not self.connected:
            return {"error": "Not connected to server"}
        
        try:
            request = {
                "command": command,
                "params": params or {},
                "timestamp": time.time()
            }
            
            data = json.dumps(request).encode()
            self.socket.sendall(len(data).to_bytes(4, 'big') + data)
            
            # Receive response
            response_length = int.from_bytes(self.socket.recv(4), 'big')
            response_data = b""
            while len(response_data) < response_length:
                chunk = self.socket.recv(response_length - len(response_data))
                if not chunk:
                    break
                response_data += chunk
            
            return json.loads(response_data.decode())
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_server_stats(self) -> Dict[str, Any]:
        """Get comprehensive server statistics"""
        return self.send_command("get_stats")
    
    def get_client_list(self) -> Dict[str, Any]:
        """Get list of connected clients"""
        return self.send_command("get_clients")
    
    def kick_client(self, client_id: str) -> Dict[str, Any]:
        """Kick a client from the server"""
        return self.send_command("kick_client", {"client_id": client_id})
    
    def broadcast_message(self, message: str) -> Dict[str, Any]:
        """Send broadcast message to all clients"""
        return self.send_command("broadcast", {"message": message})
    
    def set_network_simulation(self, packet_loss: float, delay: float) -> Dict[str, Any]:
        """Configure network simulation parameters"""
        return self.send_command("set_network_sim", {
            "packet_loss_rate": packet_loss,
            "delay": delay
        })
    
    def shutdown_server(self) -> Dict[str, Any]:
        """Shutdown the server gracefully"""
        return self.send_command("shutdown")
    
    def disconnect(self):
        """Disconnect from admin interface"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

def format_bytes(bytes_value: int) -> str:
    """Format byte count in human-readable form"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} TB"

def format_duration(seconds: float) -> str:
    """Format duration in human-readable form"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def print_server_stats(stats: Dict[str, Any]):
    """Print formatted server statistics"""
    print("\n" + "=" * 60)
    print("SERVER STATISTICS")
    print("=" * 60)
    
    if "error" in stats:
        print(f"Error: {stats['error']}")
        return
    
    print(f"Connected clients: {stats.get('connected_clients', 0)}")
    print(f"Total messages processed: {stats.get('total_messages', 0)}")
    print(f"Server uptime: {format_duration(stats.get('uptime', 0))}")
    print(f"Data transferred: {format_bytes(stats.get('bytes_transferred', 0))}")
    
    if "client_details" in stats:
        print(f"\nCLIENT DETAILS:")
        print("-" * 60)
        for client_id, details in stats["client_details"].items():
            print(f"Client ID: {client_id}")
            print(f"  Username: {details.get('username', 'N/A')}")
            print(f"  Address: {details.get('address', 'N/A')}")
            print(f"  Congestion Window: {details.get('congestion_window', 0):.2f}")
            print(f"  RTO: {details.get('rto', 0):.3f}s")
            print(f"  Pending Messages: {details.get('pending_messages', 0)}")
            print(f"  State: {details.get('state', 'Unknown')}")
            print()

def interactive_mode(admin_client: ServerAdminClient):
    """Interactive administration mode"""
    print("\n=== TCP Chat Server Administration ===")
    print("Commands:")
    print("  stats    - Show server statistics")
    print("  clients  - List connected clients")
    print("  kick <client_id> - Kick a client")
    print("  broadcast <message> - Broadcast message to all clients")
    print("  simulate <loss%> <delay_ms> - Set network simulation")
    print("  shutdown - Shutdown server")
    print("  help     - Show this help")
    print("  quit     - Exit admin tool")
    print()
    
    while True:
        try:
            command = input("admin> ").strip().split()
            if not command:
                continue
            
            cmd = command[0].lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "help":
                print("Available commands: stats, clients, kick, broadcast, simulate, shutdown, help, quit")
            elif cmd == "stats":
                stats = admin_client.get_server_stats()
                print_server_stats(stats)
            elif cmd == "clients":
                clients = admin_client.get_client_list()
                if "error" in clients:
                    print(f"Error: {clients['error']}")
                else:
                    print(f"Connected clients: {len(clients.get('clients', []))}")
                    for client in clients.get('clients', []):
                        print(f"  {client['id']}: {client['username']} ({client['address']})")
            else:
                print(f"Unknown command: {args.command}")
        elif args.mode == "monitor":
            monitor_mode(admin_client, args.interval)
        else:
            interactive_mode(admin_client)
            
    finally:
        admin_client.disconnect()

if __name__ == "__main__":
    main()print(f"\nConnected clients: {len(clients.get('clients', []))}")
                    for client in clients.get('clients', []):
                        print(f"  {client['id']}: {client['username']} ({client['address']})")
            elif cmd == "kick" and len(command) > 1:
                client_id = command[1]
                result = admin_client.kick_client(client_id)
                if "error" in result:
                    print(f"Error: {result['error']}")
                else:
                    print(f"Client {client_id} kicked successfully")
            elif cmd == "broadcast" and len(command) > 1:
                message = " ".join(command[1:])
                result = admin_client.broadcast_message(f"[ADMIN] {message}")
                if "error" in result:
                    print(f"Error: {result['error']}")
                else:
                    print("Broadcast sent successfully")
            elif cmd == "simulate" and len(command) >= 3:
                try:
                    loss_percent = float(command[1])
                    delay_ms = float(command[2])
                    result = admin_client.set_network_simulation(
                        loss_percent / 100.0, delay_ms / 1000.0
                    )
                    if "error" in result:
                        print(f"Error: {result['error']}")
                    else:
                        print(f"Network simulation set: {loss_percent}% loss, {delay_ms}ms delay")
                except ValueError:
                    print("Usage: simulate <loss_percentage> <delay_milliseconds>")
            elif cmd == "shutdown":
                confirm = input("Are you sure you want to shutdown the server? (yes/no): ")
                if confirm.lower() in ['yes', 'y']:
                    result = admin_client.shutdown_server()
                    if "error" in result:
                        print(f"Error: {result['error']}")
                    else:
                        print("Server shutdown initiated")
                        break
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except EOFError:
            break

def monitor_mode(admin_client: ServerAdminClient, interval: int = 5):
    """Continuous monitoring mode"""
    print(f"Starting continuous monitoring (interval: {interval}s)")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            stats = admin_client.get_server_stats()
            
            # Clear screen
            print("\033[2J\033[H", end="")
            
            print_server_stats(stats)
            print(f"\nLast updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Next update in {interval}s...")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

def main():
    parser = argparse.ArgumentParser(description="TCP Chat Server Administration Tool")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8889, help="Admin port (default: 8889)")
    parser.add_argument("--mode", choices=["interactive", "monitor"], default="interactive",
                       help="Operation mode (default: interactive)")
    parser.add_argument("--interval", type=int, default=5,
                       help="Monitor interval in seconds (default: 5)")
    parser.add_argument("--command", help="Single command to execute")
    
    args = parser.parse_args()
    
    admin_client = ServerAdminClient(args.host, args.port)
    
    if not admin_client.connect():
        sys.exit(1)
    
    try:
        if args.command:
            # Execute single command
            if args.command == "stats":
                stats = admin_client.get_server_stats()
                print_server_stats(stats)
            elif args.command == "clients":
                clients = admin_client.get_client_list()
                if "error" in clients:
                    print(f"Error: {clients['error']}")
                else: