#!/usr/bin/env python3
"""
Shared Protocol Definitions for TCP Chat System
==============================================

This module contains shared classes and utilities used by both
the server and client components of the TCP chat system.
"""

import hashlib
import json
import struct
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, Optional

class MessageType(Enum):
    """Enumeration of message types in the chat protocol"""
    CHAT = "chat"
    ACK = "ack"
    HEARTBEAT = "heartbeat"
    JOIN = "join"
    LEAVE = "leave"
    RETRANSMIT = "retransmit"
    SERVER_INFO = "server_info"
    USER_LIST = "user_list"
    PRIVATE_MESSAGE = "private_message"

class CongestionState(Enum):
    """Congestion control states"""
    SLOW_START = "slow_start"
    CONGESTION_AVOIDANCE = "congestion_avoidance"
    FAST_RECOVERY = "fast_recovery"

@dataclass
class Message:
    """
    Core message class for the chat protocol
    
    Attributes:
        msg_id: Unique message identifier
        msg_type: Type of message (from MessageType enum)
        sender: Username of sender
        content: Message content
        timestamp: Unix timestamp when message was created
        checksum: Message integrity checksum
        priority: Message priority (0=low, 1=normal, 2=high)
        sequence_number: Sequence number for ordering
    """
    msg_id: str
    msg_type: MessageType
    sender: str
    content: str
    timestamp: float
    checksum: str = ""
    priority: int = 1
    sequence_number: int = 0
    
    def __post_init__(self):
        if not self.checksum:
            self.checksum = self.calculate_checksum()
    
    def calculate_checksum(self) -> str:
        """Calculate SHA-256 checksum for message integrity"""
        data = f"{self.msg_id}{self.msg_type.value}{self.sender}{self.content}{self.timestamp}{self.priority}{self.sequence_number}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def is_valid(self) -> bool:
        """Verify message integrity using checksum"""
        expected_checksum = self.calculate_checksum()
        return self.checksum == expected_checksum
    
    def to_bytes(self) -> bytes:
        """
        Serialize message to bytes for network transmission
        
        Format: [4 bytes length][JSON data]
        """
        data = asdict(self)
        data['msg_type'] = data['msg_type'].value
        json_data = json.dumps(data, separators=(',', ':')).encode('utf-8')
        return struct.pack('!I', len(json_data)) + json_data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Message':
        """
        Deserialize message from bytes
        
        Args:
            data: Raw bytes containing JSON message data
            
        Returns:
            Message object
            
        Raises:
            ValueError: If data is invalid or corrupted
        """
        try:
            json_data = json.loads(data.decode('utf-8'))
            json_data['msg_type'] = MessageType(json_data['msg_type'])
            return cls(**json_data)
        except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid message data: {e}")
    
    def to_display_string(self) -> str:
        """Format message for display in chat interface"""
        timestamp_str = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        
        if self.msg_type == MessageType.CHAT:
            return f"[{timestamp_str}] {self.sender}: {self.content}"
        elif self.msg_type == MessageType.PRIVATE_MESSAGE:
            return f"[{timestamp_str}] [PRIVATE] {self.sender}: {self.content}"
        elif self.msg_type == MessageType.JOIN:
            return f"[{timestamp_str}] *** {self.sender} joined the chat ***"
        elif self.msg_type == MessageType.LEAVE:
            return f"[{timestamp_str}] *** {self.sender} left the chat ***"
        else:
            return f"[{timestamp_str}] [{self.msg_type.value.upper()}] {self.content}"

