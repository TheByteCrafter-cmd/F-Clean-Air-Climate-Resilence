"""
VayuDrishti — Forecasting Pipeline Configuration

Defines configuration parameters for short-term air quality forecasting dataset preparation,
including target horizons (+1h, +3h, +6h), historical lag windows, rolling window sizes,
weather alignment tolerance, and data readiness thresholds.
"""

from typing import List, Optional


class ForecastingConfig:
    """Explicit, documented configuration for forecasting dataset preparation."""

    def __init__(
        self,
        config_version: str = "1.0-provisional",
        primary_pollutant: str = "PM2.5",
        secondary_pollutant: str = "PM10",
        target_horizons_hours: Optional[List[int]] = None,
        lag_hours: Optional[List[int]] = None,
        rolling_windows_hours: Optional[List[int]] = None,
        min_rolling_obs: int = 2,
        weather_tolerance_minutes: float = 60.0,
        min_stations_readiness: int = 3,
        min_timestamps_readiness: int = 48,  # Minimum 48 hours for training readiness
        min_usable_rows_readiness: int = 100,
    ):
        self.config_version = config_version
        self.primary_pollutant = primary_pollutant
        self.secondary_pollutant = secondary_pollutant
        self.target_horizons_hours = target_horizons_hours or [1, 3, 6]
        self.lag_hours = lag_hours or [1, 3, 6, 12, 24]
        self.rolling_windows_hours = rolling_windows_hours or [3, 6, 24]
        self.min_rolling_obs = min_rolling_obs
        self.weather_tolerance_minutes = weather_tolerance_minutes
        self.min_stations_readiness = min_stations_readiness
        self.min_timestamps_readiness = min_timestamps_readiness
        self.min_usable_rows_readiness = min_usable_rows_readiness
