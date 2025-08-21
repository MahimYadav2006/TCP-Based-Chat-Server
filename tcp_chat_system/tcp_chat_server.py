#!/usr/bin/env python3
"""
TCP-based Chat Server with Congestion Control & Packet Loss Handling
==================================================================

This implementation includes:
- Multi-threaded TCP chat server
- Custom congestion control algorithm (similar to TCP Reno)
- Packet loss detection and recovery
- Flow control mechanisms
- Message acknowledgment system
- Client connection management
- Graceful shutdown handling
"""

import socket
import threading
import time
import json
import struct
import hashlib
import random
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageType(Enum):
    CHAT = "chat"
    ACK = "ack"
    HEARTBEAT = "heartbeat"
    JOIN = "join"
    LEAVE = "leave"
    RETRANSMIT = "retransmit"

class CongestionState(Enum):
    SLOW_START = "slow_start"
    CONGESTION_AVOIDANCE = "congestion_avoidance"
    FAST_RECOVERY = "fast_recovery"

@dataclass
class Message:
    msg_id: str
    msg_type: MessageType
    sender: str
    content: str
    timestamp: float
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = self.calculate_checksum()
    
    def calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum for message integrity"""
        data = f"{self.msg_id}{self.msg_type.value}{self.sender}{self.content}{self.timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def is_valid(self) -> bool:
        """Verify message integrity"""
        return self.checksum == self.calculate_checksum()
    
    def to_bytes(self) -> bytes:
        """Serialize message to bytes"""
        data = asdict(self)
        data['msg_type'] = data['msg_type'].value
        json_data = json.dumps(data).encode()
        # Pack length + data
        return struct.pack('!I', len(json_data)) + json_data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Message':
        """Deserialize message from bytes"""
        json_data = json.loads(data.decode())
        json_data['msg_type'] = MessageType(json_data['msg_type'])
        return cls(**json_data)

class CongestionControl:
    """TCP Reno-like congestion control implementation"""
    
    def __init__(self):
        self.cwnd = 1.0  # Congestion window
        self.ssthresh = 64.0  # Slow start threshold
        self.state = CongestionState.SLOW_START
        self.duplicate_acks = 0
        self.last_ack = 0
        self.rtt_samples = []
        self.srtt = 0.0  # Smoothed RTT
        self.rttvar = 0.0  # RTT variance
        self.rto = 3.0  # Retransmission timeout
        
    def on_ack_received(self, ack_num: int, rtt: float):
        """Handle ACK reception and update congestion window"""
        self.update_rtt(rtt)
        
        if ack_num > self.last_ack:
            # New ACK
            self.duplicate_acks = 0
            self.last_ack = ack_num
            
            if self.state == CongestionState.SLOW_START:
                self.cwnd += 1.0
                if self.cwnd >= self.ssthresh:
                    self.state = CongestionState.CONGESTION_AVOIDANCE
            elif self.state == CongestionState.CONGESTION_AVOIDANCE:
                self.cwnd += 1.0 / self.cwnd
            elif self.state == CongestionState.FAST_RECOVERY:
                self.cwnd = self.ssthresh
                self.state = CongestionState.CONGESTION_AVOIDANCE
                
        elif ack_num == self.last_ack:
            # Duplicate ACK
            self.duplicate_acks += 1
            if self.duplicate_acks == 3:
                # Fast retransmit
                self.ssthresh = max(self.cwnd / 2, 2.0)
                self.cwnd = self.ssthresh + 3.0
                self.state = CongestionState.FAST_RECOVERY
            elif self.state == CongestionState.FAST_RECOVERY:
                self.cwnd += 1.0
    
    def on_timeout(self):
        """Handle timeout event"""
        self.ssthresh = max(self.cwnd / 2, 2.0)
        self.cwnd = 1.0
        self.state = CongestionState.SLOW_START
        self.duplicate_acks = 0
        self.rto *= 2  # Exponential backoff
    
    def update_rtt(self, rtt: float):
        """Update RTT estimates using Jacobson's algorithm"""
        if not self.rtt_samples:
            self.srtt = rtt
            self.rttvar = rtt / 2
        else:
            alpha = 0.125
            beta = 0.25
            self.rttvar = (1 - beta) * self.rttvar + beta * abs(self.srtt - rtt)
            self.srtt = (1 - alpha) * self.srtt + alpha * rtt
        
        self.rto = max(1.0, self.srtt + 4 * self.rttvar)
        self.rtt_samples.append(rtt)
        if len(self.rtt_samples) > 100:
            self.rtt_samples.pop(0)

