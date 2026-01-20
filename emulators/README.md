# Hardware Emulators

This directory contains emulators for hardware devices used in the car wash terminal system. These emulators allow you to test the system without physical hardware.

## Overview

The emulators simulate:
- **PLC (Programmable Logic Controller)**: OWEN PLC via Modbus TCP protocol
- **POS Terminal**: Vendotek payment terminal via custom TCP protocol

## Quick Start

### Using Docker Compose (Recommended)

1. Start all emulators:
```bash
docker-compose -f docker-compose-emulators.yml up -d
```

2. Check status:
```bash
docker-compose -f docker-compose-emulators.yml ps
```

3. View logs:
```bash
docker-compose -f docker-compose-emulators.yml logs -f
```

4. Stop emulators:
```bash
docker-compose -f docker-compose-emulators.yml down
```

### Running Standalone

#### PLC Emulator

```bash
# Install dependencies
pip install pymodbus==3.5.2

# Run emulator
python emulators/modbus_plc_emulator.py --host 0.0.0.0 --port 502
```

#### POS Terminal Emulator

```bash
# Run emulator (no external dependencies needed)
python emulators/vendotek_pos_emulator.py --host 0.0.0.0 --port 4001

# To disable auto-approval (for testing rejections):
python emulators/vendotek_pos_emulator.py --no-auto-approve
```

## Configuration

### Connecting Main Application to Emulators

Update your `.env` file to point to the emulators:

```env
# PLC Emulator (when running in Docker, use service name)
DEFAULT_HOST_PLC=plc-emulator
DEFAULT_PORT_PLC=502

# Or if running standalone on localhost:
# DEFAULT_HOST_PLC=localhost
# DEFAULT_PORT_PLC=5020  # If using non-standard port

# POS Terminal Emulator
# Update VendotekServerConfig in Django admin or database:
# ip_address: pos-emulator (Docker) or localhost (standalone)
# port: 4001
```

### Docker Network Configuration

When running both the main application and emulators in Docker:

1. Connect main app to emulator network:
```yaml
# In docker-compose.yml, add to web service:
networks:
  - app-network
  - hardware-emulators  # Add this network
```

2. Or use host network mode for emulators (simpler for local development):
```yaml
# In docker-compose-emulators.yml, add to each service:
network_mode: "host"
```

## PLC Emulator Details

### Simulated Registers

The PLC emulator simulates:

- **Input Registers** (read-only):
  - Programs 1-5: Addresses 0-14, 35-49, 70-84, 105-119, 140-154
  - Prices: Addresses 30, 31, 65, 66, 100, 101, 135, 136, 170, 171

- **Holding Registers** (read-write):
  - Cash register: Address 200 (simulating address 16388)

- **Coils** (read-write):
  - Start commands: Addresses 0, 1, 3, 4, 5 (Programs 1-5)

- **Discrete Inputs** (read-only):
  - Wash status: Address 0 (true = washing in progress)

### Default Programs

- **Program 1**: Basic wash (200 rubles, 180 loyalty)
- **Program 2**: Standard wash (300 rubles, 270 loyalty)
- **Program 3**: Premium wash (500 rubles, 450 loyalty)
- **Program 4**: Express wash (150 rubles, 135 loyalty)
- **Program 5**: Deluxe wash (700 rubles, 630 loyalty)

### Testing PLC Emulator

```python
from pymodbus.client import ModbusTcpClient

# Connect to emulator
client = ModbusTcpClient('localhost', 5020)  # or 502 if using Docker
client.connect()

# Read program 1
result = client.read_input_registers(0, 15)
print(f"Program 1: {result.registers}")

# Read price
price = client.read_input_registers(30, 1)
print(f"Price 1: {price.registers[0]}")

# Start program 1
client.write_coil(0, True)

# Check wash status
status = client.read_discrete_inputs(0, 1)
print(f"Wash in progress: {status.bits[0]}")

client.close()
```

## POS Terminal Emulator Details

### Supported Messages

- **IDL** (Idle): Terminal status check
- **VRP** (Payment Request): Initiate payment
- **FIN** (Finalize): Complete payment
- **ABR** (Abort): Cancel payment

### Payment Flow

1. Client sends IDL → Emulator responds with status
2. Client sends VRP with amount → Emulator approves/rejects
3. Client sends FIN → Emulator finalizes transaction
4. Client sends IDL → Emulator confirms completion

### Testing POS Emulator

