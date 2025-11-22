from shared_config.constants import (
    ApiMethods,
    ExchangeConstants,
    ServiceConstants,
    WebsocketParameters,
)


def test_service_constants():
    assert ServiceConstants.REDIS_STREAM_MARKET == "stream:market_data"
    assert ServiceConstants.ERROR_TELEGRAM_ENABLED is True
    assert "orders" in ServiceConstants.ORDERS_TABLE


def test_websocket_parameters():
    assert WebsocketParameters.RECONNECT_BASE_DELAY == 5
    assert WebsocketParameters.WEBSOCKET_TIMEOUT > 0


def test_exchange_constants():
    assert ExchangeConstants.DERIBIT == "deribit"
    assert len(ExchangeConstants.SUPPORTED_EXCHANGES) >= 2


def test_api_methods():
    assert ApiMethods.GET_INSTRUMENTS == "public/get_instruments"
    assert "private" in ApiMethods.GET_ACCOUNT_SUMMARY
