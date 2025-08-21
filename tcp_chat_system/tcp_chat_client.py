#!/usr/bin/env python3
"""
TCP Chat Client with Congestion Control Support
=============================================

This client implementation includes:
- Connection to TCP chat server
- Message acknowledgment system
- Heartbeat mechanism
- Automatic reconnection
- Input handling and display
- Graceful shutdown
"""

import socket
import threading
import time
import json
import struct
import hashlib
import random
import logging
import signal
import sys
from typing import Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import shared classes (in practice, these would be in a separate module)
class MessageType(Enum):
    CHAT = "chat"
    ACK = "ack"
    HEARTBEAT = "heartbeat"
    JOIN = "join"
    LEAVE = "leave"
    RETRANSMIT = "retransmit"

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
        return struct.pack('!I', len(json_data)) + json_data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Message':
        """Deserialize message from bytes"""
        json_data = json.loads(data.decode())
        json_data['msg_type'] = MessageType(json_data['msg_type'])
        return cls(**json_data)

class ChatClient:
    """TCP Chat Client with robust connection handling"""
    
    def __init__(self, username: str, server_host: str = 'localhost', server_port: int = 8888):
        self.username = username
        self.server_host = server_host
        self.server_port = server_port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.connected = False
        
        # Message handling
        self.message_queue = queue.Queue()
        self.pending_acks = {}  # msg_id -> timestamp
        self.last_heartbeat = time.time()
        
        # Threading
        self.receive_thread: Optional[threading.Thread] = None
        self.sender_thread: Optional[threading.Thread] = None
        self.input_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.messages_sent = 0
        self.messages_received = 0
        self.acks_received = 0
        self.connection_attempts = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Shutdown signal received")
        self.disconnect()
        sys.exit(0)
    
    def connect(self) -> bool:
        """Connect to the chat server"""
        try:
            self.connection_attempts += 1
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)  # 10 second connection timeout
            
            logger.info(f"Connecting to {self.server_host}:{self.server_port}...")
            self.socket.connect((self.server_host, self.server_port))
            self.socket.settimeout(1.0)  # Set shorter timeout for receive operations
            
            self.connected = True
            self.running = True
            logger.info("Connected to server successfully")
            
            # Start worker threads
            self.receive_thread = threading.Thread(target=self._receive_worker)
            self.sender_thread = threading.Thread(target=self._sender_worker)
            self.input_thread = threading.Thread(target=self._input_worker)
            
            self.receive_thread.daemon = True
            self.sender_thread.daemon = True
            self.input_thread.daemon = True
            
            self.receive_thread.start()
            self.sender_thread.start()
            self.input_thread.start()
            
            # Send join message
            self._send_join_message()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            self.connected = False
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
    
    def _send_join_message(self):
        """Send join message to server"""
        join_message = Message(
            msg_id=f"join_{int(time.time())}_{random.randint(1000, 9999)}",
            msg_type=MessageType.JOIN,
            sender=self.username,
            content=self.username,
            timestamp=time.time()
        )
        self._queue_message(join_message)
    
    def _receive_worker(self):
        """Worker thread for receiving messages from server"""
        buffer = b""
        
        while self.running and self.connected:
            try:
                data = self.socket.recv(4096)
                if not data:
                    logger.warning("Server closed connection")
                    break
                
                buffer += data
                
                # Process complete messages
                while len(buffer) >= 4:
                    msg_length = struct.unpack('!I', buffer[:4])[0]
                    if len(buffer) >= 4 + msg_length:
                        msg_data = buffer[4:4 + msg_length]
                        buffer = buffer[4 + msg_length:]
                        
                        try:
                            message = Message.from_bytes(msg_data)
                            if message.is_valid():
                                self._process_received_message(message)
                                self.messages_received += 1
                            else:
                                logger.warning("Received message with invalid checksum")
                        except Exception as e:
                            logger.error(f"Error processing received message: {e}")
                    else:
                        break
                        
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.error(f"Error receiving data: {e}")
                break
        
        if self.running:
            self._handle_disconnect()
    
    def _sender_worker(self):
        """Worker thread for sending messages to server"""
        while self.running and self.connected:
            try:
                # Send queued messages
                try:
                    message = self.message_queue.get(timeout=0.1)
                    self._send_raw_message(message)
                    
                    # Track non-ACK messages for acknowledgment
                    if message.msg_type != MessageType.ACK:
                        self.pending_acks[message.msg_id] = time.time()
                    
                    self.messages_sent += 1
                    
                except queue.Empty:
                    pass
                
                # Check for ACK timeouts and retransmit if necessary
                current_time = time.time()
                timeout_threshold = 5.0  # 5 seconds
                
                timed_out_messages = []
                for msg_id, send_time in self.pending_acks.items():
                    if current_time - send_time > timeout_threshold:
                        timed_out_messages.append(msg_id)
                
                # Note: In a full implementation, we would store the original
                # messages and retransmit them here
                for msg_id in timed_out_messages:
                    logger.warning(f"Message {msg_id} timed out waiting for ACK")
                    del self.pending_acks[msg_id]
                
                # Send periodic heartbeat
                if current_time - self.last_heartbeat > 15.0:
                    heartbeat = Message(
                        msg_id=f"heartbeat_{int(time.time())}_{random.randint(1000, 9999)}",
                        msg_type=MessageType.HEARTBEAT,
                        sender=self.username,
                        content="ping",
                        timestamp=time.time()
                    )
                    self._queue_message(heartbeat)
                    self.last_heartbeat = current_time
                
            except Exception as e:
                logger.error(f"Error in sender worker: {e}")
                break
    
    def _input_worker(self):
        """Worker thread for handling user input"""
        print(f"\n=== Welcome to the Chat, {self.username}! ===")
        print("Type your messages and press Enter to send.")
        print("Type '/quit' to leave the chat.")
        print("Type '/stats' to show connection statistics.")
        print("=" * 50)
        
        while self.running and self.connected:
            try:
                user_input = input().strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == '/quit':
                    self.disconnect()
                    break
                elif user_input.lower() == '/stats':
                    self._show_stats()
                    continue
                
                # Send chat message
                chat_message = Message(
                    msg_id=f"chat_{int(time.time())}_{random.randint(1000, 9999)}",
                    msg_type=MessageType.CHAT,
                    sender=self.username,
                    content=user_input,
                    timestamp=time.time()
                )
                self._queue_message(chat_message)
                
            except EOFError:
                # Handle Ctrl+D
                self.disconnect()
                break
            except KeyboardInterrupt:
                # Handle Ctrl+C
                self.disconnect()
                break
            except Exception as e:
                logger.error(f"Error in input worker: {e}")
    
    def _process_received_message(self, message: Message):
        """Process messages received from server"""
        # Send ACK for non-ACK messages
        if message.msg_type != MessageType.ACK and message.sender != self.username:
            ack_message = Message(
                msg_id=f"ack_{int(time.time())}_{random.randint(1000, 9999)}",
                msg_type=MessageType.ACK,
                sender=self.username,
                content=json.dumps({"ack_for": message.msg_id}),
                timestamp=time.time()
            )
            self._queue_message(ack_message)
        
        if message.msg_type == MessageType.CHAT:
            # Display chat message
            timestamp = time.strftime("%H:%M:%S", time.localtime(message.timestamp))
            if message.sender == "server":
                print(f"[{timestamp}] {message.content}")
            else:
                print(f"[{timestamp}] {message.content}")
            
        elif message.msg_type == MessageType.ACK:
            # Handle acknowledgment
            try:
                ack_data = json.loads(message.content)
                ack_for = ack_data.get('ack_for')
                if ack_for in self.pending_acks:
                    del self.pending_acks[ack_for]
                    self.acks_received += 1
            except Exception as e:
                logger.error(f"Error processing ACK: {e}")
                
        elif message.msg_type == MessageType.HEARTBEAT:
            # Server heartbeat - respond with our own heartbeat
            if message.content == "ping":
                pong_message = Message(
                    msg_id=f"heartbeat_{int(time.time())}_{random.randint(1000, 9999)}",
                    msg_type=MessageType.HEARTBEAT,
                    sender=self.username,
                    content="pong",
                    timestamp=time.time()
                )
                self._queue_message(pong_message)
    
    def _send_raw_message(self, message: Message):
        """Send message directly to server"""
        try:
            data = message.to_bytes()
            self.socket.sendall(data)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    def _queue_message(self, message: Message):
        """Queue message for sending"""
        if self.running and self.connected:
            self.message_queue.put(message)
    
    def _show_stats(self):
        """Display connection statistics"""
        print("\n" + "=" * 50)
        print("CONNECTION STATISTICS")
        print("=" * 50)
        print(f"Username: {self.username}")
        print(f"Server: {self.server_host}:{self.server_port}")
        print(f"Connected: {self.connected}")
        print(f"Connection attempts: {self.connection_attempts}")
        print(f"Messages sent: {self.messages_sent}")
        print(f"Messages received: {self.messages_received}")
        print(f"ACKs received: {self.acks_received}")
        print(f"Pending ACKs: {len(self.pending_acks)}")
        print("=" * 50 + "\n")
    
    def _handle_disconnect(self):
        """Handle unexpected disconnection"""
        logger.warning("Connection lost to server")
        self.connected = False
        
        # Attempt to reconnect
        max_retries = 5
        retry_delay = 2.0
        
        for attempt in range(max_retries):
            if not self.running:
                break
                
            logger.info(f"Attempting to reconnect ({attempt + 1}/{max_retries})...")
            time.sleep(retry_delay)
            
            if self.connect():
                print("\n*** Reconnected to server ***")
                return
            
            retry_delay *= 2  # Exponential backoff
        
        logger.error("Failed to reconnect to server")
        print("\n*** Could not reconnect to server. Please restart the client. ***")
        self.running = False
    
    def disconnect(self):
        """Disconnect from server gracefully"""
        if self.connected:
            logger.info("Disconnecting from server...")
            
            # Send leave message
            leave_message = Message(
                msg_id=f"leave_{int(time.time())}_{random.randint(1000, 9999)}",
                msg_type=MessageType.LEAVE,
                sender=self.username,
                content="leaving",
                timestamp=time.time()
            )
            
            try:
                self._send_raw_message(leave_message)
                time.sleep(0.1)  # Give time for message to be sent
            except:
                pass
        
        self.running = False
        self.connected = False
        
        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        # Wait for threads to finish
        for thread in [self.receive_thread, self.sender_thread, self.input_thread]:
            if thread and thread.is_alive():
                thread.join(timeout=1.0)
        
        print("\nDisconnected from server. Goodbye!")
    
    def run(self):
        """Main client run loop"""
        if not self.connect():
            return False
        
        try:
            # Keep main thread alive
            while self.running and self.connected:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.disconnect()
        
        return True

def main():
    """Main client entry point"""
    print("=== TCP Chat Client ===")
    
    # Get user input
    username = input("Enter your username: ").strip()
    if not username:
        print("Username cannot be empty!")
        return
    
    server_host = input("Enter server host (default: localhost): ").strip()
    if not server_host:
        server_host = "localhost"
    
    server_port_str = input("Enter server port (default: 8888): ").strip()
    try:
        server_port = int(server_port_str) if server_port_str else 8888
    except ValueError:
        print("Invalid port number!")
        return
    
    # Create and run client
    client = ChatClient(username, server_host, server_port)
    
    try:
        client.run()
    except Exception as e:
        logger.error(f"Client error: {e}")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()