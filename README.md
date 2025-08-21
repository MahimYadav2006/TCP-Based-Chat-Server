# TCP Chat Server with Congestion Control & Packet Loss Handling

A sophisticated TCP-based chat server implementation featuring advanced networking concepts including congestion control, packet loss handling, flow control, and reliability mechanisms.

## 🚀 Features

### Core Functionality
- **Multi-threaded TCP chat server** supporting multiple concurrent clients
- **Real-time messaging** with broadcast and private message capabilities
- **User authentication and management** with username validation
- **Graceful connection handling** with automatic cleanup

### Advanced Networking Features
- **Custom congestion control algorithm** (TCP Reno-inspired)
- **Packet loss detection and recovery** with automatic retransmission
- **Flow control mechanisms** to prevent buffer overflow
- **Message acknowledgment system** with timeout handling
- **Heartbeat mechanism** for connection monitoring
- **Message integrity verification** using checksums

### Performance & Reliability
- **Network simulation capabilities** for testing under adverse conditions
- **Comprehensive statistics tracking** for performance monitoring
- **Automatic reconnection** on client side
- **Thread-safe operations** with proper synchronization
- **Configurable timeouts and thresholds**

## 📁 Project Structure

```
tcp_chat_system/
├── tcp_chat_server.py      # Main server implementation
├── tcp_chat_client.py      # Client application
├── chat_protocol.py        # Shared protocol definitions
├── server_admin_tool.py    # Server administration utility
├── network_tester.py       # Performance testing tool
├── README.md              # This documentation
```

## 🛠 Installation & Setup

### Requirements
- Python 3.7 or higher
- No external dependencies required (uses only Python standard library)

### Installation
1. Clone or download the project files
2. Ensure Python 3.7+ is installed
3. All files should be in the same directory

### Quick Start
```bash
# Start the server
python tcp_chat_server.py

# In another terminal, start a client
python tcp_chat_client.py

# Optional: Run performance tests
python network_tester.py
```

## 📖 Usage Guide

### Starting the Server

#### Basic Usage
```bash
python tcp_chat_server.py
```
The server will start on `localhost:8888` by default.

#### Advanced Options
```python
# In your code or interactive Python session
from tcp_chat_server import ChatServer

server = ChatServer(host='0.0.0.0', port=8888)

# Optional: Configure network simulation for testing
server.set_network_conditions(packet_loss_rate=0.1, delay=0.05)

server.start()
```

### Connecting Clients

#### Interactive Client
```bash
python tcp_chat_client.py
```
Follow the prompts to enter username and server details.

#### Programmatic Client
```python
from tcp_chat_client import ChatClient

client = ChatClient("username", "localhost", 8888)
if client.connect():
    client.run()
```

### Client Commands
- Type messages and press Enter to send
- `/quit` - Leave the chat
- `/stats` - Show connection statistics

### Server Administration

#### Using the Admin Tool
```bash
python server_admin_tool.py --host localhost --port 8889
```

#### Available Admin Commands
- `stats` - Show server statistics
- `clients` - List connected clients  
- `kick <client_id>` - Disconnect a client
- `broadcast <message>` - Send message to all clients
- `simulate <loss%> <delay_ms>` - Configure network simulation
- `shutdown` - Gracefully shutdown server

#### Monitor Mode
```bash
python server_admin_tool.py --mode monitor --interval 5
```

### Performance Testing

#### Run All Tests
```bash
python network_tester.py --host localhost --port 8888
```

#### Specific Tests
```bash
# Test basic connectivity
python network_tester.py --test connectivity

# Test throughput for 60 seconds
python network_tester.py --test throughput --duration 60

# Test with 20 concurrent clients
python network_tester.py --test concurrent --clients 20

# Export results to JSON
python network_tester.py --export results.json
```

## 🔧 Architecture Details

### Congestion Control Algorithm

The implementation uses a TCP Reno-inspired congestion control algorithm:

#### Slow Start Phase
- Congestion window starts at 1 MSS
- Window doubles every RTT until threshold reached
- Fast growth to find available bandwidth

#### Congestion Avoidance Phase  
- Linear growth: cwnd += 1/cwnd per ACK
- Conservative approach to avoid congestion
- Maintains stable throughput

#### Fast Recovery Phase
- Triggered by 3 duplicate ACKs
- Avoids slow start after packet loss
- Maintains higher throughput during recovery

### Packet Loss Handling

#### Detection Methods
- **Timeout-based**: Messages not acknowledged within RTO
- **Duplicate ACK**: Three duplicate ACKs indicate loss
- **Checksum validation**: Detect corrupted messages

#### Recovery Mechanisms
- **Automatic retransmission** with exponential backoff
- **Selective retransmission** of only lost packets  
- **Congestion window adjustment** to reduce load

### Message Protocol

#### Message Structure
```json
{
  "msg_id": "unique_identifier",
  "msg_type": "chat|ack|heartbeat|join|leave",
  "sender": "username",
  "content": "message_content", 
  "timestamp": 1234567890.123,
  "checksum": "integrity_hash",
  "priority": 1,
  "sequence_number": 42
}
```

#### Wire Format
```
[4 bytes: message length][JSON message data]
```

### Threading Model

#### Server Threads
- **Main thread**: Accept new connections
- **Client handler threads**: One per connected client
- **Sender worker threads**: Manage outgoing messages with congestion control
- **Heartbeat thread**: Monitor connection health

