# PLC Emulator - Technical Requirements

## 1. Overview

### 1.1 Purpose

The PLC Emulator is a software simulation of an OWEN PLC (Programmable Logic Controller) used in touchless robotic car wash systems. It provides a Modbus TCP interface that mimics the behavior of a real PLC, allowing software development and testing without physical hardware.

**Context:**
The PLC is used inside the touchless robotic car wash to control and operate the car wash system. Communication between the PLC and Kiosk terminal is performed via Modbus protocol. The goal of this communication is:

- **Receive program information:** Get information about what programs (products) are available for clients to purchase and what set of functions they contain. This information is updated every hour from the PLC.
- **Receive price information:** Get price information for each program available (regular and loyalty prices).
- **Monitor robot state:** Translate the state of the robot, meaning when it is busy or free.
- **Control robot:** Send commands to PLC to start or pause the robot.

### 1.2 Scope

The emulator MUST:

- **Simulate the process of performing car wash on a basic level** - Provide state management and command handling without actual hardware execution
- **Simulate Modbus TCP communication protocol** - Full Modbus TCP server implementation
- **Emulate car wash program storage and retrieval** - Store and serve 5 wash programs with their function sequences
- **Simulate price management** - Store and serve regular and loyalty prices for each program
- **Provide wash status monitoring** - Indicate when robot is busy, idle, or in error state
- **Support wash program start/stop commands** - Accept commands to start programs and update status accordingly
- **Provide GUI interface** - Visual interface for monitoring and manual control

### 1.3 Out of Scope

- Physical hardware control (valves, pumps, motors)
- Real-time wash execution timing with automatic progression
- Sensor input simulation
- Actual car wash robot movement
- Network security/authentication (for development use)
- Automatic wash completion timing

---

## 2. Functional Requirements

### 2.1 Modbus TCP Server

**FR-001: Modbus TCP Protocol Support**
- **Requirement:** The emulator MUST implement Modbus TCP protocol (RFC 1006)
- **Details:**
  - Listen on configurable host and port (default: 0.0.0.0:502)
  - Support Modbus function codes:
    - 0x01: Read Coils
    - 0x02: Read Discrete Inputs
    - 0x03: Read Holding Registers
    - 0x04: Read Input Registers
    - 0x05: Write Single Coil
    - 0x06: Write Single Register
  - Support Modbus Unit ID (default: 1)
  - Handle multiple concurrent connections
  - Respond to requests within 5 seconds

**FR-002: Network Configuration**
- **Requirement:** The emulator MUST be configurable for network settings
- **Details:**
  - Configurable bind address (default: 0.0.0.0 for all interfaces)
  - Configurable port (default: 502, fallback: 5020)
  - Support environment variable overrides
  - Support command-line argument overrides

### 2.2 Car Wash Program Management

**FR-003: Program Storage**
- **Requirement:** The emulator MUST store 5 car wash programs
- **Details:**
  - Each program consists of up to 15 steps
  - Each step is a function code (0-7):
    - 0: No operation
    - 1: Chemical 1 (Химия 1)
    - 2: Chemical 2 (Химия 2)
    - 3: Foam (Пена)
    - 4: Rinse (Ополаскивание)
    - 5: Osmosis (Осмос)
    - 6: Wax (Воск)
    - 7: Dry (Сушка)
  - Programs stored in Input Registers (read-only)
  - Program addresses:
    - Program 1: Registers 0-14
    - Program 2: Registers 35-49
    - Program 3: Registers 70-84
    - Program 4: Registers 105-119
    - Program 5: Registers 140-154

**FR-004: Program Reading**
- **Requirement:** The emulator MUST allow reading programs via Modbus
- **Details:**
  - Read single register (function code 0x04)
  - Read multiple registers (function code 0x04)
  - Return function codes as 16-bit integers
  - Return 0 for unused program steps

**FR-005: Program Configuration**
- **Requirement:** Programs MUST be configurable via configuration file (preferably JSON)
- **Details:**
  - Default programs provided
  - Programs editable in configuration file
  - Changes require emulator restart
  - JSON format preferred for easy editing

