import importlib
import os
from unittest.mock import mock_open, patch

import pytest

# We import the module, but we will reload it inside tests to apply mocks
import shared_config.config as config_module


@pytest.fixture
def clean_env():
    """Save and restore environment variables."""
    old_env = os.environ.copy()
    os.environ.clear()
    # Set minimal required env vars
    os.environ["SERVICE_NAME"] = "test_service"
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    yield
    os.environ.clear()
    os.environ.update(old_env)


def reload_config():
    """Helper to reload the config module so it reads new Env Vars."""
    importlib.reload(config_module)
    return config_module.load_settings()


def test_read_secret_direct_value():
    """Test read_secret returns value if no file provided."""
    assert config_module.read_secret("my_secret", None) == "my_secret"


def test_read_secret_from_file():
    """Test read_secret prefers file content."""
    with patch("pathlib.Path.read_text", return_value="file_secret"):
        with patch("os.path.exists", return_value=True):
            assert config_module.read_secret("env_secret", "/run/secrets/s") == "file_secret"


def test_read_secret_file_missing():
    """Test fallback if file path provided but does not exist."""
    with patch("os.path.exists", return_value=False):
        assert config_module.read_secret("env_secret", "/missing/file") == "env_secret"


def test_read_secret_file_error():
    """Test graceful handling of file read errors."""
    with patch("os.path.exists", return_value=True):
        with patch("pathlib.Path.read_text", side_effect=PermissionError("Denied")):
            # Should return None (failure) or fallback?
            # Code implementation returns None on exception if file exists
            assert config_module.read_secret(None, "/run/secrets/s") is None


def test_load_settings_basic(clean_env):
    """Test loading minimal settings."""
    settings = reload_config()
    assert settings.service_name == "test_service"
    assert settings.redis.url == "redis://localhost:6379"
    assert settings.environment == "testing"


def test_exchange_config_loading(clean_env):
    """Test parsing EXCHANGES__... env vars."""
    os.environ["EXCHANGES__DERIBIT__CLIENT_ID"] = "id_123"
    os.environ["EXCHANGES__DERIBIT__WS_URL"] = "wss://test"

    settings = reload_config()
    assert "deribit" in settings.exchanges
    assert settings.exchanges["deribit"].client_id == "id_123"
    assert settings.exchanges["deribit"].ws_url == "wss://test"


def test_deribit_secrets_file_override(clean_env):
    """Test that Deribit secrets can be loaded from specific file env vars."""
    os.environ["DERIBIT_CLIENT_ID_FILE"] = "/secrets/id"
    os.environ["EXCHANGES__DERIBIT__WS_URL"] = "wss://test"  # Required to init exchange dict

    with patch("pathlib.Path.read_text", return_value="secret_id_from_file"):
        with patch("os.path.exists", return_value=True):
            settings = reload_config()

    assert settings.exchanges["deribit"].client_id == "secret_id_from_file"


def test_postgres_config_for_db_service(clean_env):
    """Test that DB services fail without a password."""
    os.environ["SERVICE_NAME"] = "executor"  # Requires DB
    os.environ["POSTGRES_USER"] = "user"
    os.environ["POSTGRES_DB"] = "db"

    # Case 1: No password -> Error
    with pytest.raises(ValueError, match="PostgreSQL password could not be loaded"):
        reload_config()

    # Case 2: Password present -> Success
    os.environ["POSTGRES_PASSWORD"] = "pass123"
    settings = reload_config()
    assert settings.postgres.password == "pass123"


def test_oci_config_loading(clean_env):
    """Test OCI config loading for executor service."""
    os.environ["SERVICE_NAME"] = "executor"
    os.environ["POSTGRES_PASSWORD"] = "pg_pass"  # Satisfy PG requirement

    # Missing OCI vars
    with pytest.raises(ValueError, match="Executor service requires OCI"):
        reload_config()

    # Set OCI vars
    os.environ["OCI_DSN_FILE"] = "/s/dsn"
    os.environ["OCI_USER_FILE"] = "/s/user"
    os.environ["OCI_PASSWORD_FILE"] = "/s/pass"
    os.environ["OCI_WALLET_DIR"] = "/s/wallet"

    with patch("os.path.exists", return_value=True):
        with patch("pathlib.Path.read_text", side_effect=["dsn_val", "user_val", "pass_val"]):
            settings = reload_config()

    assert settings.oci.dsn == "dsn_val"
    assert settings.oci.user == "user_val"
    assert settings.oci.wallet_dir == "/s/wallet"


def test_oci_tns_parsing():
    """Test the Pydantic validator for TNS alias parsing."""
    from shared_config.config import OciConfig

    # 1. Clean alias
    c1 = OciConfig(dsn="my_alias", user="u", password="p", wallet_dir="w")
    assert c1.dsn == "my_alias"

    # 2. Full URL
    c2 = OciConfig(
        dsn="oracle+oracledb://user:pass@my_alias_high?param=1",
        user="u",
        password="p",
        wallet_dir="w",
    )
    assert c2.dsn == "my_alias_high"

    # 3. Just @ split
    c3 = OciConfig(dsn="user:pass@my_alias_low", user="u", password="p", wallet_dir="w")
    assert c3.dsn == "my_alias_low"


def test_strategy_config_loading(clean_env):
    """Test loading from TOML file."""
    # Mock tomli.load
    mock_toml = {"strategies": [{"strategy_label": "strat1"}]}

    with patch("builtins.open", mock_open(read_data=b"data")):
        with patch("tomli.load", return_value=mock_toml):
            settings = reload_config()

    assert settings.strategies[0]["strategy_label"] == "strat1"
    assert "strat1" in settings.strategy_map


def test_market_map_computation(clean_env):
    """Test that market_map is hydrated from exchanges config."""

    # Setup environment
    os.environ["EXCHANGES__DERIBIT__WS_URL"] = "wss://deribit"

    # We need to inject market definitions via toml load or manually
    mock_toml = {
        "market_definitions": [
            # We mock the data structure that tomli would return.
            # Pydantic validation happens inside load_settings -> AppSettings.
            {
                "market_id": "btc-perp",
                "exchange": "deribit",
                "symbol": "BTC-PERP",
                "market_type": "future",
                "base_asset": "BTC",
                "quote_asset": "USD",
                "tick_size": 0.5,
                "contract_size": 10.0,
            }
        ]
    }

    with patch("builtins.open", mock_open(read_data=b"")):
        with patch("tomli.load", return_value=mock_toml):
            settings = reload_config()

    assert "btc-perp" in settings.market_map
    mm = settings.market_map["btc-perp"]
    assert mm.ws_base_url == "wss://deribit"
    assert mm.market_id == "btc-perp"
