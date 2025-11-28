
# src/shared_config/config.py

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import tomli
from loguru import logger as log
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Helper Function (Correct and necessary) ---
def read_secret(value: str | None, file_path: str | None) -> str | None:
    if file_path and os.path.exists(file_path):
        try:
            return Path(file_path).read_text().strip()
        except Exception as e:
            log.error(f"Failed to read secret from file {file_path}: {e}")
            return None
    return value

# --- TYPE-SAFE, HIERARCHICAL MODELS ---

# --- Infrastructure Models ---
class ExchangeSettings(BaseModel):
    client_id: str
    client_secret: str
    ws_url: Optional[str] = None
    rest_url: Optional[str] = None

class RedisSettings(BaseModel):
    url: str
    db: int
    password: Optional[str] = None

class PostgresSettings(BaseModel):
    user: str
    password: str
    host: str
    port: int
    db: str

class OCISettings(BaseModel):
    user: str
    password: str
    dsn: str
    wallet_dir: str

# --- Business Logic Models (for executor.toml) ---
class RiskManagementSettings(BaseModel):
    max_order_notional_usd: float
    max_position_notional_usd: float
    price_deviation_tolerance_pct: float
    equity_dust_threshold: float

class ReconciliationSettings(BaseModel):
    interval_seconds: int
    initial_delay_seconds: int

class ExecutorServiceSettings(BaseModel):
    reconciliation: ReconciliationSettings

class RegimeParameterSettings(BaseModel):
    hedge_ratio: float
    execution_horizon_minutes: int
    order_type: str
    time_in_force: str
    ttl_seconds: int

class UsdSyntheticStrategySettings(BaseModel):
    drift_threshold_contracts: int
    twap_clip_pct: float

class StrategySettings(BaseModel):
    usdSynthetic: UsdSyntheticStrategySettings

class RedisStreamSettings(BaseModel):
    max_retries: int = 3

class TradableItem(BaseModel):
    spot: List[str]

class AnalyzerSettings(BaseModel):
    # These fields would be moved from the TOML file into this structure
    instrument_sync_interval_s: int = 3600
    anomaly_check_interval_s: int = 15
    
class BackfillSettings(BaseModel):
    # ... (fields for backfill)
    pass

class DistributorSettings(BaseModel):
    # ... (fields for distributor)
    pass

class JanitorSettings(BaseModel):
    # ... (fields for janitor)
    pass

class MaintenanceSettings(BaseModel):
    # ... (fields for maintenance)
    pass


# --- THE CENTRAL SERVICE CONTAINER ---
class ServiceSettings(BaseModel):
    """This model contains all optional, service-specific operational configs."""
    executor: Optional[ExecutorServiceSettings] = None
    analyzer: Optional[AnalyzerSettings] = None
    # distributor: Optional[DistributorSettings] = None # Future
    # maintenance: Optional[MaintenanceSettings] = None # Future

# --- AppSettings now uses the central container ---
class AppSettings(BaseModel):
    # ... (service_name, environment, exchanges, etc. are correct) ...

    # This is now the single point of entry for all service-specific operational settings
    services: Optional[ServiceSettings] = None
    
# --- COMPOSITED TOP-LEVEL SETTINGS OBJECT ---
class AppSettings(BaseModel):
    service_name: str
    environment: str
    
    # --- Infrastructure (Mandatory) ---
    exchanges: Dict[str, ExchangeSettings]
    redis: RedisSettings
    redis_streams: RedisStreamSettings = Field(default_factory=RedisStreamSettings) # Added

    # --- Infrastructure (Optional) ---
    postgres: Optional[PostgresSettings] = None
    oci: Optional[OCISettings] = None
    
    # --- Service-Specific Business Logic (All Optional) ---
    # Pydantic will only populate these if the sections exist in the TOML file.
    risk_management: Optional[RiskManagementSettings] = None
    services: Optional[ServiceSettings] = None
    regime_parameters: Optional[Dict[str, RegimeParameterSettings]] = None
    strategies: Optional[StrategySettings] = None
    tradable: List[TradableItem] = []
    analyzer: Optional[AnalyzerSettings] = None
    
    # --- Derived Properties ---
    hedged_currencies: List[str] = []

    @model_validator(mode="after")
    def build_derived_fields(self) -> "AppSettings":
        if self.tradable:
            derived_hedged_currencies = []
            for item in self.tradable:
                derived_hedged_currencies.extend(item.spot)
            self.hedged_currencies = sorted(set(derived_hedged_currencies))
        return self

