# src/shared/config/constants.py

"""
Static application constants
"""


class ServiceConstants:
    # Redis keys
    REDIS_STREAM_MARKET = "stream:market_data"
    REDIS_GROUP_DISPATCHER = "dispatcher_group"
    REDIS_STATE_CHANGE_CHANNEL = "events:state_change"
    REDIS_INSTRUMENT_INVALIDATE_CHANNEL = "system:cache:instrument:invalidate"

    REDIS_STREAMS = {
        "MARKET_DATA": "stream:market_data",
        "DISPATCHER": "dispatcher_group",
        "ERRORS": "stream:errors",
    }
    # Database
    DB_BASE_PATH = "/app/data"

    # Tables
    ORDERS_TABLE = "orders"
    OHLC_TABLE_PREFIX = "ohlc"

    # Error handling
    ERROR_TELEGRAM_ENABLED = True
    ERROR_REDIS_ENABLED = True


class WebsocketParameters:
    RECONNECT_BASE_DELAY = 5
    MAX_RECONNECT_DELAY = 3600
    MAINTENANCE_THRESHOLD = 300
    HEARTBEAT_INTERVAL = 30
    WEBSOCKET_TIMEOUT = 300


class ExchangeConstants:
    DERIBIT = "deribit"
    BINANCE = "binance"
    SUPPORTED_EXCHANGES = [DERIBIT, BINANCE]


class AddressUrl:
    DERIBIT_WS = "wss://www.deribit.com/ws/api/v2"


class AccountId:
    DERIBIT_MAIN = "deribit-148510"


class RedisChannels:
    CHART_UPDATE = "market.chart.all"
    CHART_LOW_HIGH_TICK = "market.chart.low_high_tick"
    TICKER_UPDATE_DATA = "market.ticker.data"
    TICKER_CACHE_UPDATING = "market.ticker.cached"
    MARKET_ANALYTICS_UPDATE = "market.analytics"
    ABNORMAL_TRADING_NOTICES = "market.abnormal_trading_notices"
    PORTFOLIO = "account.portfolio.ws"
    PORTFOLIO_REST = "account.portfolio.rest"
    ORDER_REST = "account.order.rest"
    ORDER_RECEIVING = "account.user_changes.order"
    MY_TRADE_RECEIVING = "account.user_changes.my_trade"
    SUB_ACCOUNT_RECEIVING = "account.user_changes.sub_account"
    ORDER_IS_ALLOWED = "account.is_order_allowed"
    ORDER_CACHE_UPDATING = "account.sub_account.cached_order"
    MY_TRADES_CACHE_UPDATING = "account.sub_account.cached_trade"
    POSITION_CACHE_UPDATING = "account.sub_account.cached_positions"
    SUB_ACCOUNT_CACHE_UPDATING = "account.sub_account.cached_all"
    MARKET_SUMMARY_UPDATING = "others.summary.cached_all"
    ACCOUNT_SUMMARY_UPDATING = "others.summary.cached_all"
    SQLITE_RECORD_UPDATING = "others.sqlite_record_updating"


class ApiMethods:
    """Centralizes the string names for API endpoints."""

    # Public
    GET_INSTRUMENTS = "public/get_instruments"
    GET_TRADINGVIEW_CHART_DATA = "public/get_tradingview_chart_data"

    # Private
    GET_ACCOUNT_SUMMARY = "private/get_account_summary"
    GET_TRANSACTION_LOG = "private/get_transaction_log"
    GET_SUBACCOUNTS_DETAILS = "private/get_subaccounts_details"
    GET_OPEN_ORDERS_BY_CURRENCY = "private/get_open_orders_by_currency"
    GET_USER_TRADES_BY_ORDER = "private/get_user_trades_by_order"
    CANCEL_ORDER = "private/cancel"
    SIMULATE_PME = "private/pme/simulate"
