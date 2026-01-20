# Configuration Guide: Connecting Main Application to PLC Emulator

This guide shows you exactly what values to configure in the PLC emulator and your main application based on how they're running.

## Quick Reference Table

| Scenario | PLC Emulator Config | Main App .env | Notes |
|----------|-------------------|---------------|-------|
| **Both in Docker** | `PLC_HOST=0.0.0.0`<br>`PLC_PORT=502` | `DEFAULT_HOST_PLC=plc-emulator`<br>`DEFAULT_PORT_PLC=502` | Use Docker network |
| **Both Standalone** | `PLC_HOST=0.0.0.0`<br>`PLC_PORT=5020` | `DEFAULT_HOST_PLC=localhost`<br>`DEFAULT_PORT_PLC=5020` | Use localhost |
| **PLC Docker, App Standalone** | `PLC_HOST=0.0.0.0`<br>`PLC_PORT=502` | `DEFAULT_HOST_PLC=localhost`<br>`DEFAULT_PORT_PLC=5020` | Port mapping: 5020→502 |
| **PLC Standalone, App Docker** | `PLC_HOST=0.0.0.0`<br>`PLC_PORT=5020` | `DEFAULT_HOST_PLC=host.docker.internal`<br>`DEFAULT_PORT_PLC=5020` | Use host network |

---

## Scenario 1: Both Running in Docker (Recommended)

### PLC Emulator Configuration

**File: `plc-emulator/config.py`**
```python
PLC_HOST = '0.0.0.0'  # Listen on all interfaces
PLC_PORT = 502        # Internal container port
PLC_UNIT_ID = 1      # Modbus unit ID
```

**File: `plc-emulator/docker-compose.yml`** (already configured)
```yaml
ports:
  - "5020:502"  # Maps host:5020 → container:502
environment:
  - PLC_PORT=502  # Internal port
```

### Main Application Configuration

**File: `.env` (in main project root)**
```env
# PLC Connection Settings
DEFAULT_HOST_PLC=plc-emulator
DEFAULT_PORT_PLC=502
DEFAULT_TIMEOUT_PLC=10
```

**File: `docker-compose.yml` (main app)**
```yaml
services:
  web:
    networks:
      - app-network
      - plc-emulator-network  # Add this

networks:
  app-network:
    driver: bridge
  plc-emulator-network:
    external: true
    name: plc-emulator-network
```

**Why these values?**
- `plc-emulator` is the Docker service name (hostname in Docker network)
- `502` is the internal container port
- Both containers are on the same Docker network

---

## Scenario 2: Both Running Standalone (No Docker)

### PLC Emulator Configuration

**File: `plc-emulator/config.py`**
```python
PLC_HOST = '0.0.0.0'  # Listen on all interfaces
PLC_PORT = 5020       # Use non-standard port (502 requires root)
PLC_UNIT_ID = 1
```

**Run:**
```bash
cd plc-emulator
python plc_emulator.py
```

### Main Application Configuration

**File: `.env` (in main project root)**
```env
# PLC Connection Settings
DEFAULT_HOST_PLC=localhost
DEFAULT_PORT_PLC=5020
DEFAULT_TIMEOUT_PLC=10
```

**Why these values?**
- `localhost` because both run on the same machine
- `5020` matches the emulator port (avoid 502 which needs root)

---

## Scenario 3: PLC in Docker, Main App Standalone

### PLC Emulator Configuration

**File: `plc-emulator/config.py`**
```python
PLC_HOST = '0.0.0.0'  # Listen on all interfaces
PLC_PORT = 502        # Internal container port
PLC_UNIT_ID = 1
```

**File: `plc-emulator/docker-compose.yml`**
```yaml
ports:
  - "5020:502"  # Maps host:5020 → container:502
```

### Main Application Configuration

**File: `.env` (in main project root)**
```env
# PLC Connection Settings
DEFAULT_HOST_PLC=localhost
DEFAULT_PORT_PLC=5020
DEFAULT_TIMEOUT_PLC=10
```

**Why these values?**
- `localhost` because app runs on host
- `5020` is the mapped host port (Docker maps 5020→502)

---

## Scenario 4: PLC Standalone, Main App in Docker

### PLC Emulator Configuration

**File: `plc-emulator/config.py`**
```python
PLC_HOST = '0.0.0.0'  # Listen on all interfaces
PLC_PORT = 5020       # Use non-standard port
PLC_UNIT_ID = 1
```

**Run:**
```bash
cd plc-emulator
python plc_emulator.py
```

### Main Application Configuration

**File: `.env` (in main project root)**
```env
# PLC Connection Settings
DEFAULT_HOST_PLC=host.docker.internal  # Special Docker hostname
DEFAULT_PORT_PLC=5020
DEFAULT_TIMEOUT_PLC=10
```

**Alternative (Linux):**
```env
DEFAULT_HOST_PLC=172.17.0.1  # Docker bridge gateway IP
DEFAULT_PORT_PLC=5020
```

**Why these values?**
- `host.docker.internal` is Docker's special hostname for host machine (macOS/Windows)
- On Linux, use `172.17.0.1` or add `extra_hosts` to docker-compose.yml

---

## Configuration Checklist

### For PLC Emulator (`plc-emulator/config.py`):