# --- Environment Variable Loader (Correct) ---
class RawEnvSettings(BaseSettings):
    SERVICE_NAME: str = "unknown"
    ENVIRONMENT: str = "development"
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    POSTGRES_USER: str = "trading_app"
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_PASSWORD_FILE: Optional[str] = None
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "trading"
    DERIBIT_CLIENT_ID_FILE: Optional[str] = None
    DERIBIT_CLIENT_SECRET_FILE: Optional[str] = None
    OCI_DSN_FILE: Optional[str] = None
    OCI_USER_FILE: Optional[str] = None
    OCI_PASSWORD_FILE: Optional[str] = None
    OCI_WALLET_DIR: Optional[str] = None
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# --- REFACTORED load_settings() FUNCTION ---
def load_settings() -> AppSettings:
    log.info("Loading application configuration...")
    raw_env = RawEnvSettings()

    # 1. Load the service-specific TOML file.
    toml_data = {}
    service_config_path = Path(__file__).parent / f"{raw_env.SERVICE_NAME}.toml"
    try:
        with open(service_config_path, "rb") as f:
            toml_data = tomli.load(f)
        log.info(f"Successfully loaded service-specific config from {service_config_path}")
    except FileNotFoundError:
        log.warning(f"No service-specific config found at {service_config_path}. This may be normal.")

    # 2. Assemble the final data dictionary for validation.
    final_data = {
        "service_name": raw_env.SERVICE_NAME,
        "environment": raw_env.ENVIRONMENT,
        # Infrastructure from environment
        "exchanges": {
            "deribit": ExchangeSettings(
                client_id=read_secret(None, raw_env.DERIBIT_CLIENT_ID_FILE),
                client_secret=read_secret(None, raw_env.DERIBIT_CLIENT_SECRET_FILE),
            )
        },
        "redis": RedisSettings(
            url=raw_env.REDIS_URL, db=raw_env.REDIS_DB, password=raw_env.REDIS_PASSWORD
        ),
        # Inject the entire loaded TOML data structure
        **toml_data,
    }

    # 3. Conditionally add DB connections
    services_requiring_db = ["distributor", "executor", "janitor", "maintenance", "analyzer", "backfill"]
    if raw_env.SERVICE_NAME in services_requiring_db:
        pg_password = read_secret(raw_env.POSTGRES_PASSWORD, raw_env.POSTGRES_PASSWORD_FILE)
        if not pg_password:
            raise ValueError(f"PostgreSQL password not found for service '{raw_env.SERVICE_NAME}'.")
        final_data["postgres"] = PostgresSettings(
            user=raw_env.POSTGRES_USER, password=pg_password,
            host=raw_env.POSTGRES_HOST, port=raw_env.POSTGRES_PORT, db=raw_env.POSTGRES_DB,
        )
    
    if raw_env.SERVICE_NAME == "executor":
        oci_dsn = read_secret(None, raw_env.OCI_DSN_FILE)
        oci_user = read_secret(None, raw_env.OCI_USER_FILE)
        oci_password = read_secret(None, raw_env.OCI_PASSWORD_FILE)
        if all([oci_dsn, oci_user, oci_password, raw_env.OCI_WALLET_DIR]):
            final_data["oci"] = OCISettings(
                dsn=oci_dsn, user=oci_user, password=oci_password, wallet_dir=raw_env.OCI_WALLET_DIR
            )
        else:
            raise ValueError("Executor service is missing required OCI secrets.")

    # 4. Validate the entire structure with Pydantic
    final_settings = AppSettings.model_validate(final_data)
    log.info(f"Configuration for '{final_settings.service_name}' loaded and validated.")
    return final_settings

settings = load_settings()