class ClientConnection:
    """Manages individual client connection with congestion control"""
    
    def __init__(self, socket: socket.socket, address: Tuple[str, int], client_id: str):
        self.socket = socket
        self.address = address
        self.client_id = client_id
        self.username = ""
        self.congestion_control = CongestionControl()
        self.send_queue = queue.Queue()
        self.pending_messages = {}  # msg_id -> (message, timestamp)
        self.last_heartbeat = time.time()
        self.sequence_number = 0
        self.expected_ack = 0
        self.running = True
        
        # Start sender thread
        self.sender_thread = threading.Thread(target=self._sender_worker)
        self.sender_thread.start()
    
    def _sender_worker(self):
        """Worker thread for sending messages with congestion control"""
        while self.running:
            try:
                # Check for retransmissions
                current_time = time.time()
                to_retransmit = []
                
                for msg_id, (message, send_time) in self.pending_messages.items():
                    if current_time - send_time > self.congestion_control.rto:
                        to_retransmit.append(msg_id)
                
                # Handle retransmissions
                for msg_id in to_retransmit:
                    if msg_id in self.pending_messages:
                        message, _ = self.pending_messages[msg_id]
                        logger.warning(f"Retransmitting message {msg_id} to {self.client_id}")
                        self._send_raw(message)
                        self.pending_messages[msg_id] = (message, current_time)
                        self.congestion_control.on_timeout()
                
                # Send new messages based on congestion window
                messages_in_flight = len(self.pending_messages)
                can_send = int(self.congestion_control.cwnd) - messages_in_flight
                
                for _ in range(max(0, can_send)):
                    try:
                        message = self.send_queue.get(timeout=0.1)
                        self._send_raw(message)
                        if message.msg_type != MessageType.ACK:
                            self.pending_messages[message.msg_id] = (message, current_time)
                    except queue.Empty:
                        break
                
                time.sleep(0.01)  # Small delay to prevent busy waiting
                
            except Exception as e:
                logger.error(f"Error in sender worker for {self.client_id}: {e}")
                break
    
    def _send_raw(self, message: Message):
        """Send message directly to socket"""
        try:
            data = message.to_bytes()
            self.socket.sendall(data)
        except Exception as e:
            logger.error(f"Failed to send message to {self.client_id}: {e}")
            self.running = False
    
    def send_message(self, message: Message):
        """Queue message for sending"""
        if self.running:
            self.send_queue.put(message)
    
    def handle_ack(self, ack_message: Message):
        """Process acknowledgment message"""
        try:
            ack_data = json.loads(ack_message.content)
            ack_msg_id = ack_data.get('ack_for')
            
            if ack_msg_id in self.pending_messages:
                # Calculate RTT
                _, send_time = self.pending_messages[ack_msg_id]
                rtt = time.time() - send_time
                
                # Update congestion control
                self.congestion_control.on_ack_received(self.expected_ack, rtt)
                self.expected_ack += 1
                
                # Remove from pending
                del self.pending_messages[ack_msg_id]
                
                logger.debug(f"ACK received for {ack_msg_id}, RTT: {rtt:.3f}s, CWND: {self.congestion_control.cwnd:.2f}")
                
        except Exception as e:
            logger.error(f"Error processing ACK from {self.client_id}: {e}")
    
    def close(self):
        """Clean shutdown of connection"""
        self.running = False
        try:
            self.socket.close()
        except:
            pass
        
        if self.sender_thread.is_alive():
            self.sender_thread.join(timeout=1.0)

