# PLC Emulator - Quick Start Guide

## 📁 Folder Structure

```
plc-emulator/
├── plc_emulator.py      # Main emulator code
├── config.py            # ⚙️ CONFIGURATION FILE (edit this!)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── env.example          # Example environment variables
├── start.sh             # Quick start script
├── README.md            # Full documentation
└── QUICK_START.md       # This file
```

## 🚀 Quick Start

### Option 1: Docker Compose (Easiest)

```bash
cd plc-emulator
./start.sh
```

Or manually:
```bash
cd plc-emulator
docker-compose up -d
```

### Option 2: Standalone Python

```bash
cd plc-emulator
pip install -r requirements.txt
python plc_emulator.py
```

## ⚙️ Configuration

**All configuration is in `config.py`** - open it and read the comments!

Key sections to configure:

1. **Network Settings** (lines ~20-30)
   - `PLC_HOST`: Where to listen (default: `0.0.0.0`)
   - `PLC_PORT`: Port number (default: `502`)

2. **Wash Programs** (lines ~50-80)
   - Define your 5 car wash programs
   - Each program has steps (function codes 1-7)

3. **Prices** (lines ~90-120)
   - Set regular and loyalty prices for each program

4. **Register Map** (lines ~130-200)
   - ⚠️ **Only change if your real PLC uses different addresses!**
   - Defines Modbus memory addresses

## 🔧 What You Need to Configure

### Required (if different from defaults):

1. **Port Number** (if 502 is taken):
   ```python
   PLC_PORT = 5020  # In config.py
   ```

2. **Programs** (if you have different wash programs):
   ```python
   PROGRAMS[1] = {
       'name': 'Your Program Name',
       'steps': [1, 4, 7],  # Your function sequence
   }
   ```

3. **Prices** (to match your pricing):
   ```python
   PRICES[1] = {
       'regular': 250,  # Your price
       'loyalty': 225,  # Your loyalty price
   }
   ```

### Optional:

- **Host binding**: Change `PLC_HOST` if you need specific IP
- **Unit ID**: Change `PLC_UNIT_ID` if your system uses different ID
- **Register addresses**: Only if your PLC uses different addresses

## 📝 Configuration Checklist

Before running, check:

- [ ] Port is available (502 or your chosen port)
- [ ] Programs match your car wash system
- [ ] Prices are correct
- [ ] Register addresses match your real PLC (if known)
- [ ] Network settings are correct

## 🔌 Connecting Your Application

### From Docker:
```python
client = ModbusTcpClient('plc-emulator', 502)
```

### From Host:
```python
client = ModbusTcpClient('localhost', 5020)  # or 502
```

### Update Main App .env:
```env
DEFAULT_HOST_PLC=plc-emulator  # or localhost
DEFAULT_PORT_PLC=502            # or 5020
```

## 🧪 Test Connection

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('localhost', 5020)
if client.connect():
    print("✅ Connected!")
    # Read Program 1
    result = client.read_input_registers(0, 15)
    print(f"Program 1: {result.registers}")
    client.close()
```

## 📚 More Information

- See `README.md` for full documentation
- See `config.py` comments for detailed configuration help
- Check logs: `docker-compose logs -f`

## 🆘 Troubleshooting

**Can't connect?**
1. Check if running: `docker ps` or `ps aux | grep plc`
2. Check port: `netstat -an | grep 5020`
3. Check logs: `docker-compose logs`

**Wrong values?**
1. Verify `config.py` settings
2. Restart emulator after config changes
3. Check register addresses match your client code

**Port 502 permission denied?**
- Use port 5020 instead (edit `config.py`)
- Or run Docker with port mapping

