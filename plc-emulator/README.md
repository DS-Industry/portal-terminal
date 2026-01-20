# PLC Emulator - Standalone

A standalone Modbus TCP server that emulates an OWEN PLC for car wash systems. This emulator can run independently and is perfect for testing your car wash terminal application without physical hardware.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start the emulator
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the emulator
docker-compose down
```

The emulator will be available on `localhost:5020` (or the port specified in `.env`).

### Using Docker

```bash
# Build the image
docker build -t plc-emulator .

# Run the container
docker run -d \
  --name plc-emulator \
  -p 5020:502 \
  -e PLC_PORT=502 \
  plc-emulator
```

### Standalone Python

```bash
# Install dependencies
pip install -r requirements.txt

# Run the emulator
python plc_emulator.py

# Or with custom settings
python plc_emulator.py --host 0.0.0.0 --port 5020
```

## Configuration

### Main Configuration File: `config.py`

All emulator settings are in `config.py`. Key sections:

1. **Network Configuration**
   - `PLC_HOST`: Host to bind to (default: `0.0.0.0`)
   - `PLC_PORT`: Port number (default: `502`)
   - `PLC_UNIT_ID`: Modbus unit ID (default: `1`)

2. **Wash Programs**
   - Define 5 car wash programs with their steps
   - Each step is a function code (1-7)
   - Modify `PROGRAMS` dict to change programs

3. **Pricing**
   - Set regular and loyalty prices for each program
   - Modify `PRICES` dict to change prices

4. **Register Map**
   - Defines Modbus memory addresses
   - **IMPORTANT**: Must match your real PLC configuration
   - Only modify if you know your PLC uses different addresses

### Environment Variables

You can override `config.py` settings using environment variables:

```bash
# Create .env file (copy from .env.example)
cp .env.example .env

# Edit .env file
PLC_HOST=0.0.0.0
PLC_PORT=5020
PLC_UNIT_ID=1
LOG_LEVEL=INFO
```

### Docker Compose Configuration

Edit `docker-compose.yml` or use `.env` file:

```yaml
environment:
  - PLC_HOST=0.0.0.0
  - PLC_PORT=502
  - PLC_UNIT_ID=1
```

## Connecting Your Application

### From Docker Container

If your application runs in Docker:

1. Add the PLC network to your `docker-compose.yml`:
```yaml
services:
  your-app:
    networks:
      - your-network
      - plc-emulator-network

networks:
  plc-emulator-network:
    external: true
```

2. Connect using hostname `plc-emulator` and port `502`:
```python
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('plc-emulator', 502)
```

### From Host Machine

If your application runs on the host:

1. Use `localhost` and the mapped port (default `5020`):
```python
from pymodbus.client import ModbusTcpClient
client = ModbusTcpClient('localhost', 5020)
```

### From Another Machine

1. Use the host machine's IP address:
```python
client = ModbusTcpClient('192.168.1.100', 5020)
```

## Testing the Emulator

### Test Connection

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('localhost', 5020)
if client.connect():
    print("✅ Connected!")
    client.close()
else:
    print("❌ Connection failed")
```

### Read Programs

```python
# Read Program 1 (addresses 0-14)
result = client.read_input_registers(0, 15)
print(f"Program 1 steps: {result.registers}")
```

### Read Prices

```python
# Read Program 1 price (address 30)
price = client.read_input_registers(30, 1)
print(f"Price: {price.registers[0]} rubles")
```

### Start Wash

```python
# Start Program 1 (coil 0)
client.write_coil(0, True)

# Check status (discrete input 0)
status = client.read_discrete_inputs(0, 1)
print(f"Washing: {status.bits[0]}")
```

## Default Configuration

The emulator comes pre-configured with:

- **5 Programs**: Basic, Standard, Premium, Express, Deluxe
- **Prices**: 150₽ - 700₽ (regular), 135₽ - 630₽ (loyalty)
- **Port**: 502 (standard Modbus TCP)
- **Unit ID**: 1

