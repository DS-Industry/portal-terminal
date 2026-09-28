# PLC Emulator - How It Works

## Overview

The PLC Emulator is a **Modbus TCP server** that simulates an OWEN PLC (Programmable Logic Controller) used to control a car wash system. It responds to Modbus requests exactly like a real PLC would, allowing you to test your application without physical hardware.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Your Application (Django)                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │  ModbusClient (pymodbus)                         │  │
│  │  - Reads programs, prices                        │  │
│  │  - Writes start commands                         │  │
│  │  - Monitors wash status                          │  │
│  └──────────────┬───────────────────────────────────┘  │
└─────────────────┼──────────────────────────────────────┘
                  │ Modbus TCP Protocol
                  │ (Port 502)
                  ▼
┌─────────────────────────────────────────────────────────┐
│         PLC Emulator (Modbus TCP Server)                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │  ModbusServerContext                              │  │
│  │  ┌──────────────┬──────────────────────────────┐ │  │
│  │  │ Input Regs   │ Programs, Prices (read-only) │ │  │
│  │  │ Holding Regs │ Cash acceptor (read-write)  │ │  │
│  │  │ Coils        │ Start commands (read-write) │ │  │
│  │  │ Discrete In  │ Wash status (read-only)      │ │  │
│  │  └──────────────┴──────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Modbus Protocol Basics

Modbus is an industrial communication protocol. The PLC emulator implements **Modbus TCP** (Ethernet-based), which uses:

- **Function Codes**: Commands like "read register", "write coil"
- **Addresses**: Memory locations (registers, coils)
- **Data Types**: Different memory areas for different purposes

### Modbus Memory Areas

The emulator uses 4 types of Modbus memory areas:

1. **Input Registers (IR)** - Read-only, 16-bit values
   - Used for: Programs, prices
   - Address range: 0-9999

2. **Holding Registers (HR)** - Read-write, 16-bit values
   - Used for: Cash acceptor, control values
   - Address range: 0-9999

3. **Coils** - Read-write, single bit (on/off)
   - Used for: Start commands
   - Address range: 0-9999

4. **Discrete Inputs (DI)** - Read-only, single bit
   - Used for: Wash status
   - Address range: 0-9999

## Data Structure

### 1. Input Registers (Read-Only Data)

These contain programs and prices that your application reads:

```python
# Program 1: Addresses 0-14 (15 registers)
input_registers[0:3] = [1, 4, 7]
# Meaning: Химия 1 → Ополаскивание → Сушка

# Program 2: Addresses 35-49
input_registers[35:40] = [1, 3, 4, 5, 7]
# Meaning: Химия 1 → Пена → Ополаскивание → Осмос → Сушка

# Prices: Stored at specific addresses
input_registers[30] = 200   # Program 1 regular price
input_registers[31] = 180   # Program 1 loyalty price
input_registers[65] = 300   # Program 2 regular price
# ... and so on
```

**Function Codes**:
- Each number (1, 4, 7) represents a wash function:
  - `1` = Химия 1 (Chemical 1)
  - `2` = Химия 2 (Chemical 2)
  - `3` = Пена (Foam)
  - `4` = Ополаскивание (Rinse)
  - `5` = Осмос (Osmosis)
  - `6` = Воск (Wax)
  - `7` = Сушка (Dry)

### 2. Coils (Start Commands)

These are write-only commands to start wash programs:

```python
coils[0] = True   # Start Program 1
coils[1] = True   # Start Program 2
coils[3] = True   # Start Program 3
coils[4] = True   # Start Program 4
coils[5] = True   # Start Program 5
```

When your application writes `True` to coil address 0, it's telling the PLC to start Program 1.

### 3. Discrete Inputs (Status)

Read-only status indicators:

```python
discrete_inputs[0] = True   # Wash in progress
discrete_inputs[0] = False  # Wash idle/complete
```

Your application reads this to check if a wash is currently running.

### 4. Holding Registers (Cash Acceptor)

For cash payments:

```python
holding_registers[200] = 500  # 500 rubles inserted
```

In the real PLC, this might be at address 16388, but the emulator maps it to 200 for simplicity.

## Register Mapping

Here's the complete address map:

| Address | Type | Description | Access |
|---------|------|-------------|--------|
| 0-14 | Input Register | Program 1 steps | Read |
| 30 | Input Register | Program 1 price | Read |
| 31 | Input Register | Program 1 loyalty price | Read |
| 35-49 | Input Register | Program 2 steps | Read |
| 65 | Input Register | Program 2 price | Read |
| 66 | Input Register | Program 2 loyalty price | Read |
| 70-84 | Input Register | Program 3 steps | Read |
| 100 | Input Register | Program 3 price | Read |
| 101 | Input Register | Program 3 loyalty price | Read |
| 105-119 | Input Register | Program 4 steps | Read |
| 135 | Input Register | Program 4 price | Read |
| 136 | Input Register | Program 4 loyalty price | Read |
| 140-154 | Input Register | Program 5 steps | Read |
| 170 | Input Register | Program 5 price | Read |
| 171 | Input Register | Program 5 loyalty price | Read |
| 0 | Coil | Start Program 1 | Write |
| 1 | Coil | Start Program 2 | Write |
| 3 | Coil | Start Program 3 | Write |
| 4 | Coil | Start Program 4 | Write |
| 5 | Coil | Start Program 5 | Write |
| 0 | Discrete Input | Wash in progress | Read |
| 200 | Holding Register | Cash amount | Read/Write |

## Communication Flow

### Example 1: Reading a Program

