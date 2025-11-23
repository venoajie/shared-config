Excellent question. You've identified that the monolithic `strategies.toml` is a legacy artifact that directly contradicts the principles of your polyrepo architecture.

The best way forward is to **decentralize the configuration** so that each service owns its specific settings. This aligns with the core philosophy of service isolation and independent deployment.

Here is the architecturally-sound plan to redefine your configuration.

---

### The Plan: Service-Specific Configuration Files

The monolithic file will be split into smaller, domain-focused files. Each service will load a "base" configuration and then its own specific file.

#### 1. The New File Structure

Your `shared-config` repository will change like this:

**Before:**
```
src/shared_config/
└── strategies.toml  (monolith)
```

**After:**
```
src/shared_config/
├── business_logic.toml  (Shared, high-level business rules)
├── analyzer.toml
├── backfill.toml
├── distributor.toml
├── executor.toml
├── maintenance.toml
└── receiver.toml
```

#### 2. How to Split the Content

**File:** `business_logic.toml` (Shared by multiple services)
This file contains high-level business logic, not operational tuning.

```toml
# src/shared_config/business_logic.toml

# Defines the symbols that are part of the core business strategy.
# Consumed by: Janitor, Receiver
[[tradable]]
spot = [ "BTC", "ETH" ]

[[public_symbols]]
symbol = "BTCUSDT"
market_type = "spot"

# A list of all available strategy labels.
# Consumed by: Executor
strategy_labels = [
    "hedgingSpot",
    "futureSpread",
    "comboAuto",
    "scalping",
    "custom",
]

# Defines risk parameters.
# Consumed by: Executor
[[market_situation]]
market_situation = "NEUTRAL"
hedging_ratio = 80
# ... other market situations ...

# Defines the detailed parameters for trading strategies.
# Consumed by: Executor
[[strategies]]
strategy_label = "hedgingSpot"
is_active = true
# ... other strategy details ...
```

**File:** `receiver.toml` (Specific to the `receiver` service)

```toml
# src/shared_config/receiver.toml

# This section configures the real-time data ingestion clients.
# Each entry launches a dedicated WebSocket client within the 'receiver' service.
[[market_definitions]]
market_id = "deribit_inverse"
exchange = "deribit"
market_type = "inverse_futures" # Corrected value
mode = "full"

[[market_definitions]]
market_id = "binance_spot"
exchange = "binance"
market_type = "spot"
mode = "full"

[realtime]
# The Redis channel used by the 'binance' receiver to dynamically manage subscriptions.
binance_subscription_control_channel = "control:binance:subscriptions"
```

**File:** `backfill.toml` (Specific to `janitor` and `backfill`)

```toml
# src/shared_config/backfill.toml

[backfill]
start_date = "2025-07-01"
resolutions = ["1", "5", "15", "60", "1D"]
bootstrap_target_candles = 6000
worker_count = 4
ohlc_backfill_whitelist = [
    "BTC-PERPETUAL",
    "ETH-PERPETUAL",
    "BTCUSDT",
    "ETHUSDT"
]

[backfill.public_trades]
enabled = false
lookback_days = 7
whitelist = [ "BTCUSDT", "ETHUSDT", "SOLUSDT" ]
```

*(You would create similar specific files for `analyzer.toml`, `distributor.toml`, etc.)*

#### 3. How to Update the `config.py` Loader

The `load_settings()` function will be modified to load files based on the service name.

**File:** `src/shared_config/config.py` (Conceptual Change)

```python
# ... (imports) ...

class RawEnvSettings(BaseSettings):
    SERVICE_NAME: str = "unknown"
    # --- ADD ENVIRONMENT VARIABLES FOR THE NEW FILE PATHS ---
    BUSINESS_LOGIC_CONFIG_PATH: str = str(Path(__file__).parent / "business_logic.toml")
    SERVICE_CONFIG_PATH: str | None = None # This will be set per-service

# ... (other classes) ...

def load_settings() -> AppSettings:
    log.info("Loading application configuration...")
    raw_env = RawEnvSettings()

    # 1. Load the BASE business logic that applies to everyone
    business_data = {}
    try:
        with open(raw_env.BUSINESS_LOGIC_CONFIG_PATH, "rb") as f:
            business_data = tomli.load(f)
        log.info(f"Successfully loaded base config from {raw_env.BUSINESS_LOGIC_CONFIG_PATH}")
    except FileNotFoundError:
        log.warning("Base business_logic.toml not found. Continuing with defaults.")

    # 2. Load the SERVICE-SPECIFIC configuration
    service_data = {}
    # Construct the expected path, e.g., .../shared_config/janitor.toml
    service_config_path = str(Path(__file__).parent / f"{raw_env.SERVICE_NAME}.toml")

    try:
        with open(service_config_path, "rb") as f:
            service_data = tomli.load(f)
        log.info(f"Successfully loaded service config from {service_config_path}")
    except FileNotFoundError:
        log.warning(f"Service-specific config not found at {service_config_path}. Service may not need one.")

    # 3. Merge the configurations (service-specific values override base values)
    toml_data = {**business_data, **service_data}

    # ... (the rest of the function remains the same, processing raw_env and final_data)
```

### Benefits of This Approach

1.  **Service Isolation:** The `receiver` configuration can be changed and deployed without touching or validating settings for the `executor`.
2.  **Reduced Blast Radius:** A typo in `analyzer.toml` will only affect the `analyzer` service, not the entire system.
3.  **Clarity:** Developers working on the `distributor` only need to look at `distributor.toml`, which is small and focused.
4.  **Aligns with Polyrepo:** This configuration strategy mirrors your code strategy: small, independent, and well-defined units.