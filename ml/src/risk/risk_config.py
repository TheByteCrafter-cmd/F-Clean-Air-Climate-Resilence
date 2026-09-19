"""
VayuDrishti — Risk Assessment Engine Configuration (Phase 1E-J2E.4.1)

Defines versioned weights, exact piecewise severity formulas, persistence thresholds,
uncertainty normalization parameters, spatial context modifiers, and risk level boundaries.
"""

from typing import Dict, List


class RiskConfig:
    """Versioned configuration for deterministic environmental risk assessment."""

    def __init__(
        self,
        config_version: str = "1.0",
        max_forecast_age_minutes: float = 120.0,
        elevated_pm25_threshold: float = 60.0,
        low_severity_capping_threshold: float = 15.0,
    ):
        self.config_version = config_version
        self.max_forecast_age_minutes = max_forecast_age_minutes
        self.elevated_pm25_threshold = elevated_pm25_threshold
        self.low_severity_capping_threshold = low_severity_capping_threshold

        # Component Maximum Weights (Sum = 100.0)
        self.weights = {
            "forecast_severity": 40.0,
            "forecast_persistence": 20.0,
            "uncertainty": 15.0,
            "hotspot_corroboration": 15.0,
            "context": 10.0,
        }

        # Spatial Context Modifiers (Sum = 10.0)
        self.context_modifiers = {
            "industrial_context": 3.5,
            "major_road_context": 3.0,
            "sensitive_receptor_context": 3.5,
        }

        # Risk Level Boundaries
        self.level_boundaries = [
            (0.0, 24.99, "LOW"),
            (25.0, 49.99, "MODERATE"),
            (50.0, 74.99, "HIGH"),
            (75.0, 100.0, "VERY_HIGH"),
        ]

    def compute_severity_score(self, p_eff: float) -> float:
        """
        Computes exact piecewise linear severity score from effective PM2.5 concentration p_eff:
        p_eff < 30:       10 * p_eff / 30
        30 <= p_eff < 60: 10 + 10 * (p_eff - 30) / 30
        60 <= p_eff < 120: 20 + 10 * (p_eff - 60) / 60
        p_eff >= 120:     40.0
        """
        p = max(0.0, float(p_eff))
        if p < 30.0:
            return round(10.0 * (p / 30.0), 2)
        elif p < 60.0:
            return round(10.0 + 10.0 * ((p - 30.0) / 30.0), 2)
        elif p < 120.0:
            return round(20.0 + 10.0 * ((p - 60.0) / 60.0), 2)
        else:
            return 40.0

    def map_score_to_level(self, score: float, severity_score: float) -> str:
        """
        Maps numerical score (0-100) to qualitative risk level.
        Enforces CORRECTION 3: If severity_score < 15.0 (low severity), max level is capped at MODERATE.
        """
        raw_level = "LOW"
        for low, high, level in self.level_boundaries:
            if low <= score <= high or (high == 100.0 and score >= 100.0):
                raw_level = level
                break

        # Uncertainty capping rule: low severity cannot be HIGH or VERY_HIGH
        if severity_score < self.low_severity_capping_threshold:
            if raw_level in ["HIGH", "VERY_HIGH"]:
                return "MODERATE"

        return raw_level