### 2.3 Price Management

**FR-006: Price Storage**
- **Requirement:** The emulator MUST store prices for each program
- **Details:**
  - Regular price (in rubles)
  - Loyalty price (in rubles)
  - Prices stored in Input Registers (read-only)
  - Price addresses:
    - Program 1: Regular=30, Loyalty=31
    - Program 2: Regular=65, Loyalty=66
    - Program 3: Regular=100, Loyalty=101
    - Program 4: Regular=135, Loyalty=136
    - Program 5: Regular=170, Loyalty=171

**FR-007: Price Reading**
- **Requirement:** The emulator MUST allow reading prices via Modbus
- **Details:**
  - Read single register (function code 0x04)
  - Return price as 16-bit integer (rubles)
  - Support reading all prices in batch

**FR-008: Price Configuration**
- **Requirement:** Prices MUST be configurable via configuration file
- **Details:**
  - Default prices provided
  - Prices editable in configuration file
  - Changes require emulator restart

### 2.4 Wash Control

**FR-009: Start Commands**
- **Requirement:** The emulator MUST accept wash start commands
- **Details:**
  - Commands via Coils (write-only)
  - Coil addresses:
    - Program 1: Coil 0
    - Program 2: Coil 1
    - Program 3: Coil 3
    - Program 4: Coil 4
    - Program 5: Coil 5
  - Write True (1) to start program
  - Write False (0) to stop/reset
  - Support function code 0x05 (Write Single Coil)

**FR-010: Wash Status**
- **Requirement:** The emulator MUST provide wash status
- **Details:**
  - Status via Discrete Input (read-only)
  - Address: Discrete Input 0
  - Values:
    - False (0): Wash idle/complete
    - True (1): Wash in progress
  - Support function code 0x02 (Read Discrete Inputs)
  - Status updates when start command received

**FR-011: Status Simulation**
- **Requirement:** The emulator MUST simulate wash status changes
- **Details:**
  - Set status to True when start command received
  - Provide method to simulate wash completion
  - Status persists until explicitly changed
  - No automatic timing (manual control for testing)

### 2.5 Configuration Management

**FR-012: Configuration File**
- **Requirement:** The emulator MUST support a single configuration file (preferably JSON format)
- **Details:**
  - All configuration in one file (preferably JSON)
  - Support for:
    - Network settings (host, port, unit ID)
    - Program definitions
    - Price definitions
    - Register address mapping
  - Environment variable overrides
  - Command-line argument overrides
  - Priority: CLI args > Env vars > Config file > Defaults

**FR-013: Configuration Validation**
- **Requirement:** The emulator MUST validate configuration
- **Details:**
  - Validate all programs have prices
  - Validate register addresses don't overlap
  - Validate port range (1-65535)
  - Validate unit ID range (1-247)
  - Report errors on startup

### 2.6 Error Handling

**FR-014: Connection Errors**
- **Requirement:** The emulator MUST handle connection errors gracefully
- **Details:**
  - Log connection attempts
  - Handle connection timeouts
  - Handle invalid Modbus requests
  - Return appropriate Modbus error codes
  - Continue running after errors

**FR-015: Invalid Requests**
- **Requirement:** The emulator MUST handle invalid Modbus requests
- **Details:**
  - Validate function codes
  - Validate address ranges
  - Validate data types
  - Return Modbus exception codes:
    - 0x01: Illegal Function
    - 0x02: Illegal Data Address
    - 0x03: Illegal Data Value

### 2.7 Logging

**FR-016: Logging Support**
- **Requirement:** The emulator MUST provide logging
- **Details:**
  - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Log connection events
  - Log Modbus requests/responses (optional, configurable)
  - Log configuration loading
  - Log errors with context
  - Configurable log level

---

## 3. GUI Interface Requirements

### 3.1 Overview

**FR-017: Graphical User Interface**
- **Requirement:** The emulator MUST provide a simple GUI interface for monitoring and control
- **Purpose:**
  - Visualize current Modbus register values
  - Display system state (robot status, errors)
  - Allow manual input to change register values
  - Enable interactive testing and debugging

