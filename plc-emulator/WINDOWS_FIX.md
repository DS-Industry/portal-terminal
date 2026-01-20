# Windows Docker Compatibility Fix

## Issue
On Windows Docker, you may encounter the error:
```
argument --port: invalid int value
```

## Root Cause
Windows Docker handles environment variables differently than macOS/Linux, which can cause type conversion issues.

## Solution Applied

The code has been updated to:
1. **Handle invalid environment variables gracefully** - Falls back to defaults if env vars are malformed
2. **Use `parse_known_args()`** - Ignores unknown arguments that might come from Windows Docker
3. **Explicit type conversion** - Validates and converts port/unit_id values safely

## Additional Windows-Specific Fixes

### Option 1: Use Explicit Values in docker-compose.yml

Edit `docker-compose.yml` and use explicit values instead of environment variable expansion:

```yaml
environment:
  - PLC_HOST=0.0.0.0
  - PLC_PORT=502
  - PLC_UNIT_ID=1
```

### Option 2: Create .env File

Create a `.env` file in the `plc-emulator` directory:

```env
PLC_HOST=0.0.0.0
PLC_PORT=502
PLC_UNIT_ID=1
```

Then docker-compose will read from it automatically.

### Option 3: Use docker-compose.override.yml (Windows)

Create `docker-compose.override.yml`:

```yaml
version: "3.9"
services:
  plc-emulator:
    environment:
      - PLC_HOST=0.0.0.0
      - PLC_PORT=502
      - PLC_UNIT_ID=1
```

## Verification

After applying fixes, rebuild and test:

```bash
# Rebuild the image
docker-compose build

# Start the container
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify it's running
docker-compose ps
```

## Expected Output

You should see:
```
✅ Modbus TCP server started on 0.0.0.0:502
```

No errors about invalid port values.

## If Issues Persist

1. **Check environment variables in container:**
   ```bash
   docker exec plc-emulator env | grep PLC
   ```

2. **Check logs for specific errors:**
   ```bash
   docker-compose logs plc-emulator
   ```

3. **Test with explicit values:**
   ```bash
   docker run --rm -e PLC_PORT=502 -e PLC_HOST=0.0.0.0 plc-emulator:latest
   ```

## Differences: Windows vs macOS/Linux

| Aspect | macOS/Linux | Windows |
|--------|-------------|---------|
| Env var expansion | Works in docker-compose | May need explicit values |
| Path handling | Unix-style | Windows-style (but Docker handles) |
| Line endings | LF | CRLF (Docker handles) |
| Variable types | String (converted) | May need explicit conversion |

The updated code now handles all these differences automatically.

