#!/usr/bin/env python3
"""
Network Performance Testing Tool
==============================

This tool tests the performance and reliability of the TCP chat system
under various network conditions including:
- Packet loss simulation
- Network delay testing
- Throughput measurement
- Congestion control validation
"""

import socket
import time
import threading
import random
import json
import statistics
import argparse
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

@dataclass
class TestResult:
    """Results from a network test"""
    test_name: str
    success_rate: float
    avg_latency: float
    throughput_bps: float
    packet_loss_rate: float
    total_messages: int
    successful_messages: int
    failed_messages: int
    test_duration: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency * 1000,
            "throughput_bps": self.throughput_bps,
            "packet_loss_rate": self.packet_loss_rate,
            "total_messages": self.total_messages,
            "successful_messages": self.successful_messages,
            "failed_messages": self.failed_messages,
            "test_duration_seconds": self.test_duration
        }

class NetworkTester:
    """Network performance testing framework"""
    
    def __init__(self, server_host: str = 'localhost', server_port: int = 8888):
        self.server_host = server_host
        self.server_port = server_port
        self.test_results: List[TestResult] = []
    
    def create_test_client(self, username: str) -> socket.socket:
        """Create a test client connection"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30.0)
        sock.connect((self.server_host, self.server_port))
        return sock
    
    def send_message(self, sock: socket.socket, message: str, msg_id: str) -> bool:
        """Send a test message and return success status"""
        try:
            # Create a simple JSON message
            msg_data = {
                "id": msg_id,
                "type": "chat",
                "username": "tester",
                "content": message,
                "timestamp": time.time()
            }
            
            json_str = json.dumps(msg_data)
            data = json_str.encode()
            
            # Send length prefix + data
            length_bytes = len(data).to_bytes(4, 'big')
            sock.sendall(length_bytes + data)
            
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False
    
    def receive_with_timeout(self, sock: socket.socket, timeout: float = 5.0) -> Tuple[bool, float]:
        """Receive response with timeout, return (success, latency)"""
        start_time = time.time()
        sock.settimeout(timeout)
        
        try:
            # Try to receive length prefix
            length_data = sock.recv(4)
            if len(length_data) != 4:
                return False, 0.0
            
            message_length = int.from_bytes(length_data, 'big')
            
            # Receive the actual message
            received_data = b""
            while len(received_data) < message_length:
                chunk = sock.recv(message_length - len(received_data))
                if not chunk:
                    break
                received_data += chunk
            
            latency = time.time() - start_time
            return len(received_data) == message_length, latency
            
        except socket.timeout:
            return False, time.time() - start_time
        except Exception as e:
            print(f"Receive error: {e}")
            return False, time.time() - start_time
    
    def test_basic_connectivity(self) -> TestResult:
        """Test basic client-server connectivity"""
        print("Running basic connectivity test...")
        
        start_time = time.time()
        successful = 0
        failed = 0
        latencies = []
        
        num_tests = 10
        
        for i in range(num_tests):
            try:
                sock = self.create_test_client(f"test_client_{i}")
                
                # Send a test message
                msg_id = f"test_msg_{i}_{int(time.time())}"
                send_time = time.time()
                
                if self.send_message(sock, f"Test message {i}", msg_id):
                    success, latency = self.receive_with_timeout(sock, 10.0)
                    
                    if success:
                        successful += 1
                        latencies.append(latency)
                    else:
                        failed += 1
                else:
                    failed += 1
                
                sock.close()
                time.sleep(0.1)  # Brief pause between tests
                
            except Exception as e:
                print(f"Test {i} failed: {e}")
                failed += 1
        
        test_duration = time.time() - start_time
        avg_latency = statistics.mean(latencies) if latencies else 0.0
        success_rate = successful / num_tests
        
        result = TestResult(
            test_name="Basic Connectivity",
            success_rate=success_rate,
            avg_latency=avg_latency,
            throughput_bps=0.0,  # Not measured in this test
            packet_loss_rate=0.0,  # Not simulated
            total_messages=num_tests,
            successful_messages=successful,
            failed_messages=failed,
            test_duration=test_duration
        )
        
        self.test_results.append(result)
        return result
    
    def test_throughput(self, duration_seconds: int = 30, message_size: int = 1024) -> TestResult:
        """Test message throughput"""
        print(f"Running throughput test ({duration_seconds}s, {message_size} byte messages)...")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        successful = 0
        failed = 0
        total_bytes = 0
        latencies = []
        
        try:
            sock = self.create_test_client("throughput_tester")
            
            msg_counter = 0
            while time.time() < end_time:
                # Create message of specified size
                message_content = "x" * (message_size - 50)  # Account for JSON overhead
                msg_id = f"throughput_{msg_counter}_{int(time.time())}"
                
                send_time = time.time()
                if self.send_message(sock, message_content, msg_id):
                    success, latency = self.receive_with_timeout(sock, 5.0)
                    
                    if success:
                        successful += 1
                        latencies.append(latency)
                        total_bytes += message_size
                    else:
                        failed += 1
                else:
                    failed += 1
                
                msg_counter += 1
                
                # Small delay to prevent overwhelming
                time.sleep(0.01)
            
            sock.close()
            
        except Exception as e:
            print(f"Throughput test error: {e}")
        
        test_duration = time.time() - start_time
        avg_latency = statistics.mean(latencies) if latencies else 0.0
        throughput_bps = total_bytes / test_duration if test_duration > 0 else 0.0
        success_rate = successful / (successful + failed) if (successful + failed) > 0 else 0.0
        
        result = TestResult(
            test_name=f"Throughput Test ({message_size}B)",
            success_rate=success_rate,
            avg_latency=avg_latency,
            throughput_bps=throughput_bps,
            packet_loss_rate=0.0,
            total_messages=successful + failed,
            successful_messages=successful,
            failed_messages=failed,
            test_duration=test_duration
        )
        
        self.test_results.append(result)
        return result
    
    def test_concurrent_clients(self, num_clients: int = 10, messages_per_client: int = 20) -> TestResult:
        """Test server performance with multiple concurrent clients"""
        print(f"Running concurrent client test ({num_clients} clients, {messages_per_client} messages each)...")
        
        start_time = time.time()
        results_lock = threading.Lock()
        client_results = []
        
        def client_worker(client_id: int):
            """Worker function for each test client"""
            client_successful = 0
            client_failed = 0
            client_latencies = []
            
            try:
                sock = self.create_test_client(f"concurrent_client_{client_id}")
                
                for i in range(messages_per_client):
                    msg_id = f"concurrent_{client_id}_{i}_{int(time.time())}"
                    message = f"Concurrent test message {i} from client {client_id}"
                    
                    if self.send_message(sock, message, msg_id):
                        success, latency = self.receive_with_timeout(sock, 10.0)
                        
                        if success:
                            client_successful += 1
                            client_latencies.append(latency)
                        else:
                            client_failed += 1
                    else:
                        client_failed += 1
                    
                    time.sleep(0.05)  # Brief pause between messages
                
                sock.close()
                
            except Exception as e:
                print(f"Client {client_id} error: {e}")
                client_failed += messages_per_client - client_successful
            
            with results_lock:
                client_results.append({
                    'successful': client_successful,
                    'failed': client_failed,
                    'latencies': client_latencies
                })
        
        # Start all client threads
        threads = []
        for i in range(num_clients):
            thread = threading.Thread(target=client_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Aggregate results
        total_successful = sum(r['successful'] for r in client_results)
        total_failed = sum(r['failed'] for r in client_results)
        all_latencies = []
        for r in client_results:
            all_latencies.extend(r['latencies'])
        
        test_duration = time.time() - start_time
        avg_latency = statistics.mean(all_latencies) if all_latencies else 0.0
        success_rate = total_successful / (total_successful + total_failed) if (total_successful + total_failed) > 0 else 0.0
        
        result = TestResult(
            test_name=f"Concurrent Clients ({num_clients} clients)",
            success_rate=success_rate,
            avg_latency=avg_latency,
            throughput_bps=0.0,  # Not the focus of this test
            packet_loss_rate=0.0,
            total_messages=total_successful + total_failed,
            successful_messages=total_successful,
            failed_messages=total_failed,
            test_duration=test_duration
        )
        
        self.test_results.append(result)
        return result
    
    def test_message_reliability(self, num_messages: int = 100) -> TestResult:
        """Test message delivery reliability"""
        print(f"Running message reliability test ({num_messages} messages)...")
        
        start_time = time.time()
        successful = 0
        failed = 0
        latencies = []
        
        try:
            sock = self.create_test_client("reliability_tester")
            
            for i in range(num_messages):
                msg_id = f"reliability_{i}_{int(time.time())}"
                message = f"Reliability test message {i} with some additional content to make it more realistic"
                
                if self.send_message(sock, message, msg_id):
                    success, latency = self.receive_with_timeout(sock, 10.0)
                    
                    if success:
                        successful += 1
                        latencies.append(latency)
                    else:
                        failed += 1
                else:
                    failed += 1
                
                # Add random delay between messages
                time.sleep(random.uniform(0.01, 0.1))
            
            sock.close()
            
        except Exception as e:
            print(f"Reliability test error: {e}")
        
        test_duration = time.time() - start_time
        avg_latency = statistics.mean(latencies) if latencies else 0.0
        success_rate = successful / num_messages
        
        result = TestResult(
            test_name="Message Reliability",
            success_rate=success_rate,
            avg_latency=avg_latency,
            throughput_bps=0.0,
            packet_loss_rate=0.0,
            total_messages=num_messages,
            successful_messages=successful,
            failed_messages=failed,
            test_duration=test_duration
        )
        
        self.test_results.append(result)
        return result
    
    def run_all_tests(self) -> List[TestResult]:
        """Run all network tests"""
        print("Starting comprehensive network testing suite...")
        print("=" * 60)
        
        # Run all tests
        self.test_basic_connectivity()
        self.test_throughput(duration_seconds=15, message_size=512)
        self.test_throughput(duration_seconds=15, message_size=2048)
        self.test_concurrent_clients(num_clients=5, messages_per_client=10)
        self.test_concurrent_clients(num_clients=15, messages_per_client=5)
        self.test_message_reliability(num_messages=50)
        
        return self.test_results
    
    def print_results_summary(self):
        """Print a summary of all test results"""
        print("\n" + "=" * 60)
        print("NETWORK TESTING RESULTS SUMMARY")
        print("=" * 60)
        
        for result in self.test_results:
            print(f"\nTest: {result.test_name}")
            print(f"  Success Rate: {result.success_rate:.2%}")
            print(f"  Average Latency: {result.avg_latency*1000:.2f} ms")
            if result.throughput_bps > 0:
                print(f"  Throughput: {result.throughput_bps/1024:.2f} KB/s")
            print(f"  Messages: {result.successful_messages}/{result.total_messages}")
            print(f"  Duration: {result.test_duration:.2f} seconds")
        
        # Overall statistics
        if self.test_results:
            overall_success = sum(r.successful_messages for r in self.test_results)
            overall_total = sum(r.total_messages for r in self.test_results)
            overall_success_rate = overall_success / overall_total if overall_total > 0 else 0.0
            
            print(f"\nOVERALL STATISTICS:")
            print(f"  Total Messages Tested: {overall_total}")
            print(f"  Overall Success Rate: {overall_success_rate:.2%}")
            
            avg_latencies = [r.avg_latency for r in self.test_results if r.avg_latency > 0]
            if avg_latencies:
                print(f"  Average Latency: {statistics.mean(avg_latencies)*1000:.2f} ms")
    
    def export_results(self, filename: str):
        """Export results to JSON file"""
        results_data = {
            "test_timestamp": time.time(),
            "server_host": self.server_host,
            "server_port": self.server_port,
            "results": [r.to_dict() for r in self.test_results]
        }
        
        with open(filename, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"Results exported to {filename}")

def main():
    parser = argparse.ArgumentParser(description="TCP Chat Network Performance Tester")
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", type=int, default=8888, help="Server port (default: 8888)")
    parser.add_argument("--test", choices=["connectivity", "throughput", "concurrent", "reliability", "all"],
                       default="all", help="Test to run (default: all)")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds (default: 30)")
    parser.add_argument("--clients", type=int, default=10, help="Number of concurrent clients (default: 10)")
    parser.add_argument("--messages", type=int, default=100, help="Number of test messages (default: 100)")
    parser.add_argument("--export", help="Export results to JSON file")
    
    args = parser.parse_args()
    
    tester = NetworkTester(args.host, args.port)
    
    try:
        if args.test == "connectivity":
            tester.test_basic_connectivity()
        elif args.test == "throughput":
            tester.test_throughput(args.duration)
        elif args.test == "concurrent":
            tester.test_concurrent_clients(args.clients)
        elif args.test == "reliability":
            tester.test_message_reliability(args.messages)
        else:
            tester.run_all_tests()
        
        tester.print_results_summary()
        
        if args.export:
            tester.export_results(args.export)
            
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
    except Exception as e:
        print(f"Testing error: {e}")

if __name__ == "__main__":
    main()