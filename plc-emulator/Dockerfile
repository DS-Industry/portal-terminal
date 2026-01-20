FROM python:3.12-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py /app/config.py
COPY plc_emulator.py /app/plc_emulator.py

# Make executable
RUN chmod +x /app/plc_emulator.py

# Expose Modbus TCP port
# Note: Port 502 requires root privileges, consider using 5020 for non-root
EXPOSE 502

# Health check
# Note: Health check uses port 502 (internal container port)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from pymodbus.client import ModbusTcpClient; import os; port = int(os.getenv('PLC_PORT', '502')); c = ModbusTcpClient('localhost', port); exit(0 if c.connect() else 1); c.close()" || exit 1

# Run emulator
# The script reads from environment variables (PLC_HOST, PLC_PORT, PLC_UNIT_ID)
# or from config.py. Environment variables take precedence.
# Use shell form to allow variable expansion if needed, or just let Python read env vars
CMD python /app/plc_emulator.py

