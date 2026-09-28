#!/usr/bin/env python3
"""
Vendotek POS Terminal Emulator
Simulates a Vendotek payment terminal for testing
"""
import socket
import struct
import threading
import logging
import time
from typing import Optional, Dict
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PaymentState:
    """State of a payment transaction"""
    operation_number: int = 1
    current_amount: int = 0
    approved: bool = False
    timeout: int = 60


class VendotekPOSEmulator:
    """Emulates Vendotek POS terminal"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 4001):
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.payment_state = PaymentState()
        self.auto_approve = True  # Auto-approve payments by default
        self.approval_delay = 1.0  # Delay before approving (seconds)
        
    def start(self):
        """Start the POS terminal emulator server"""
        if self.running:
            logger.warning("Server is already running")
            return
        
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            
            logger.info(f"✅ Vendotek POS emulator started on {self.host}:{self.port}")
            
            # Start accepting connections
            accept_thread = threading.Thread(target=self._accept_connections, daemon=True)
            accept_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start POS emulator: {e}")
            self.running = False
            raise
    
    def _accept_connections(self):
        """Accept incoming connections"""
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                logger.info(f"New connection from {address}")
                
                # Handle each client in a separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")
    
    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """Handle a client connection"""
        try:
            while self.running:
                # Receive message length (2 bytes)
                length_data = client_socket.recv(2)
                if len(length_data) < 2:
                    break
                
                message_length = struct.unpack('>H', length_data)[0]
                
                # Receive message body
                message_data = client_socket.recv(message_length)
                if len(message_data) < message_length:
                    break
                
                # Parse and handle message
                response = self._handle_message(message_data)
                
                if response:
                    client_socket.sendall(response)
                    
        except Exception as e:
            logger.error(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
            logger.info(f"Client {address} disconnected")
    
    def _handle_message(self, message: bytes) -> Optional[bytes]:
        """Handle incoming message and return response"""
        if len(message) < 4:
            return None
        
        # Check header (0x96 0xFB)
        if message[0] != 0x96 or message[1] != 0xFB:
            logger.warning(f"Invalid message header: {message[0]:02x} {message[1]:02x}")
            return None
        
        # Parse TLV fields
        tlvs = self._parse_tlvs(message[2:])
        
        # Get message type
        message_type = tlvs.get(0x01, b'').decode('ascii', errors='ignore')
        logger.info(f"Received message type: {message_type}")
        
        if message_type == "IDL":
            return self._handle_idl(tlvs)
        elif message_type == "VRP":
            return self._handle_vrp(tlvs)
        elif message_type == "FIN":
            return self._handle_fin(tlvs)
        elif message_type == "ABR":
            return self._handle_abr(tlvs)
        else:
            logger.warning(f"Unknown message type: {message_type}")
            return None
    
    def _parse_tlvs(self, data: bytes) -> Dict[int, bytes]:
        """Parse TLV (Type-Length-Value) fields"""
        tlvs = {}
        i = 0
        while i < len(data) - 1:
            param_id = data[i]
            param_len = data[i + 1]
            
            if i + 2 + param_len > len(data):
                break
            
            param_value = data[i + 2:i + 2 + param_len]
            tlvs[param_id] = param_value
            
            i += 2 + param_len
        
        return tlvs
    
    def _handle_idl(self, tlvs: Dict[int, bytes]) -> bytes:
        """Handle IDL (Idle) message"""
        logger.info("Handling IDL message")
        
        # Build response
        response_tlvs = bytearray()
        
        # Message type: IDL
        response_tlvs.extend((0x01, 0x03))
        response_tlvs.extend(b'IDL')
        
        # Operation number
        op_num_str = str(self.payment_state.operation_number)
        response_tlvs.extend((0x03, len(op_num_str)))
        response_tlvs.extend(op_num_str.encode('ascii'))
        
        # Local time (simulated)
        local_time = time.strftime("%Y%m%d%H%M%S")
        response_tlvs.extend((0x11, len(local_time)))
        response_tlvs.extend(local_time.encode('ascii'))
        
        return self._build_message(response_tlvs)
    
    def _handle_vrp(self, tlvs: Dict[int, bytes]) -> bytes:
        """Handle VRP (Payment Request) message"""
        # Extract amount
        amount_str = tlvs.get(0x04, b'').decode('ascii', errors='ignore')
        operation_number_str = tlvs.get(0x03, b'').decode('ascii', errors='ignore')
        
        try:
            amount_minor = int(amount_str)  # Amount in kopecks
            amount_rubles = amount_minor / 100
            self.payment_state.current_amount = int(amount_rubles)
            self.payment_state.operation_number = int(operation_number_str) if operation_number_str else self.payment_state.operation_number
        except ValueError:
            logger.error(f"Invalid amount: {amount_str}")
            return self._build_error_message("Invalid amount")
        
        logger.info(f"Handling VRP: {amount_rubles} rubles, operation #{self.payment_state.operation_number}")
        
        # Build response
        response_tlvs = bytearray()
        
        # Message type: VRP response
        response_tlvs.extend((0x01, 0x03))
        response_tlvs.extend(b'VRP')
        
        # Operation number
        op_num_str = str(self.payment_state.operation_number)
        response_tlvs.extend((0x03, len(op_num_str)))
        response_tlvs.extend(op_num_str.encode('ascii'))
        
        if self.auto_approve:
            # Approve payment
            approved_amount_minor = str(int(amount_rubles * 100))
            response_tlvs.extend((0x04, len(approved_amount_minor)))
            response_tlvs.extend(approved_amount_minor.encode('ascii'))
            
            # Timeout
            timeout_str = str(self.payment_state.timeout)
            response_tlvs.extend((0x06, len(timeout_str)))
            response_tlvs.extend(timeout_str.encode('ascii'))
            
            self.payment_state.approved = True
            logger.info(f"✅ Payment approved: {amount_rubles} rubles")
        else:
            # Reject payment (for testing rejection scenarios)
            response_tlvs.extend((0x04, 0x01))
            response_tlvs.extend(b'0')
            logger.info(f"❌ Payment rejected: {amount_rubles} rubles")
        
        return self._build_message(response_tlvs)
    
    def _handle_fin(self, tlvs: Dict[int, bytes]) -> bytes:
        """Handle FIN (Finalize) message"""
        logger.info("Handling FIN message")
        
        # Build response
        response_tlvs = bytearray()
        
        # Message type: FIN
        response_tlvs.extend((0x01, 0x03))
        response_tlvs.extend(b'FIN')
        
        # Operation number
        op_num_str = str(self.payment_state.operation_number)
        response_tlvs.extend((0x03, len(op_num_str)))
        response_tlvs.extend(op_num_str.encode('ascii'))
        
        # Amount
        amount_minor = str(int(self.payment_state.current_amount * 100))
        response_tlvs.extend((0x04, len(amount_minor)))
        response_tlvs.extend(amount_minor.encode('ascii'))
        
        # Increment operation number for next transaction
        self.payment_state.operation_number += 1
        self.payment_state.approved = False
        self.payment_state.current_amount = 0
        
        return self._build_message(response_tlvs)
    
    def _handle_abr(self, tlvs: Dict[int, bytes]) -> bytes:
        """Handle ABR (Abort) message"""
        logger.info("Handling ABR message (payment cancellation)")
        
        # Reset payment state
        self.payment_state.approved = False
        self.payment_state.current_amount = 0
        
        # Build response
        response_tlvs = bytearray()
        
        # Message type: ABR
        response_tlvs.extend((0x01, 0x03))
        response_tlvs.extend(b'ABR')
        
        # Operation number
        op_num_str = str(self.payment_state.operation_number)
        response_tlvs.extend((0x03, len(op_num_str)))
        response_tlvs.extend(op_num_str.encode('ascii'))
        
        return self._build_message(response_tlvs)
    
    def _build_message(self, tlvs: bytearray) -> bytes:
        """Build message frame: [len(2)][0x97 0xFB][TLVs...]"""
        body = bytearray()
        body.extend((0x97, 0xFB))  # Response header
        body.extend(tlvs)
        length = len(body)
        length_bytes = length.to_bytes(2, 'big')
        return bytes(length_bytes + body)
    
    def _build_error_message(self, error: str) -> bytes:
        """Build error message"""
        response_tlvs = bytearray()
        response_tlvs.extend((0x01, 0x03))
        response_tlvs.extend(b'ERR')
        error_bytes = error.encode('ascii')
        response_tlvs.extend((0xFF, len(error_bytes)))
        response_tlvs.extend(error_bytes)
        return self._build_message(response_tlvs)
    
    def stop(self):
        """Stop the POS terminal emulator"""
        logger.info("Stopping Vendotek POS emulator...")
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
    
    def set_auto_approve(self, auto_approve: bool):
        """Set whether to auto-approve payments"""
        self.auto_approve = auto_approve
        logger.info(f"Auto-approve set to: {auto_approve}")
    
    def get_status(self) -> Dict:
        """Get current emulator status"""
        return {
            'running': self.running,
            'host': self.host,
            'port': self.port,
            'auto_approve': self.auto_approve,
            'current_payment': {
                'amount': self.payment_state.current_amount,
                'approved': self.payment_state.approved,
                'operation_number': self.payment_state.operation_number
            }
        }


def main():
    """Main entry point for standalone execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Vendotek POS Terminal Emulator')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=4001, help='Port to bind to')
    parser.add_argument('--no-auto-approve', action='store_true', help='Disable auto-approval of payments')
    
    args = parser.parse_args()
    
    emulator = VendotekPOSEmulator(host=args.host, port=args.port)
    emulator.set_auto_approve(not args.no_auto_approve)
    
    try:
        emulator.start()
        logger.info("Emulator running. Press Ctrl+C to stop.")
        while emulator.running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping emulator...")
        emulator.stop()


if __name__ == "__main__":
    main()

