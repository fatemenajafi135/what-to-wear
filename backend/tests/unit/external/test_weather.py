"""Unit tests for external/weather.py — never had one before this port."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from whattowear.external import weather


class TestTempToBand:
    @pytest.mark.parametrize(
        "temp_c,band",
        [
            (-5, "freezing"),
            (0, "cold"),
            (9.9, "cold"),
            (10, "cool"),
            (15.9, "cool"),
            (16, "mild"),
            (21.9, "mild"),
            (22, "warm"),
            (27.9, "warm"),
            (28, "hot"),
            (35, "hot"),
        ],
    )
    def test_boundaries(self, temp_c: float, band: str) -> None:
        assert weather.temp_to_band(temp_c) == band


class TestMonthToSeason:
    @pytest.mark.parametrize("month,season", [(1, "winter"), (4, "spring"), (7, "summer"), (10, "autumn")])
    def test_northern_hemisphere(self, month: int, season: str) -> None:
        assert weather.month_to_season(month) == season

    @pytest.mark.parametrize("month,season", [(1, "summer"), (4, "autumn"), (7, "winter"), (10, "spring")])
    def test_southern_hemisphere_is_flipped(self, month: int, season: str) -> None:
        assert weather.month_to_season(month, southern=True) == season


class TestGetWeather:
    def test_returns_temp_condition_band_and_season(self) -> None:
        geo_response = MagicMock()
        geo_response.json.return_value = {"results": [{"latitude": 51.5, "longitude": -0.1}]}
        forecast_response = MagicMock()
        forecast_response.json.return_value = {"current": {"temperature_2m": 5.0, "weather_code": 61}}

        with patch("whattowear.external.weather.requests.get", side_effect=[geo_response, forecast_response]):
            result = weather.get_weather("London")

        assert result["temp_c"] == 5.0
        assert result["condition"] == "rain"
        assert result["temp_band"] == "cold"
        assert result["season"] in ("winter", "spring", "summer", "autumn")

    def test_southern_hemisphere_latitude_flips_season(self) -> None:
        geo_response = MagicMock()
        geo_response.json.return_value = {"results": [{"latitude": -33.9, "longitude": 18.4}]}
        forecast_response = MagicMock()
        forecast_response.json.return_value = {"current": {"temperature_2m": 20.0, "weather_code": 0}}

        with (
            patch("whattowear.external.weather.requests.get", side_effect=[geo_response, forecast_response]),
            patch("whattowear.external.weather.datetime") as mock_dt,
        ):
            mock_dt.now.return_value.month = 1  # January -> northern winter, southern summer
            result = weather.get_weather("Cape Town")

        assert result["season"] == "summer"

    def test_unknown_location_raises(self) -> None:
        geo_response = MagicMock()
        geo_response.json.return_value = {"results": []}

        with patch("whattowear.external.weather.requests.get", return_value=geo_response):
            with pytest.raises(ValueError, match="could not geocode"):
                weather.get_weather("Nowhereville")

    def test_unknown_weather_code_maps_to_unknown_condition(self) -> None:
        geo_response = MagicMock()
        geo_response.json.return_value = {"results": [{"latitude": 0.0, "longitude": 0.0}]}
        forecast_response = MagicMock()
        forecast_response.json.return_value = {"current": {"temperature_2m": 20.0, "weather_code": 12345}}

        with patch("whattowear.external.weather.requests.get", side_effect=[geo_response, forecast_response]):
            result = weather.get_weather("Nullisland")

        assert result["condition"] == "unknown"
