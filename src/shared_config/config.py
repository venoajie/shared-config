
# src\shared_config\config.py

"""
Primary configuration loader. SINGLE SOURCE OF TRUTH.
This module provides a singleton `settings` object that is populated once on startup.
"""
import os
import tomli
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, model_validator, ConfigDict, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger as log
from pathlib import Path

# MarketDefinition is a core data contract and must be imported from the appropriate shared library.
from trading_engine_core.models import MarketDefinition


# --- Helper Function for reading secrets --- ADDED
def read_secret(value: Optional[str], file_path: Optional[str]) -> Optional[str]:
    """
    Reads a secret, prioritizing the file path if provided and valid.
    Falls back to the direct value.
    """
    if file_path and os.path.exists(file_path):
        try:
            return Path(file_path).read_text().strip()
        except Exception as e:
            log.error(f"Failed to read secret from file {file_path}: {e}")
            return None
    return value


class ExchangeSettings(BaseModel):
    account_id: Optional[str] = None
    ws_url: Optional[str] = None
    rest_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    model_config = ConfigDict(extra="allow")

class OciConfig(BaseModel):
    dsn: str
    wallet_dir: str
    
    @model_validator(mode='after')
    def parse_tns_alias(self) -> 'OciConfig':
        """
        Parses the TNS alias from a full Oracle connection string.
        Input format example: oracle+oracledb://user:pass@alias_name?param=value
        Target output: alias_name
        """
        # 1. Isolate the part after credentials (after the last '@')
        if '@' in self.dsn:
            self.dsn = self.dsn.split('@')[-1]
            
        # 2. Remove any query parameters (after the first '?')
        if '?' in self.dsn:
            self.dsn = self.dsn.split('?')[0]
            
        return self


class MaintenanceSettings(BaseModel):
    public_trades_retention_period: str = "24 hours"


class DistributorSettings(BaseModel):
    public_trades_retention_period: str = "1 hour"
    pruning_interval_s: int = 600


class PostgresSettings(BaseModel):
    user: str
    password: str
    host: str
    port: int
    db: str

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseModel):
    url: str
    db: int
    password: Optional[str] = None


# --- ADDED: Model for OCI Database Settings ---
class OCISettings(BaseModel):
    user: str
    password: str
    dsn: str
    wallet_dir: str


class AnalyzerSettings(BaseModel):
    consumer_name: str = "analyzer-1"
    group_name: str = "analyzer_group"
    instrument_sync_interval_s: int = 3600
    anomaly_check_interval_s: int = 15
    volume_window_recent_s: int = 60
    volume_window_historical_s: int = 3600
    anomaly_threshold_multiplier: float = 5.0
    alert_cooldown_s: int = 300
    blacklist: List[str] = Field(default_factory=list)


class PublicTradesBackfillSettings(BaseModel):
    enabled: bool = False
    lookback_days: int = 7
    whitelist: List[str] = Field(default_factory=list)


class BackfillSettings(BaseModel):
    start_date: str = "2025-07-01"
    resolutions: List[Union[int, str]] = Field(default_factory=lambda: ["1", "5", "15", "60", "1D"])
    bootstrap_target_candles: int = 6000
    worker_count: int = 4
    ohlc_backfill_whitelist: List[str] = Field(default_factory=list)
    public_trades: Optional[PublicTradesBackfillSettings] = None


class AppSettings(BaseModel):
    service_name: str
    environment: str
    strategy_config_path: str
    exchanges: Dict[str, ExchangeSettings] = Field(default_factory=dict)
    market_definitions: List[MarketDefinition] = Field(default_factory=list)
    redis: RedisSettings
    postgres: Optional[PostgresSettings] = None
    # --- ADDED: Field for OCI settings ---
    oci: Optional[OCISettings] = None
    analyzer: Optional[AnalyzerSettings] = None
    tradable: List[Dict] = []
    strategies: List[Dict] = []
    all_instruments: List[Dict] = Field(default_factory=list)
    hedged_currencies: List[str] = []
    market_situation: List[Dict] = []
    strategy_map: Dict[str, Any] = Field(default_factory=dict, exclude=True)
    realtime: Dict[str, Any] = Field(default_factory=dict)
    backfill: Optional[BackfillSettings] = None
    public_symbols: List[Dict[str, str]] = Field(default_factory=list)
    maintenance: Optional[MaintenanceSettings] = None
    distributor: Optional[DistributorSettings] = None

    @computed_field
    @property
    def market_map(self) -> Dict[str, MarketDefinition]:
        hydrated_market_map = {}
        for md in self.market_definitions:
            exchange_config = self.exchanges.get(md.exchange)
            if not exchange_config:
                log.warning(f"Config Warning: Market '{md.market_id}' specifies exchange '{md.exchange}', but no connection details found. Skipping.")
                continue
            md.ws_base_url = exchange_config.ws_url
            md.rest_base_url = exchange_config.rest_url
            hydrated_market_map[md.market_id] = md
        if hydrated_market_map:
            log.info(f"Built and hydrated market map for IDs: {list(hydrated_market_map.keys())}")
        return hydrated_market_map

    @model_validator(mode="after")
    def build_other_derived_fields(self) -> "AppSettings":
        derived_hedged_currencies = []
        if self.tradable:
            for tradable_item in self.tradable:
                derived_hedged_currencies.extend(tradable_item.get("spot", []))
        self.hedged_currencies = sorted(list(set(derived_hedged_currencies)))
        self.strategy_map = {s.get("strategy_label"): s for s in self.strategies}
        if self.strategy_map:
            log.info(f"Built strategy map for labels: {list(self.strategy_map.keys())}")
        return self


