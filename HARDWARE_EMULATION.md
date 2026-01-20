# Hardware Emulation Guide

This guide explains how to use hardware emulators for testing the car wash terminal system without physical hardware.

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# Start emulators
docker-compose -f docker-compose-emulators.yml up -d

# Check status
docker-compose -f docker-compose-emulators.yml ps

# View logs
docker-compose -f docker-compose-emulators.yml logs -f

# Stop emulators
docker-compose -f docker-compose-emulators.yml down
```

### Option 2: Helper Script

```bash
# Start emulators (auto-detects Docker or standalone)
./emulators/start_emulators.sh
```

### Option 3: Standalone Python

```bash
# Install dependencies
pip install pymodbus==3.5.2

# Start PLC emulator
python emulators/modbus_plc_emulator.py --port 5020 &

# Start POS emulator
python emulators/vendotek_pos_emulator.py --port 4001 &
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Main Application                        │
│  (Django + WebSocket + API)                              │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
               │ Modbus TCP           │ TCP Socket
               │ (Port 502/5020)     │ (Port 4001)
               │                      │
       ┌───────▼────────┐    ┌───────▼────────┐
       │  PLC Emulator  │    │  POS Emulator  │
       │  (Modbus TCP)  │    │  (Vendotek)    │
       └────────────────┘    └────────────────┘
```

## Configuration

### 1. Update Environment Variables

Create or update `.env` file:

```env
# PLC Configuration
DEFAULT_HOST_PLC=localhost      # Use 'plc-emulator' if in Docker network
DEFAULT_PORT_PLC=5020           # Use 502 if in Docker network

# POS Configuration (update in Django admin)
# VendotekServerConfig:
#   ip_address: localhost (or pos-emulator in Docker)
#   port: 4001
```

### 2. Connect Main App to Emulators

#### If using Docker for main app:

Update `docker-compose.yml`:

```yaml
services:
  web:
    # ... existing config ...
    networks:
      - app-network
      - hardware-emulators  # Add this

networks:
  app-network:
    driver: bridge
  hardware-emulators:
    external: true
    name: hardware-emulators
```

Then use service names in `.env`:
```env
DEFAULT_HOST_PLC=plc-emulator
DEFAULT_PORT_PLC=502
```

#### If running main app locally:

Use `localhost` with mapped ports:
```env
DEFAULT_HOST_PLC=localhost
DEFAULT_PORT_PLC=5020
```

## Testing

### Test PLC Connection

```python
from orders.modbus_client import ModbusClient

client = ModbusClient('localhost', 5020, 10)
if client.connect():
    # Read program 1
    program = client.read_program('Program1')
    print(f"Program 1: {program}")
    
    # Read prices
    prices = client.read_all_prices()
    print(f"Prices: {prices}")
    
    client.disconnect()
```

### Test POS Terminal

```python
from orders.vendotek import VendotekClient

client = VendotekClient('localhost', 4001)
if client.connect():
    response = client.process_payment(200)
    print(f"Payment: {response.success}")
    print(f"Amount: {response.approved_amount}")
    client.disconnect()
```

### Test Full Flow

1. Start emulators
2. Start main application
3. Create an order via API
4. Process payment (will use POS emulator)
5. Start car wash (will use PLC emulator)

## Emulator Features

### PLC Emulator

- ✅ Simulates 5 car wash programs
- ✅ Simulates prices (regular and loyalty)
- ✅ Responds to start/stop commands
- ✅ Tracks wash status
- ✅ Simulates cash acceptor

**Default Programs:**
- Program 1: Basic (200₽ / 180₽ loyalty)
- Program 2: Standard (300₽ / 270₽ loyalty)
- Program 3: Premium (500₽ / 450₽ loyalty)
- Program 4: Express (150₽ / 135₽ loyalty)
- Program 5: Deluxe (700₽ / 630₽ loyalty)

### POS Emulator

- ✅ Handles IDL, VRP, FIN, ABR messages
- ✅ Auto-approves payments (configurable)
- ✅ Simulates payment flow
- ✅ Tracks operation numbers

**Payment Flow:**
1. IDL → Get terminal status
2. VRP → Request payment (auto-approved)
3. FIN → Finalize payment
4. IDL → Confirm completion

## Advanced Usage

### Customize PLC Emulator

Edit `emulators/modbus_plc_emulator.py`:

```python
# Change default prices
input_registers[30] = 250  # Program 1 price

# Change program steps
input_registers[0:3] = [1, 3, 4, 7]  # Different wash sequence
```

### Customize POS Emulator

```python
# Disable auto-approval (for testing rejections)
emulator.set_auto_approve(False)

# Add approval delay
emulator.approval_delay = 5.0  # 5 second delay
```

### Simulate Errors

You can modify emulator code to:
- Return connection errors
- Return invalid responses
- Simulate timeouts
- Simulate device failures

## Troubleshooting

### Can't Connect to PLC Emulator

1. **Check if emulator is running:**
   ```bash
   docker ps | grep plc-emulator
   # or
   ps aux | grep modbus_plc_emulator
   ```

2. **Check port availability:**
   ```bash
   netstat -an | grep 5020
   # or
   lsof -i :5020
   ```

3. **Check firewall:**
   ```bash
   # macOS
   sudo pfctl -s rules
   ```

4. **Check network configuration:**
   - If using Docker: ensure networks are connected
   - If using standalone: ensure using correct host/port

### Payment Always Fails

1. **Check POS emulator logs:**
   ```bash
   docker-compose -f docker-compose-emulators.yml logs pos-emulator
   ```

2. **Verify auto-approve is enabled:**
   - Check emulator code or environment variables

3. **Check connection:**
   ```python
   import socket
   s = socket.socket()
   s.connect(('localhost', 4001))
   s.close()
   ```

### Wrong Register Values

1. **Verify register addresses:**
   - Check `modbus_config.py` for correct addresses
   - Ensure emulator uses same addresses

2. **Check emulator initialization:**
   - View emulator startup logs
   - Verify default values are set correctly

## Best Practices

1. **Separate Networks**: Keep emulators isolated from production
2. **Port Mapping**: Use non-standard ports (5020, 4001) to avoid conflicts
3. **Environment Variables**: Use env vars for all configuration
4. **Health Checks**: Monitor emulator health in CI/CD
5. **State Reset**: Reset emulator state between test runs
6. **Logging**: Enable detailed logging for debugging

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Start emulators
  run: |
    docker-compose -f docker-compose-emulators.yml up -d
    sleep 5  # Wait for emulators to start

- name: Run tests
  run: |
    pytest tests/ --env-file=.env.test

- name: Stop emulators
  run: |
    docker-compose -f docker-compose-emulators.yml down
```

## See Also

- [emulators/README.md](emulators/README.md) - Detailed emulator documentation
- [MODBUS_INTEGRATION.md](MODBUS_INTEGRATION.md) - Modbus integration guide
- [README.md](README.md) - Main project documentation