```python
from orders.vendotek import VendotekClient

# Connect to emulator
client = VendotekClient(ip_address='localhost', port=4001)

if client.connect():
    # Process payment
    response = client.process_payment(amount=200)
    print(f"Payment result: {response.success}")
    print(f"Approved amount: {response.approved_amount}")
    
    client.disconnect()
```

## Integration with Main Application

### Option 1: Docker Compose (Recommended for Development)

1. Start emulators:
```bash
docker-compose -f docker-compose-emulators.yml up -d
```

2. Update main app's docker-compose.yml to connect to emulator network:
```yaml
services:
  web:
    # ... existing config ...
    networks:
      - app-network
      - hardware-emulators

networks:
  app-network:
    driver: bridge
  hardware-emulators:
    external: true
    name: hardware-emulators
```

3. Update `.env`:
```env
DEFAULT_HOST_PLC=plc-emulator
DEFAULT_PORT_PLC=502
```

4. Start main application:
```bash
docker-compose up
```

### Option 2: Standalone (Recommended for Testing)

1. Start emulators on host machine:
```bash
python emulators/modbus_plc_emulator.py --port 5020 &
python emulators/vendotek_pos_emulator.py --port 4001 &
```

2. Update `.env`:
```env
DEFAULT_HOST_PLC=localhost
DEFAULT_PORT_PLC=5020
```

3. Update VendotekServerConfig:
- ip_address: `localhost`
- port: `4001`

4. Run main application (Docker or local)

### Option 3: Host Network Mode (Simplest for Local Dev)

Modify `docker-compose-emulators.yml`:
```yaml
services:
  plc-emulator:
    network_mode: "host"
    # Remove ports section
  pos-emulator:
    network_mode: "host"
    # Remove ports section
```

Then use `localhost` in your `.env` file.

## Advanced Usage

### Simulating Different Scenarios

#### PLC Emulator

You can modify the emulator code to simulate:
- Different program configurations
- Price changes
- Wash status changes
- Cash acceptor events

#### POS Emulator

Control payment behavior:
```python
# In vendotek_pos_emulator.py, modify:
emulator.set_auto_approve(False)  # Reject all payments
emulator.approval_delay = 5.0     # Delay approval by 5 seconds
```

### Monitoring

View emulator logs:
```bash
# Docker
docker-compose -f docker-compose-emulators.yml logs -f plc-emulator
docker-compose -f docker-compose-emulators.yml logs -f pos-emulator

# Standalone
# Logs are printed to stdout
```

### Health Checks

Both emulators include health checks when running in Docker. Check status:
```bash
docker-compose -f docker-compose-emulators.yml ps
```

## Troubleshooting

### PLC Emulator

**Problem**: Can't connect to PLC emulator
- Check if port 502 (or 5020) is available
- Verify firewall settings
- Check emulator logs for errors

**Problem**: Wrong register values
- Verify you're using correct addresses from `modbus_config.py`
- Check if emulator initialized correctly (check logs)

### POS Emulator

**Problem**: Payment always fails
- Check if `auto_approve` is set to `True`
- Verify connection to correct port
- Check emulator logs for message parsing errors

**Problem**: Connection refused
- Verify emulator is running: `docker ps` or check process
- Check if port 4001 is available
- Verify network configuration

## Development

### Adding New Features

To extend the emulators:

1. **PLC Emulator**: Modify `modbus_plc_emulator.py`
   - Add new registers in `_init_data_store()`
   - Add simulation methods for new behaviors

2. **POS Emulator**: Modify `vendotek_pos_emulator.py`
   - Add new message handlers
   - Extend `PaymentState` dataclass
   - Add new TLV field parsers

### Testing Changes

1. Run emulator standalone to test:
```bash
python emulators/modbus_plc_emulator.py
```

2. Test with actual client code:
```python
from orders.modbus_client import ModbusClient
client = ModbusClient('localhost', 5020, 10)
client.connect()
# Test your changes
```

3. Rebuild Docker images:
```bash
docker-compose -f docker-compose-emulators.yml build
```

## Best Practices

1. **Separate Networks**: Keep emulators on separate network from production
2. **Port Mapping**: Use non-standard ports (5020, 4001) to avoid conflicts
3. **Environment Variables**: Use env vars for configuration
4. **Health Checks**: Monitor emulator health in production-like setups
5. **Logging**: Enable detailed logging for debugging
6. **State Management**: Reset emulator state between test runs

## See Also

- [MODBUS_INTEGRATION.md](../MODBUS_INTEGRATION.md) - Main application Modbus integration
- [README.md](../README.md) - Main project documentation