class ChatServer:
    """Main chat server with congestion control and packet loss handling"""
    
    def __init__(self, host: str = 'localhost', port: int = 8888):
        self.host = host
        self.port = port
        self.socket = None
        self.clients: Dict[str, ClientConnection] = {}
        self.running = False
        
        # Simulate network conditions (for testing)
        self.packet_loss_rate = 0.0  # 0-1.0 (0% to 100%)
        self.artificial_delay = 0.0  # seconds
        
    def start(self):
        """Start the chat server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True
            
            logger.info(f"Chat server started on {self.host}:{self.port}")
            
            # Start heartbeat thread
            heartbeat_thread = threading.Thread(target=self._heartbeat_worker)
            heartbeat_thread.daemon = True
            heartbeat_thread.start()
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    client_id = f"client_{int(time.time())}_{random.randint(1000, 9999)}"
                    
                    logger.info(f"New client connected: {address} (ID: {client_id})")
                    
                    client_conn = ClientConnection(client_socket, address, client_id)
                    self.clients[client_id] = client_conn
                    
                    # Start client handler thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_conn,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
                    
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.shutdown()
    
    def _handle_client(self, client_conn: ClientConnection):
        """Handle messages from a specific client"""
        buffer = b""
        
        while client_conn.running and self.running:
            try:
                data = client_conn.socket.recv(4096)
                if not data:
                    break
                
                buffer += data
                
                # Process complete messages
                while len(buffer) >= 4:
                    msg_length = struct.unpack('!I', buffer[:4])[0]
                    if len(buffer) >= 4 + msg_length:
                        msg_data = buffer[4:4 + msg_length]
                        buffer = buffer[4 + msg_length:]
                        
                        # Simulate packet loss
                        if random.random() < self.packet_loss_rate:
                            logger.warning(f"Simulating packet loss for message from {client_conn.client_id}")
                            continue
                        
                        # Simulate network delay
                        if self.artificial_delay > 0:
                            time.sleep(self.artificial_delay)
                        
                        try:
                            message = Message.from_bytes(msg_data)
                            if message.is_valid():
                                self._process_message(client_conn, message)
                            else:
                                logger.warning(f"Invalid message checksum from {client_conn.client_id}")
                        except Exception as e:
                            logger.error(f"Error processing message from {client_conn.client_id}: {e}")
                    else:
                        break
                        
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error handling client {client_conn.client_id}: {e}")
                break
        
        self._disconnect_client(client_conn.client_id)
    
    def _process_message(self, client_conn: ClientConnection, message: Message):
        """Process received message based on type"""
        client_conn.last_heartbeat = time.time()
        
        # Send ACK for non-ACK messages
        if message.msg_type != MessageType.ACK:
            ack_message = Message(
                msg_id=f"ack_{int(time.time())}_{random.randint(1000, 9999)}",
                msg_type=MessageType.ACK,
                sender="server",
                content=json.dumps({"ack_for": message.msg_id}),
                timestamp=time.time()
            )
            client_conn.send_message(ack_message)
        
        if message.msg_type == MessageType.JOIN:
            client_conn.username = message.content
            logger.info(f"Client {client_conn.client_id} joined as '{client_conn.username}'")
            self._broadcast_message(
                f"*** {client_conn.username} joined the chat ***",
                exclude_client=client_conn.client_id
            )
            
        elif message.msg_type == MessageType.CHAT:
            logger.info(f"Chat message from {client_conn.username}: {message.content}")
            self._broadcast_message(
                f"[{client_conn.username}]: {message.content}",
                exclude_client=client_conn.client_id
            )
            
        elif message.msg_type == MessageType.ACK:
            client_conn.handle_ack(message)
            
        elif message.msg_type == MessageType.HEARTBEAT:
            # Heartbeat handled by updating last_heartbeat timestamp
            pass
            
        elif message.msg_type == MessageType.LEAVE:
            logger.info(f"Client {client_conn.client_id} requested to leave")
            self._disconnect_client(client_conn.client_id)
    
    def _broadcast_message(self, content: str, exclude_client: Optional[str] = None):
        """Broadcast message to all connected clients"""
        message = Message(
            msg_id=f"broadcast_{int(time.time())}_{random.randint(1000, 9999)}",
            msg_type=MessageType.CHAT,
            sender="server",
            content=content,
            timestamp=time.time()
        )
        
        for client_id, client_conn in self.clients.items():
            if client_id != exclude_client and client_conn.running:
                client_conn.send_message(message)
    
    def _heartbeat_worker(self):
        """Send periodic heartbeats and check for dead connections"""
        while self.running:
            current_time = time.time()
            dead_clients = []
            
            for client_id, client_conn in self.clients.items():
                if current_time - client_conn.last_heartbeat > 30:  # 30 second timeout
                    logger.warning(f"Client {client_id} timed out")
                    dead_clients.append(client_id)
                elif current_time - client_conn.last_heartbeat > 10:  # Send heartbeat every 10 seconds
                    heartbeat_msg = Message(
                        msg_id=f"heartbeat_{int(time.time())}_{random.randint(1000, 9999)}",
                        msg_type=MessageType.HEARTBEAT,
                        sender="server",
                        content="ping",
                        timestamp=time.time()
                    )
                    client_conn.send_message(heartbeat_msg)
            
            for client_id in dead_clients:
                self._disconnect_client(client_id)
            
            time.sleep(5)  # Check every 5 seconds
    
    def _disconnect_client(self, client_id: str):
        """Disconnect and cleanup client"""
        if client_id in self.clients:
            client_conn = self.clients[client_id]
            username = client_conn.username or client_id
            
            logger.info(f"Disconnecting client {client_id}")
            
            if client_conn.username:
                self._broadcast_message(
                    f"*** {username} left the chat ***",
                    exclude_client=client_id
                )
            
            client_conn.close()
            del self.clients[client_id]
    
    def set_network_conditions(self, packet_loss_rate: float = 0.0, delay: float = 0.0):
        """Set artificial network conditions for testing"""
        self.packet_loss_rate = max(0.0, min(1.0, packet_loss_rate))
        self.artificial_delay = max(0.0, delay)
        logger.info(f"Network conditions: {self.packet_loss_rate*100}% loss, {self.artificial_delay}s delay")
    
    def get_server_stats(self) -> Dict:
        """Get server statistics"""
        stats = {
            "connected_clients": len(self.clients),
            "client_details": {}
        }
        
        for client_id, client_conn in self.clients.items():
            cc = client_conn.congestion_control
            stats["client_details"][client_id] = {
                "username": client_conn.username,
                "address": client_conn.address,
                "congestion_window": cc.cwnd,
                "rto": cc.rto,
                "pending_messages": len(client_conn.pending_messages),
                "state": cc.state.value
            }
        
        return stats
    
    def shutdown(self):
        """Gracefully shutdown server"""
        logger.info("Shutting down server...")
        self.running = False
        
        # Disconnect all clients
        for client_id in list(self.clients.keys()):
            self._disconnect_client(client_id)
        
        # Close server socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

def main():
    """Main server entry point"""
    server = ChatServer(host='localhost', port=8888)
    
    try:
        # Optional: Set network conditions for testing
        # server.set_network_conditions(packet_loss_rate=0.1, delay=0.05)
        
        server.start()
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    finally:
        server.shutdown()

if __name__ == "__main__":
    main()