```
Your App                    PLC Emulator
   │                            │
   │── Read Input Regs 0-14 ───>│
   │   (Function Code 0x04)     │
   │                            │
   │<── [1, 4, 7, 0, 0, ...] ───│
   │    (Program 1 steps)       │
```

**What happens:**
1. Your `ModbusClient` sends: "Read 15 input registers starting at address 0"
2. Emulator looks up `input_registers[0:15]`
3. Returns: `[1, 4, 7, 0, 0, 0, ...]` (first 3 are steps, rest are zeros)
4. Your app interprets: Program 1 = Chemical 1 → Rinse → Dry

### Example 2: Starting a Wash

```
Your App                    PLC Emulator
   │                            │
   │── Write Coil 0 = True ────>│
   │   (Function Code 0x05)     │
   │                            │
   │<── Success ────────────────│
   │                            │
   │── Read Discrete Input 0 ──>│
   │   (Check status)           │
   │                            │
   │<── True (washing) ─────────│
```

**What happens:**
1. Your app writes `True` to coil 0 (start Program 1)
2. Emulator sets `coils[0] = True`
3. Emulator sets `discrete_inputs[0] = True` (wash in progress)
4. Your app reads discrete input 0 to verify wash started

### Example 3: Reading Prices

```
Your App                    PLC Emulator
   │                            │
   │── Read Input Reg 30 ──────>│
   │   (Program 1 price)        │
   │                            │
   │<── 200 ────────────────────│
   │    (200 rubles)            │
   │                            │
   │── Read Input Reg 31 ──────>│
   │   (Program 1 loyalty)      │
   │                            │
   │<── 180 ────────────────────│
   │    (180 rubles)            │
```

## Implementation Details

### Initialization

When the emulator starts:

1. **Creates data blocks** for each memory type:
   ```python
   input_registers = [0] * 200      # 200 input registers
   holding_registers = [0] * 300    # 300 holding registers
   coils = [False] * 100             # 100 coils
   discrete_inputs = [False] * 100  # 100 discrete inputs
   ```

2. **Populates default values**:
   - Programs (wash sequences)
   - Prices (regular and loyalty)
   - All start at zero/idle

3. **Creates Modbus context**:
   ```python
   slave_context = ModbusSlaveContext(
       di=discrete_block,      # Discrete inputs
       co=coil_block,           # Coils
       hr=holding_block,        # Holding registers
       ir=input_block           # Input registers
   )
   ```

4. **Starts TCP server**:
   - Listens on port 502 (or specified port)
   - Accepts Modbus TCP connections
   - Handles requests in separate threads

### Request Handling

When a Modbus request arrives:

1. **Parse request**: Extract function code, address, count
2. **Validate**: Check address range, access permissions
3. **Read/Write**: Access appropriate data block
4. **Respond**: Send data or confirmation

### Threading

The emulator runs in a separate thread:
- Main thread: Can control emulator (start/stop)
- Server thread: Handles Modbus requests (blocking)
- This allows the emulator to run alongside your application

## Default Programs

The emulator comes with 5 pre-configured programs:

| Program | Steps | Regular Price | Loyalty Price |
|---------|-------|---------------|---------------|
| 1 (Basic) | Химия 1 → Ополаскивание → Сушка | 200₽ | 180₽ |
| 2 (Standard) | Химия 1 → Пена → Ополаскивание → Осмос → Сушка | 300₽ | 270₽ |
| 3 (Premium) | All 7 functions | 500₽ | 450₽ |
| 4 (Express) | Химия 1 → Ополаскивание | 150₽ | 135₽ |
| 5 (Deluxe) | All functions + repeat | 700₽ | 630₽ |

## Simulation Methods

The emulator provides helper methods for testing:

```python
# Simulate starting a wash
emulator.simulate_wash_start(program_number=1)

# Simulate wash completion
emulator.simulate_wash_complete()

# Simulate cash insertion
emulator.simulate_cash_inserted(amount=500)
```

These methods update the internal state, which your application can then read via Modbus.

## Differences from Real PLC

| Aspect | Real PLC | Emulator |
|--------|----------|----------|
| Hardware | Physical device | Software simulation |
| Cash Address | 16388 | 200 (mapped) |
| State Changes | Automatic (based on sensors) | Manual (via methods) |
| Timing | Real wash duration | Instant (no delays) |
| Errors | Hardware failures | Simulated errors |

## Usage Example

```python
from pymodbus.client import ModbusTcpClient

# Connect to emulator
client = ModbusTcpClient('localhost', 5020)
client.connect()

# Read Program 1
result = client.read_input_registers(0, 15)
program_steps = result.registers
print(f"Program 1: {program_steps}")

# Read price
price = client.read_input_registers(30, 1)
print(f"Price: {price.registers[0]} rubles")

# Start wash
client.write_coil(0, True)

# Check status
status = client.read_discrete_inputs(0, 1)
print(f"Washing: {status.bits[0]}")

client.close()
```

## Key Points

1. **Protocol Compliance**: Uses standard Modbus TCP, compatible with any Modbus client
2. **Stateful**: Maintains state (programs, prices, wash status)
3. **Thread-Safe**: Handles multiple concurrent connections
4. **Configurable**: Easy to modify programs, prices, addresses
5. **Testable**: Can simulate various scenarios (errors, delays, etc.)

## Extending the Emulator

To add new features:

1. **New registers**: Add to `_init_data_store()`
2. **New programs**: Extend input_registers array
3. **New commands**: Add to coils or holding registers
4. **Simulation logic**: Add methods to simulate hardware behavior

The emulator is designed to be a drop-in replacement for the real PLC during development and testing!