### 3.2 Register Display

**FR-018: Register Value Display**
- **Requirement:** GUI MUST display all Modbus register values in real-time
- **Details:**
  - **Input Registers Section:**
    - Display all program steps (registers 0-14, 35-49, 70-84, 105-119, 140-154)
    - Display all prices (registers 30, 31, 65, 66, 100, 101, 135, 136, 170, 171)
    - Show register address and current value
    - Display function names for program steps (not just codes)
  - **Coils Section:**
    - Display all start command coils (0, 1, 3, 4, 5)
    - Show current state (True/False, On/Off)
    - Visual indicator (green/red, checkbox)
  - **Discrete Inputs Section:**
    - Display wash status (Discrete Input 0)
    - Show current state with clear label (Idle/Running)
  - **Update frequency:** Refresh every 1-2 seconds
  - **Color coding:** Different colors for different register types

### 3.3 System State Display

**FR-019: System Status Display**
- **Requirement:** GUI MUST display comprehensive system state information
- **Details:**
  - **Robot Status:**
    - Current state: Idle / Running / Error
    - Active program number (if running)
    - Visual indicator (status light: green/yellow/red)
  - **Connection Status:**
    - Modbus server status (Running/Stopped)
    - Number of active connections
    - Server address and port
  - **Error Display:**
    - Show any errors that occurred
    - Error log/history
    - Clear error messages
  - **System Information:**
    - Modbus Unit ID
    - Uptime
    - Last update time

### 3.4 Manual Value Input

**FR-020: Register Value Editing**
- **Requirement:** GUI MUST allow manual editing of register values
- **Details:**
  - **Editable Registers:**
    - Coils: Toggle start commands (buttons or checkboxes)
    - Prices: Edit price values (input fields)
    - Program steps: Edit function codes (dropdown or input)
    - Wash status: Manually set idle/running (button or toggle)
  - **Input Validation:**
    - Validate register address ranges
    - Validate data types (integers for registers, booleans for coils)
    - Validate function codes (0-7 for program steps)
    - Show error messages for invalid inputs
  - **Write Operations:**
    - "Apply" or "Write" button for each editable field
    - Confirmation for critical operations (start commands)
    - Immediate update of displayed values after write
  - **Bulk Operations:**
    - Load program from configuration
    - Reset all values to defaults
    - Set all prices at once

### 3.5 Interactive Controls

**FR-021: Control Buttons**
- **Requirement:** GUI MUST provide interactive control buttons
- **Details:**
  - **Program Control:**
    - "Start Program 1-5" buttons for each program
    - "Stop" button to stop current wash
    - "Reset" button to reset all coils
  - **Status Control:**
    - "Set Idle" button
    - "Set Running" button
    - "Simulate Error" button (for testing error scenarios)
  - **System Control:**
    - "Restart Server" button
    - "Reload Config" button
    - "Clear Logs" button
  - **Visual Feedback:**
    - Button state changes (enabled/disabled)
    - Confirmation dialogs for critical actions
    - Success/error messages after operations

### 3.6 GUI Technical Specifications

**FR-022: GUI Implementation**
- **Requirement:** GUI MUST be simple and cross-platform
- **Details:**
  - **Technology Options:**
    - Web-based (HTML/CSS/JavaScript) - Recommended for simplicity
    - Desktop GUI (Tkinter, PyQt, or similar)
    - Accessible via web browser (localhost:8080 or similar)
  - **Features:**
    - Real-time updates (auto-refresh or WebSocket)
    - Responsive design (works on different screen sizes)
    - Clear, organized layout
    - Easy to understand labels and tooltips
  - **Access:**
    - Accessible from same machine (localhost)
    - Optional: Accessible from network (for remote monitoring)
  - **Performance:**
    - Low resource usage
    - Smooth updates without lag
    - Handle multiple simultaneous users (if web-based)

### 3.7 GUI Layout Structure

