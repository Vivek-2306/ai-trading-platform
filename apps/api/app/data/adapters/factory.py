"""Pick the adapter for a venue."""

from app.core.config import Settings
from app.data.adapters.base import AdapterError, MarketDataAdapter
from app.data.adapters.binance import BinanceAdapter
from app.data.adapters.twelvedata import TwelveDataAdapter


def build_adapter(venue: str, settings: Settings) -> MarketDataAdapter:
    if venue == "binance":
        return BinanceAdapter()
    if venue == "twelvedata":
        if settings.twelve_data_api_key is None:
            raise AdapterError("TWELVE_DATA_API_KEY is not set")
        return TwelveDataAdapter(settings.twelve_data_api_key)
    raise AdapterError(f"unknown venue: {venue}")
