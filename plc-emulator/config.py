#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration file for PLC Emulator

This file contains all configuration settings for the Modbus PLC emulator.
Modify the values below to match your car wash system requirements.

IMPORTANT: After modifying this file, restart the emulator for changes to take effect.
"""

import os
from typing import Dict, List

# ============================================================================
# NETWORK CONFIGURATION
# ============================================================================

# Host to bind the Modbus TCP server to
# Use '0.0.0.0' to listen on all interfaces, or specific IP like '192.168.1.100'
# Default: '0.0.0.0' (allows connections from any network interface)
PLC_HOST = os.getenv('PLC_HOST', '0.0.0.0')

# Port for Modbus TCP server
# Standard Modbus TCP port is 502, but you may need to use a different port
# if 502 is already in use or requires root privileges
# Default: 502
# Handle Windows Docker environment variable issues
try:
    plc_port_env = os.getenv('PLC_PORT', '502')
    PLC_PORT = int(plc_port_env) if plc_port_env else 502
except (ValueError, TypeError):
    PLC_PORT = 502  # Fallback to default

# Modbus Unit ID (Slave ID)
# This identifies the PLC on the Modbus network
# Default: 1
# Handle Windows Docker environment variable issues
try:
    plc_unit_id_env = os.getenv('PLC_UNIT_ID', '1')
    PLC_UNIT_ID = int(plc_unit_id_env) if plc_unit_id_env else 1
except (ValueError, TypeError):
    PLC_UNIT_ID = 1  # Fallback to default


# ============================================================================
# CAR WASH FUNCTIONS
# ============================================================================

# Function codes for different wash operations
# These codes are used in program steps to define the wash sequence
# DO NOT CHANGE these codes unless your PLC uses different values
FUNCTIONS = {
    0: "Нет",           # No operation
    1: "Химия 1",        # Chemical 1
    2: "Химия 2",        # Chemical 2
    3: "Пена",           # Foam
    4: "Ополаскивание",  # Rinse
    5: "Осмос",          # Osmosis
    6: "Воск",           # Wax
    7: "Сушка"           # Dry
}


# ============================================================================
# WASH PROGRAMS
# ============================================================================

# Define car wash programs
# Each program consists of a sequence of function codes (see FUNCTIONS above)
# Programs are numbered 1-5 (matching your car wash system)

PROGRAMS: Dict[int, Dict[str, any]] = {
    1: {
        'name': 'Basic Wash',
        'description': 'Basic wash program',
        'steps': [1, 4, 7],  # Химия 1 → Ополаскивание → Сушка
    },
    2: {
        'name': 'Standard Wash',
        'description': 'Standard wash program',
        'steps': [1, 3, 4, 5, 7],  # Химия 1 → Пена → Ополаскивание → Осмос → Сушка
    },
    3: {
        'name': 'Premium Wash',
        'description': 'Premium wash with all functions',
        'steps': [1, 2, 3, 4, 5, 6, 7],  # All functions
    },
    4: {
        'name': 'Express Wash',
        'description': 'Quick express wash',
        'steps': [1, 4],  # Химия 1 → Ополаскивание
    },
    5: {
        'name': 'Deluxe Wash',
        'description': 'Deluxe wash with repeat',
        'steps': [1, 2, 3, 4, 5, 6, 7, 1],  # All functions + repeat
    },
}

# To add a new program or modify existing:
# 1. Add/modify entry in PROGRAMS dict above
# 2. Add corresponding price in PRICES section below
# 3. Add register addresses in REGISTER_MAP section below


# ============================================================================
# PRICING CONFIGURATION
# ============================================================================

# Prices for each program (in rubles)
# Each program has a regular price and a loyalty price
PRICES: Dict[int, Dict[str, int]] = {
    1: {
        'regular': 200,   # Regular price for Program 1
        'loyalty': 180,   # Loyalty price for Program 1
    },
    2: {
        'regular': 300,
        'loyalty': 270,
    },
    3: {
        'regular': 500,
        'loyalty': 450,
    },
    4: {
        'regular': 150,
        'loyalty': 135,
    },
    5: {
        'regular': 700,
        'loyalty': 630,
    },
}

# To modify prices:
# 1. Update the values in PRICES dict above
# 2. Restart the emulator


# ============================================================================
# MODBUS REGISTER MAP
# ============================================================================

# This section defines where data is stored in Modbus memory
# IMPORTANT: These addresses must match your real PLC configuration
# DO NOT CHANGE unless you know your PLC uses different addresses

REGISTER_MAP = {
    # Program storage (Input Registers - read-only)
    'programs': {
        # Starting addresses for each program
        # Each program uses 15 consecutive registers
        'start_addresses': {
            1: 0,      # Program 1 starts at address 0
            2: 35,     # Program 2 starts at address 35
            3: 70,     # Program 3 starts at address 70
            4: 105,    # Program 4 starts at address 105
            5: 140,    # Program 5 starts at address 140
        },
        'count': 15,   # Number of registers per program
        'max_address': 154,  # Maximum address used (140 + 15 - 1)
    },
    
    # Price storage (Input Registers - read-only)
    'prices': {
        # Addresses for regular and loyalty prices
        'addresses': {
            'Price1': 30,          # Program 1 regular price
            'LoyaltyPrice1': 31,  # Program 1 loyalty price
            'Price2': 65,          # Program 2 regular price
            'LoyaltyPrice2': 66,  # Program 2 loyalty price
            'Price3': 100,         # Program 3 regular price
            'LoyaltyPrice3': 101, # Program 3 loyalty price
            'Price4': 135,         # Program 4 regular price
            'LoyaltyPrice4': 136, # Program 4 loyalty price
            'Price5': 170,         # Program 5 regular price
            'LoyaltyPrice5': 171, # Program 5 loyalty price
        },
        'max_address': 171,  # Maximum address used
    },
    
    # Start command coils (Coils - read/write)
    'coils': {
        # Coil addresses to start each program
        'start_addresses': {
            1: 0,   # Write True to coil 0 to start Program 1
            2: 1,   # Write True to coil 1 to start Program 2
            3: 3,   # Write True to coil 3 to start Program 3
            4: 4,   # Write True to coil 4 to start Program 4
            5: 5,   # Write True to coil 5 to start Program 5
        },
        'max_address': 5,
    },
    
    # Status discrete inputs (Discrete Inputs - read-only)
    'discrete_inputs': {
        # Address for wash status
        'wash_status': 0,  # Read discrete input 0 to check if wash is in progress
        'max_address': 0,
    },
    
    # Cash acceptor (Holding Registers - read/write)
    'cash': {
        # Address for cash amount
        # In real PLC this might be at address 16388, but we map it to 200 for simplicity
        'address': 200,  # Read/write holding register 200 for cash amount
        # If your real PLC uses address 16388, you may need to adjust your client code
        # or modify this emulator to handle high addresses
    },
}


# ============================================================================
# ADVANCED CONFIGURATION
# ============================================================================

# Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Enable detailed Modbus protocol logging (for debugging)
# Set to True to see all Modbus requests/responses
DEBUG_MODBUS = os.getenv('DEBUG_MODBUS', 'False').lower() == 'true'


# ============================================================================
# VALIDATION
# ============================================================================

# Validate configuration
def validate_config():
    """Validate that configuration is correct"""
    errors = []
    
    # Check that all programs have prices
    for prog_num in PROGRAMS.keys():
        if prog_num not in PRICES:
            errors.append(f"Program {prog_num} is defined but has no price")
    
    # Check that all prices have programs
    for price_num in PRICES.keys():
        if price_num not in PROGRAMS:
            errors.append(f"Price for program {price_num} is defined but program doesn't exist")
    
    # Check register map consistency
    for prog_num in PROGRAMS.keys():
        if prog_num not in REGISTER_MAP['programs']['start_addresses']:
            errors.append(f"Program {prog_num} has no register address defined")
        if prog_num not in REGISTER_MAP['coils']['start_addresses']:
            errors.append(f"Program {prog_num} has no start coil address defined")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True


# Run validation on import
try:
    validate_config()
except ValueError as e:
    print(f"WARNING: {e}")
    print("Emulator may not work correctly. Please fix configuration errors.")


# ============================================================================
# EXPORT CONFIGURATION
# ============================================================================

# This class is used by the emulator to access configuration
class PLCConfig:
    """Configuration class for PLC Emulator"""
    HOST = PLC_HOST
    PORT = PLC_PORT
    UNIT_ID = PLC_UNIT_ID
    PROGRAMS = PROGRAMS
    PRICES = PRICES
    REGISTER_MAP = REGISTER_MAP
    FUNCTIONS = FUNCTIONS
    LOG_LEVEL = LOG_LEVEL
    DEBUG_MODBUS = DEBUG_MODBUS