**FR-023: GUI Organization**
- **Requirement:** GUI MUST be organized in clear sections
- **Details:**
  - **Header Section:**
    - System status indicator
    - Connection information
    - Error display area
  - **Main Panel - Tabs or Sections:**
    - **Programs Tab:**
      - List of all 5 programs
      - Show steps with function names
      - Edit buttons for each program
    - **Prices Tab:**
      - Table of all prices
      - Edit fields for regular and loyalty prices
    - **Registers Tab:**
      - Complete register map view
      - Search/filter functionality
      - Edit individual registers
    - **Control Tab:**
      - Start/stop buttons
      - Status controls
      - System controls
  - **Footer Section:**
    - Log output area
    - Connection statistics
    - Last update timestamp

---

## 4. Technical Specifications

### 4.1 Protocol Specifications

**Modbus TCP:**
- Protocol: TCP/IP
- Port: 502 (standard), 5020 (alternative)
- Unit ID: 1 (default, configurable 1-247)
- Transaction ID: Auto-incrementing
- Protocol ID: 0 (Modbus)
- Length: Auto-calculated
- Function Code: As per Modbus specification

**Data Types:**
- Coils: Boolean (1 bit)
- Discrete Inputs: Boolean (1 bit)
- Holding Registers: 16-bit unsigned integer
- Input Registers: 16-bit unsigned integer

### 4.2 Register Map

**Input Registers (Read-Only):**
- 0-14: Program 1 steps
- 30: Program 1 regular price
- 31: Program 1 loyalty price
- 35-49: Program 2 steps
- 65: Program 2 regular price
- 66: Program 2 loyalty price
- 70-84: Program 3 steps
- 100: Program 3 regular price
- 101: Program 3 loyalty price
- 105-119: Program 4 steps
- 135: Program 4 regular price
- 136: Program 4 loyalty price
- 140-154: Program 5 steps
- 170: Program 5 regular price
- 171: Program 5 loyalty price

**Coils (Read/Write):**
- 0: Start Program 1
- 1: Start Program 2
- 3: Start Program 3
- 4: Start Program 4
- 5: Start Program 5

**Discrete Inputs (Read-Only):**
- 0: Wash status (True = in progress, False = idle)

### 4.3 Default Programs

**Program 1 - Basic:**
- Steps: [1, 4, 7] (Chemical 1 → Rinse → Dry)
- Regular Price: 200₽
- Loyalty Price: 180₽

**Program 2 - Standard:**
- Steps: [1, 3, 4, 5, 7] (Chemical 1 → Foam → Rinse → Osmosis → Dry)
- Regular Price: 300₽
- Loyalty Price: 270₽

**Program 3 - Premium:**
- Steps: [1, 2, 3, 4, 5, 6, 7] (All functions)
- Regular Price: 500₽
- Loyalty Price: 450₽

**Program 4 - Express:**
- Steps: [1, 4] (Chemical 1 → Rinse)
- Regular Price: 150₽
- Loyalty Price: 135₽

**Program 5 - Deluxe:**
- Steps: [1, 2, 3, 4, 5, 6, 7, 1] (All functions + repeat)
- Regular Price: 700₽
- Loyalty Price: 630₽

### 4.4 Software Stack

**Runtime:**
- Python 3.12+ (minimum 3.8)
- pymodbus 3.5.2+

**Dependencies:**
- pymodbus (Modbus protocol implementation)
- Standard library only (no external dependencies for core functionality)
- GUI dependencies (TBD based on chosen GUI framework)

**Optional:**
- Docker (for containerized deployment)
- docker-compose (for orchestration)
- Web framework (Flask/FastAPI if web-based GUI)

---

## 5. Deployment Requirements

### 5.1 Docker Deployment

**DR-001: Docker Image**
- Base image: python:3.12-slim
- Expose port 502 (or configured port) for Modbus
- Expose port 8080 (or configured port) for GUI (if web-based)
- Health check included
- Volume mount for configuration

**DR-002: Docker Compose**
- Service definition
- Network configuration
- Environment variable support
- Health check configuration