## Customization

### Adding a New Program

1. Edit `config.py`:
```python
PROGRAMS[6] = {
    'name': 'Super Wash',
    'description': 'Super wash program',
    'steps': [1, 2, 3, 4, 5, 6, 7, 1, 2],  # Your steps
}

PRICES[6] = {
    'regular': 800,
    'loyalty': 720,
}
```

2. Add register addresses:
```python
REGISTER_MAP['programs']['start_addresses'][6] = 175
REGISTER_MAP['prices']['addresses']['Price6'] = 175
REGISTER_MAP['prices']['addresses']['LoyaltyPrice6'] = 176
REGISTER_MAP['coils']['start_addresses'][6] = 6
```

3. Restart the emulator

### Changing Prices

Simply edit `PRICES` in `config.py` and restart:

```python
PRICES[1] = {
    'regular': 250,  # Changed from 200
    'loyalty': 225,  # Changed from 180
}
```

### Changing Register Addresses

⚠️ **Warning**: Only change if your real PLC uses different addresses!

Edit `REGISTER_MAP` in `config.py`:

```python
REGISTER_MAP['programs']['start_addresses'][1] = 100  # New address
```

## Troubleshooting

### Can't Connect

1. **Check if emulator is running**:
   ```bash
   docker ps | grep plc-emulator
   # or
   ps aux | grep plc_emulator
   ```

2. **Check port**:
   ```bash
   netstat -an | grep 5020
   # or
   lsof -i :5020
   ```

3. **Check firewall**: Ensure port is not blocked

4. **Check logs**:
   ```bash
   docker-compose logs plc-emulator
   ```

### Wrong Register Values

1. Verify addresses in `config.py` match your client code
2. Check that programs/prices are defined correctly
3. Restart emulator after config changes

### Permission Denied (Port 502)

Port 502 requires root privileges on Linux. Solutions:

1. Use a different port (e.g., 5020) in `config.py`
2. Run with sudo (not recommended)
3. Use Docker with port mapping (recommended)

## Architecture

```
┌─────────────────────────────────────┐
│     Your Application                │
│  (Django, ModbusClient, etc.)       │
└──────────────┬──────────────────────┘
               │ Modbus TCP
               │ (Port 502/5020)
               ▼
┌─────────────────────────────────────┐
│      PLC Emulator                   │
│  ┌──────────────────────────────┐  │
│  │  Modbus TCP Server            │  │
│  │  ┌────────────────────────┐   │  │
│  │  │ Memory Blocks:         │   │  │
│  │  │ - Input Registers     │   │  │
│  │  │ - Holding Registers   │   │  │
│  │  │ - Coils               │   │  │
│  │  │ - Discrete Inputs     │   │  │
│  │  └────────────────────────┘   │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Configuration (config.py)    │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

## Files

- `plc_emulator.py` - Main emulator code
- `config.py` - Configuration file (edit this!)
- `requirements.txt` - Python dependencies
- `Dockerfile` - Docker image definition
- `docker-compose.yml` - Docker Compose configuration
- `.env.example` - Example environment variables
- `README.md` - This file

## Integration with Main Application

To connect your main car wash terminal application:

1. **Update environment variables** in main app:
   ```env
   DEFAULT_HOST_PLC=plc-emulator  # or localhost
   DEFAULT_PORT_PLC=502           # or 5020 if using mapped port
   ```

2. **If using Docker**, connect to `plc-emulator-network`

3. **Test connection** from your application:
   ```python
   from orders.modbus_client import ModbusClient
   client = ModbusClient('plc-emulator', 502, 10)
   if client.connect():
       print("Connected!")
   ```

## License

Part of the Portal Car Wash Terminal project.

## Support

For issues or questions:
1. Check `config.py` comments for configuration help
2. Review logs: `docker-compose logs -f`
3. Test connection: `python -c "from pymodbus.client import ModbusTcpClient; ..."`

