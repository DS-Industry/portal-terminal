# Docker Network Setup: Connecting Two docker-compose Files

## How It Works

When you have two separate `docker-compose.yml` files, Docker networks allow containers from different compose files to communicate.

### Step-by-Step Process

1. **PLC Emulator creates the network** (when you run `docker-compose up` in `plc-emulator/`):
   ```yaml
   # plc-emulator/docker-compose.yml
   networks:
     plc-network:
       driver: bridge
       name: plc-emulator-network  # ← This creates a named network
   ```

2. **Main app connects to existing network** (using `external: true`):
   ```yaml
   # docker-compose.yml (main app)
   networks:
     plc-emulator-network:
       external: true              # ← Tells Docker: "Don't create, use existing"
       name: plc-emulator-network  # ← Must match the name from step 1
   ```

3. **Web service joins both networks**:
   ```yaml
   services:
     web:
       networks:
         - app-network           # For db, redis
         - plc-emulator-network  # For PLC emulator
   ```

## Important Points

✅ **Network name must match exactly** - `plc-emulator-network` in both files

✅ **PLC emulator must be started first** - So the network exists before main app tries to connect

✅ **External networks persist** - Even if you stop the PLC emulator, the network stays until you remove it

✅ **Containers can communicate** - Your web container can reach `plc-emulator:502` using the service name

## Startup Order

1. **Start PLC emulator first:**
   ```bash
   cd plc-emulator
   docker-compose up -d
   ```

2. **Then start main application:**
   ```bash
   cd ..  # Back to project root
   docker-compose up -d
   ```

## Verification

Check if networks are connected:

```bash
# List all networks
docker network ls

# Inspect the network (see which containers are connected)
docker network inspect plc-emulator-network

# Test connection from web container
docker exec -it <web-container-name> ping plc-emulator
```

## Troubleshooting

### Error: "network plc-emulator-network not found"

**Cause:** PLC emulator hasn't been started yet, or network was removed.

**Solution:**
```bash
# Start PLC emulator first
cd plc-emulator
docker-compose up -d

# Verify network exists
docker network ls | grep plc-emulator-network

# Then start main app
cd ..
docker-compose up -d
```

### Error: "network with name plc-emulator-network already exists"

**Cause:** Network exists but from a different source.

**Solution:**
```bash
# Check who created it
docker network inspect plc-emulator-network

# If needed, remove and recreate
docker network rm plc-emulator-network
cd plc-emulator
docker-compose up -d
```

### Containers can't communicate

**Check:**
1. Are both containers on the network?
   ```bash
   docker network inspect plc-emulator-network
   ```

2. Is the service name correct?
   - Use `plc-emulator` (the service name, not container name)
   - Port is `502` (internal container port)

3. Check logs:
   ```bash
   docker-compose logs web
   docker-compose -f plc-emulator/docker-compose.yml logs
   ```

## Alternative: Using Docker Compose Project Names

If you want to be more explicit, you can use project names:

```bash
# Start PLC emulator with project name
cd plc-emulator
docker-compose -p plc-emulator up -d

# Main app can still connect using external network
```

But the `external: true` approach is simpler and more common.

## Summary

✅ **Yes, it works!** Two separate docker-compose files can share a network.

✅ **Key requirement:** Network name must match exactly, and PLC emulator must start first.

✅ **Result:** Your web container can connect to `plc-emulator:502` just like it's on the same compose file.