#### Client Threads  
- **Receiver thread**: Handle incoming messages
- **Sender thread**: Send outgoing messages with flow control
- **Input thread**: Handle user input

## 🧪 Testing & Validation

### Network Conditions Testing

The system includes built-in simulation capabilities:

```python
# Simulate 10% packet loss and 50ms delay
server.set_network_conditions(packet_loss_rate=0.1, delay=0.05)
```

### Performance Metrics

The system tracks comprehensive statistics:
- **Throughput**: Messages/bytes per second
- **Latency**: Round-trip time measurements  
- **Success rates**: Message delivery reliability
- **Congestion control**: Window size, RTO values
- **Resource usage**: Memory, CPU, network utilization

### Test Scenarios

1. **Basic Connectivity**: Verify client-server communication
2. **Throughput Testing**: Measure maximum message rates
3. **Concurrent Clients**: Test scalability with multiple users
4. **Reliability Testing**: Validate message delivery under stress
5. **Network Simulation**: Performance under packet loss/delay

## 🔍 Monitoring & Debugging

### Built-in Logging

The system uses Python's logging module with configurable levels:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Statistics Dashboard

Access real-time statistics via the admin interface:
- Connected clients and their states
- Message throughput and latency
- Congestion control parameters
- Network simulation settings

### Performance Profiling

Use the network tester for detailed performance analysis:
```bash
python network_tester.py --export detailed_results.json
```

## 🚨 Error Handling & Recovery

### Connection Failures
- **Automatic reconnection** with exponential backoff
- **Connection pooling** for improved reliability
- **Graceful degradation** when server unavailable

### Message Failures
- **Timeout detection** with configurable thresholds
- **Automatic retransmission** with congestion control
- **Duplicate detection** to prevent message replay

### Resource Management
- **Memory leak prevention** with proper cleanup
- **Thread lifecycle management** 
- **Socket resource recycling**

## 🔧 Configuration Options

### Server Configuration
```python
class ServerConfig:
    HOST = 'localhost'
    PORT = 8888
    MAX_CLIENTS = 100
    HEARTBEAT_INTERVAL = 15  # seconds
    ACK_TIMEOUT = 5  # seconds
    MAX_RETRANSMISSIONS = 3
    BUFFER_SIZE = 4096
```

### Client Configuration  
```python
class ClientConfig:
    RECONNECT_ATTEMPTS = 5
    RECONNECT_DELAY = 2.0  # seconds
    SEND_TIMEOUT = 10.0  # seconds
    RECEIVE_TIMEOUT = 1.0  # seconds
```

### Congestion Control Parameters
```python
class CongestionConfig:
    INITIAL_CWND = 1.0
    SLOW_START_THRESHOLD = 64.0
    MIN_RTO = 1.0  # seconds
    MAX_RTO = 60.0  # seconds
    RTT_ALPHA = 0.125  # SRTT smoothing
    RTT_BETA = 0.25   # RTTVAR smoothing
```

## 🎯 Use Cases & Applications

### Educational Purposes
- **Network programming concepts** demonstration
- **TCP/IP protocol understanding**
- **Concurrent programming** with threads
- **System design principles**

### Real-world Applications
- **Corporate chat systems** with reliability requirements
- **Gaming communication** with low-latency needs  
- **IoT messaging** with congestion control
- **Distributed system communication**

### Research & Development
- **Congestion control algorithm** experimentation
- **Network condition simulation**
- **Performance optimization** research
- **Protocol design** validation

## 🔒 Security Considerations

### Current Implementation
- **Message integrity** via checksums
- **Basic input validation**
- **Connection limit** controls
- **Resource usage** monitoring

### Recommended Enhancements
- **TLS/SSL encryption** for data privacy
- **User authentication** with credentials
- **Rate limiting** to prevent abuse
- **Input sanitization** for security

## 📈 Performance Characteristics

### Typical Performance Metrics
- **Throughput**: 1000-5000 messages/second (depending on hardware)
- **Latency**: 1-10ms on localhost, 50-200ms over WAN
- **Scalability**: 100+ concurrent clients per server
- **Memory usage**: ~1-5MB per client connection
- **CPU usage**: Low (<10%) under normal load

### Scaling Considerations
- **Horizontal scaling**: Multiple server instances
- **Load balancing** for high availability
- **Database integration** for persistent storage
- **Caching mechanisms** for improved performance

## 🛠 Troubleshooting

### Common Issues

#### Connection Problems
```
Error: Connection refused
Solution: Ensure server is running and accessible
```

#### Message Loss
```
Error: High packet loss rate
Solution: Check network conditions, adjust congestion control parameters
```

#### Performance Issues
```  
Error: Low throughput
Solution: Increase congestion window, optimize message size
```

### Debug Commands
```bash
# Enable debug logging
export PYTHONPATH=$PYTHONPATH:.
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"

# Test network connectivity
python network_tester.py --test connectivity --host <server>

# Monitor server statistics  
python server_admin_tool.py --mode monitor
```

## 🔮 Future Enhancements

### Planned Features
- **SSL/TLS encryption** for secure communication
- **Database persistence** for chat history
- **Web interface** for administration
- **REST API** for integration
- **Mobile client** support

### Advanced Networking
- **Custom congestion control algorithms** (BBR, CUBIC)
- **Multi-path TCP** support
- **Quality of Service** (QoS) management
- **IPv6 support**

### Scalability Improvements
- **Microservices architecture**
- **Container deployment** (Docker/Kubernetes)
- **Cloud integration** (AWS, Azure, Google Cloud)
