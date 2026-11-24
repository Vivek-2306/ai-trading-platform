"""The instruments we collect. Adding one here (and running a backfill) is all it takes."""

from dataclasses import dataclass

from app.data.models import AssetClass


@dataclass(frozen=True, slots=True)
class InstrumentSpec:
    venue: str
    symbol: str
    asset_class: AssetClass


CRYPTO = (
    InstrumentSpec("binance", "BTC/USDT", AssetClass.CRYPTO),
    InstrumentSpec("binance", "ETH/USDT", AssetClass.CRYPTO),
)
# Gold: PAXG tracks spot gold and trades 24/7 on Binance with no key (the default).
GOLD_PAXG = InstrumentSpec("binance", "PAXG/USDT", AssetClass.GOLD)
# True spot gold, only when TWELVE_DATA_API_KEY is set. See ADR 0003.
GOLD_SPOT = InstrumentSpec("twelvedata", "XAU/USD", AssetClass.GOLD)


def default_universe(*, twelve_data_enabled: bool) -> list[InstrumentSpec]:
    specs = [*CRYPTO, GOLD_PAXG]
    if twelve_data_enabled:
        specs.append(GOLD_SPOT)
    return specs