class RawEnvSettings(BaseSettings):
    SERVICE_NAME: str = "unknown"
    ENVIRONMENT: str = "development"
    STRATEGY_CONFIG_PATH: str = "/app/src/shared/config/strategies.toml"
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    POSTGRES_USER: str = "trading_app"
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_PASSWORD_FILE: Optional[str] = None
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "trading"

    # --- ADDED: Fields for Deribit and OCI file-based secrets ---
    DERIBIT_CLIENT_ID_FILE: Optional[str] = None
    DERIBIT_CLIENT_SECRET_FILE: Optional[str] = None
    OCI_DSN_FILE: Optional[str] = None
    OCI_USER_FILE: Optional[str] = None
    OCI_PASSWORD_FILE: Optional[str] = None
    OCI_WALLET_DIR: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


def load_settings() -> AppSettings:
    log.info("Loading application configuration...")
    raw_env = RawEnvSettings()
    
    # --- Logic to handle exchange API keys from files ---
    exchanges_data = {}
    for key, value in os.environ.items():
        key = key.lower()
        if key.startswith("exchanges__"):
            parts = key.split("__")
            if len(parts) == 3:
                _, exchange_name, field_name = parts
                if exchange_name not in exchanges_data:
                    exchanges_data[exchange_name] = {}
                exchanges_data[exchange_name][field_name] = value

    # Override with file-based secrets if available for Deribit
    if "deribit" in exchanges_data:
        deribit_client_id = read_secret(exchanges_data["deribit"].get("client_id"), raw_env.DERIBIT_CLIENT_ID_FILE)
        deribit_client_secret = read_secret(exchanges_data["deribit"].get("client_secret"), raw_env.DERIBIT_CLIENT_SECRET_FILE)
        if deribit_client_id:
            exchanges_data["deribit"]["client_id"] = deribit_client_id
        if deribit_client_secret:
            exchanges_data["deribit"]["client_secret"] = deribit_client_secret

    toml_data = {}
    try:
        with open(raw_env.STRATEGY_CONFIG_PATH, "rb") as f:
            toml_data = tomli.load(f)
        log.info(f"Successfully loaded strategy config from {raw_env.STRATEGY_CONFIG_PATH}")
    except (FileNotFoundError, AttributeError):
        log.warning(f"Strategy config file not found at {raw_env.STRATEGY_CONFIG_PATH}. Skipping.")


    final_data = {
        "service_name": raw_env.SERVICE_NAME,
        "environment": raw_env.ENVIRONMENT,
        "strategy_config_path": raw_env.STRATEGY_CONFIG_PATH,
        "exchanges": exchanges_data,
        "redis": {
            "url": raw_env.REDIS_URL,
            "db": raw_env.REDIS_DB,
            "password": raw_env.REDIS_PASSWORD,
        },        
        "analyzer": {}, # Force creation with defaults
        **toml_data,
    }
   
    # --- Use the helper function for Postgres password ---
    pg_password = read_secret(raw_env.POSTGRES_PASSWORD, raw_env.POSTGRES_PASSWORD_FILE)
    services_requiring_db = ["distributor", "executor", "janitor", "receiver", "analyzer", "backfill"]
    if raw_env.SERVICE_NAME in services_requiring_db:
        if not pg_password:
            raise ValueError(f"PostgreSQL password could not be loaded for service '{raw_env.SERVICE_NAME}'.")
        final_data["postgres"] = {
            "user": raw_env.POSTGRES_USER,
            "password": pg_password,
            "host": raw_env.POSTGRES_HOST,
            "port": raw_env.POSTGRES_PORT,
            "db": raw_env.POSTGRES_DB,
        }

    # --- CORRECTED: Conditional logic to load OCI settings for the executor ---
    if raw_env.SERVICE_NAME == "executor":
        oci_dsn = read_secret(None, raw_env.OCI_DSN_FILE)
        oci_user = read_secret(None, raw_env.OCI_USER_FILE)
        oci_password = read_secret(None, raw_env.OCI_PASSWORD_FILE)
        oci_wallet_dir = raw_env.OCI_WALLET_DIR
        if all([oci_dsn, oci_user, oci_password, oci_wallet_dir]):
            log.info("Loading OCI database configuration for executor service.")
            final_data["oci"] = OCISettings(
                dsn=oci_dsn,
                user=oci_user,
                password=oci_password,
                wallet_dir=oci_wallet_dir
            )
        else:
            raise ValueError("Executor service requires OCI_DSN_FILE, OCI_USER_FILE, OCI_PASSWORD_FILE, and OCI_WALLET_DIR.")

    final_settings = AppSettings.model_validate(final_data)
    log.info(f"Configuration loaded for service '{final_settings.service_name}' in '{final_settings.environment}' environment.")
    return final_settings

settings = load_settings()