- [ ] **PLC_HOST**: Set to `'0.0.0.0'` (allows connections from anywhere)
- [ ] **PLC_PORT**: 
  - `502` if running in Docker
  - `5020` if running standalone (to avoid root requirement)
- [ ] **PLC_UNIT_ID**: Usually `1` (match your real PLC if known)
- [ ] **PROGRAMS**: Verify programs match your car wash system
- [ ] **PRICES**: Update prices to match your pricing
- [ ] **REGISTER_MAP**: Only change if your real PLC uses different addresses

### For Main Application (`.env` in project root):

- [ ] **DEFAULT_HOST_PLC**: 
  - `plc-emulator` if both in Docker
  - `localhost` if both standalone or PLC in Docker
  - `host.docker.internal` if app in Docker, PLC standalone
- [ ] **DEFAULT_PORT_PLC**:
  - `502` if both in Docker (internal port)
  - `5020` if using port mapping or standalone
- [ ] **DEFAULT_TIMEOUT_PLC**: Usually `10` seconds

---

## Testing the Connection

### From Main Application

```python
# Test in Django shell or Python script
from orders.modbus_client import ModbusClient

client = ModbusClient('localhost', 5020, 10)  # Adjust host/port
if client.connect():
    print("✅ Connected to PLC emulator!")
    
    # Read Program 1
    program = client.read_program('Program1')
    print(f"Program 1: {program}")
    
    # Read prices
    prices = client.read_all_prices()
    print(f"Prices: {prices}")
    
    client.disconnect()
else:
    print("❌ Failed to connect")
```

### Quick Test Command

```bash
# Test from main project directory
python -c "
from orders.modbus_client import ModbusClient
import os
host = os.getenv('DEFAULT_HOST_PLC', 'localhost')
port = int(os.getenv('DEFAULT_PORT_PLC', '5020'))
client = ModbusClient(host, port, 10)
print(f'Connecting to {host}:{port}...')
if client.connect():
    print('✅ Connected!')
    result = client.read_input_registers(0, 1)
    print(f'Test read: {result.registers[0] if result else \"Failed\"}')
    client.disconnect()
else:
    print('❌ Connection failed')
"
```

---

## Common Issues & Solutions

### Issue: "Connection refused"

**Check:**
1. Is PLC emulator running? `docker ps` or `ps aux | grep plc`
2. Is port correct? Check `netstat -an | grep 5020`
3. Is hostname correct?
   - Docker: Use service name `plc-emulator`
   - Standalone: Use `localhost`
   - Cross-platform: Use `host.docker.internal`

**Solution:**
```bash
# Check PLC emulator logs
cd plc-emulator
docker-compose logs -f

# Or if standalone
# Check terminal where emulator is running
```

### Issue: "Wrong register values"

**Check:**
1. Are register addresses correct in `config.py`?
2. Do they match `modbus_config.py` in main app?
3. Did you restart emulator after config changes?

**Solution:**
- Verify `REGISTER_MAP` in `plc-emulator/config.py` matches addresses in main app
- Restart emulator: `docker-compose restart` or restart Python process

### Issue: "Port 502 permission denied"

**Solution:**
- Use port `5020` instead (doesn't require root)
- Update both emulator config and main app `.env`

---

## Register Address Reference

The emulator uses these addresses (from `config.py`):

| Item | Address | Type | Description |
|------|---------|------|-------------|
| Program 1 | 0-14 | Input Register | Program 1 steps |
| Program 2 | 35-49 | Input Register | Program 2 steps |
| Program 3 | 70-84 | Input Register | Program 3 steps |
| Program 4 | 105-119 | Input Register | Program 4 steps |
| Program 5 | 140-154 | Input Register | Program 5 steps |
| Price 1 | 30 | Input Register | Program 1 regular price |
| Loyalty Price 1 | 31 | Input Register | Program 1 loyalty price |
| Price 2 | 65 | Input Register | Program 2 regular price |
| Loyalty Price 2 | 66 | Input Register | Program 2 loyalty price |
| Price 3 | 100 | Input Register | Program 3 regular price |
| Loyalty Price 3 | 101 | Input Register | Program 3 loyalty price |
| Price 4 | 135 | Input Register | Program 4 regular price |
| Loyalty Price 4 | 136 | Input Register | Program 4 loyalty price |
| Price 5 | 170 | Input Register | Program 5 regular price |
| Loyalty Price 5 | 171 | Input Register | Program 5 loyalty price |
| Start Program 1 | 0 | Coil | Write True to start |
| Start Program 2 | 1 | Coil | Write True to start |
| Start Program 3 | 3 | Coil | Write True to start |
| Start Program 4 | 4 | Coil | Write True to start |
| Start Program 5 | 5 | Coil | Write True to start |
| Wash Status | 0 | Discrete Input | Read to check if washing |
| Cash | 200 | Holding Register | Cash amount inserted |

**These must match your main application's expectations!**

---

## Summary

**Most Common Setup (Both in Docker):**

1. **PLC Emulator**: No changes needed (defaults work)
2. **Main App `.env`**:
   ```env
   DEFAULT_HOST_PLC=plc-emulator
   DEFAULT_PORT_PLC=502
   ```
3. **Main App `docker-compose.yml`**: Add `plc-emulator-network` to networks

That's it! The emulator is pre-configured to work with your main application.