class NetworkStats:
    """Network statistics tracking"""
    
    def __init__(self):
        self.bytes_sent = 0
        self.bytes_received = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.acks_sent = 0
        self.acks_received = 0
        self.retransmissions = 0
        self.checksum_errors = 0
        self.connection_time = time.time()
        self.last_activity = time.time()
    
    def record_sent(self, message: Message, byte_count: int):
        """Record a sent message"""
        self.bytes_sent += byte_count
        self.messages_sent += 1
        if message.msg_type == MessageType.ACK:
            self.acks_sent += 1
        self.last_activity = time.time()
    
    def record_received(self, message: Message, byte_count: int):
        """Record a received message"""
        self.bytes_received += byte_count
        self.messages_received += 1
        if message.msg_type == MessageType.ACK:
            self.acks_received += 1
        self.last_activity = time.time()
    
    def record_retransmission(self):
        """Record a message retransmission"""
        self.retransmissions += 1
    
    def record_checksum_error(self):
        """Record a checksum validation error"""
        self.checksum_errors += 1
    
    def get_uptime(self) -> float:
        """Get connection uptime in seconds"""
        return time.time() - self.connection_time
    
    def get_throughput(self) -> Dict[str, float]:
        """Calculate throughput statistics"""
        uptime = self.get_uptime()
        if uptime == 0:
            return {"sent_bps": 0, "received_bps": 0, "sent_mps": 0, "received_mps": 0}
        
        return {
            "sent_bps": self.bytes_sent / uptime,
            "received_bps": self.bytes_received / uptime,
            "sent_mps": self.messages_sent / uptime,
            "received_mps": self.messages_received / uptime
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary"""
        throughput = self.get_throughput()
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "acks_sent": self.acks_sent,
            "acks_received": self.acks_received,
            "retransmissions": self.retransmissions,
            "checksum_errors": self.checksum_errors,
            "uptime_seconds": self.get_uptime(),
            "throughput": throughput
        }

def create_ack_message(sender: str, ack_for_msg_id: str, sequence_number: int = 0) -> Message:
    """
    Create an ACK message for a given message ID
    
    Args:
        sender: Username of ACK sender
        ack_for_msg_id: Message ID being acknowledged
        sequence_number: Sequence number for the ACK
        
    Returns:
        ACK Message object
    """
    import random
    
    return Message(
        msg_id=f"ack_{int(time.time())}_{random.randint(1000, 9999)}",
        msg_type=MessageType.ACK,
        sender=sender,
        content=json.dumps({"ack_for": ack_for_msg_id}),
        timestamp=time.time(),
        priority=2,  # High priority for ACKs
        sequence_number=sequence_number
    )

def create_heartbeat_message(sender: str, content: str = "ping") -> Message:
    """
    Create a heartbeat message
    
    Args:
        sender: Username of heartbeat sender
        content: Heartbeat content (usually "ping" or "pong")
        
    Returns:
        Heartbeat Message object
    """
    import random
    
    return Message(
        msg_id=f"heartbeat_{int(time.time())}_{random.randint(1000, 9999)}",
        msg_type=MessageType.HEARTBEAT,
        sender=sender,
        content=content,
        timestamp=time.time(),
        priority=2  # High priority for heartbeats
    )

def create_chat_message(sender: str, content: str, sequence_number: int = 0) -> Message:
    """
    Create a chat message
    
    Args:
        sender: Username of message sender
        content: Chat message content
        sequence_number: Sequence number for ordering
        
    Returns:
        Chat Message object
    """
    import random
    
    return Message(
        msg_id=f"chat_{int(time.time())}_{random.randint(1000, 9999)}",
        msg_type=MessageType.CHAT,
        sender=sender,
        content=content,
        timestamp=time.time(),
        sequence_number=sequence_number
    )

def validate_username(username: str) -> bool:
    """
    Validate username format
    
    Args:
        username: Username to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not username:
        return False
    
    # Check length
    if len(username) < 1 or len(username) > 32:
        return False
    
    # Check allowed characters (alphanumeric, underscore, hyphen)
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if not all(c in allowed_chars for c in username):
        return False
    
    # Cannot start with hyphen
    if username.startswith('-'):
        return False
    
    return True

class ProtocolError(Exception):
    """Base exception for protocol-related errors"""
    pass

class MessageValidationError(ProtocolError):
    """Exception raised when message validation fails"""
    pass

class ChecksumMismatchError(ProtocolError):
    """Exception raised when message checksum doesn't match"""
    pass

# Protocol constants
PROTOCOL_VERSION = "1.0"
MAX_MESSAGE_SIZE = 65536  # 64KB
DEFAULT_PORT = 8888
HEARTBEAT_INTERVAL = 15  # seconds
ACK_TIMEOUT = 5  # seconds
MAX_RETRANSMISSIONS = 3
CONGESTION_WINDOW_INITIAL = 1
SLOW_START_THRESHOLD = 64