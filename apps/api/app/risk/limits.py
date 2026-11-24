"""Risk limits, read from environment variables (prefix RISK_) with conservative defaults.

The defaults are safe for anyone. Your own values (capital, tighter limits) belong in the
git-ignored env file, never in the repo. Values outside the hard ceilings below are rejected
at startup, so a typo cannot quietly turn a 0.5% risk into 50%.
"""

from decimal import Decimal
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import ENV_FILE

D = Decimal


class RiskLimits(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RISK_", env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # Money you are willing to put at work, in the quote currency (USDT). A placeholder: set
    # RISK_CAPITAL in your env file. Sizing is only as real as this number.
    capital: Decimal = Field(default=D("1000"), gt=0)
    # Loss if the stop is hit, as a percent of capital. Hard ceiling 2%.
    risk_per_trade_pct: Decimal = Field(default=D("0.5"), gt=0, le=2)
    # One position may use at most this percent of capital.
    max_capital_share_pct: Decimal = Field(default=D("20"), gt=0, le=100)
    # No new entries once today's realised losses reach this percent of capital. Ceiling 10%.
    max_daily_loss_pct: Decimal = Field(default=D("2"), gt=0, le=10)
    max_open_positions: int = Field(default=3, ge=1, le=20)
    # A setup must offer at least this much reward for each unit of risk.
    min_risk_reward: Decimal = Field(default=D("1.5"), ge=1)
    # Stop and target distances in ATR multiples (ATR = average candle range).
    stop_atr_multiple: Decimal = Field(default=D("1.5"), ge=D("0.5"), le=10)
    target_atr_multiple: Decimal = Field(default=D("3"), gt=0, le=20)
    # Refuse setups whose stop is further than this percent below the entry.
    max_stop_distance_pct: Decimal = Field(default=D("10"), gt=0, le=50)
    # Needed to switch the kill switch OFF through the API (switching it ON never needs it).
    admin_token: SecretStr | None = None

    @field_validator("admin_token", mode="before")
    @classmethod
    def _empty_means_unset(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator(
        "capital",
        "risk_per_trade_pct",
        "max_capital_share_pct",
        "max_daily_loss_pct",
        "min_risk_reward",
        "stop_atr_multiple",
        "target_atr_multiple",
        "max_stop_distance_pct",
    )
    @classmethod
    def _finite(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("must be a finite number")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        planned = self.target_atr_multiple / self.stop_atr_multiple
        if planned < self.min_risk_reward:
            raise ValueError(
                f"target/stop ATR multiples give a risk-to-reward of {planned:.2f}, "
                f"below RISK_MIN_RISK_REWARD ({self.min_risk_reward}): every trade would be vetoed"
            )
        if self.risk_per_trade_pct > self.max_daily_loss_pct:
            raise ValueError("RISK_RISK_PER_TRADE_PCT must not exceed RISK_MAX_DAILY_LOSS_PCT")
        return self


@lru_cache
def get_risk_limits() -> RiskLimits:
    return RiskLimits()
