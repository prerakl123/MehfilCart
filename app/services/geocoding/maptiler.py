"""
MapTiler geocoding provider.

Docs: https://docs.maptiler.com/cloud/api/geocoding/
Free tier: 100k requests/month, OSM-based data (portable to other OSM
providers such as Geoapify / LocationIQ / Photon if we ever switch).
"""

from urllib.parse import quote

import httpx

from app.core.exceptions import BadRequestException
from app.services.geocoding.base import GeocodeResult

_BASE_URL = "https://api.maptiler.com/geocoding"
_TIMEOUT = 10.0


class MapTilerProvider:
    """Forward + reverse geocoding backed by the MapTiler Cloud API."""

    name = "maptiler"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def _require_key(self) -> None:
        if not self._api_key:
            raise BadRequestException(
                "Geocoding is not configured: set MAPTILER_API_KEY.")

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        proximity: tuple[float, float] | None = None,
    ) -> list[GeocodeResult]:
        """Forward-geocode an address query into ranked suggestions."""
        self._require_key()
        if not query or not query.strip():
            return []

        params: dict[str, str] = {
            "key": self._api_key,
            "limit": str(limit),
            "autocomplete": "true",
        }
        if proximity is not None:
            lat, lng = proximity
            # MapTiler expects proximity as "lng,lat".
            params["proximity"] = f"{lng},{lat}"

        url = f"{_BASE_URL}/{quote(query.strip())}.json"
        data = await self._get(url, params)
        return [self._to_result(f) for f in data.get("features", [])]

    async def reverse(
        self, latitude: float, longitude: float,
    ) -> GeocodeResult | None:
        """Reverse-geocode a coordinate into the closest formatted address."""
        self._require_key()
        # MapTiler reverse geocoding takes "lng,lat" in the path.
        url = f"{_BASE_URL}/{longitude},{latitude}.json"
        data = await self._get(url, {"key": self._api_key, "limit": "1"})
        features = data.get("features", [])
        return self._to_result(features[0]) if features else None

    async def _get(self, url: str, params: dict[str, str]) -> dict:
        """Perform the HTTP GET and surface provider errors uniformly."""
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            raise BadRequestException(
                f"Geocoding provider error ({exc.response.status_code}).")
        except httpx.HTTPError:
            raise BadRequestException("Geocoding provider is unreachable.")

    def _to_result(self, feature: dict) -> GeocodeResult:
        """Normalize a MapTiler GeoJSON feature into a GeocodeResult."""
        # GeoJSON coordinates are [longitude, latitude].
        lng, lat = feature["geometry"]["coordinates"][:2]
        place_id = feature.get("id")
        return GeocodeResult(
            formatted_address=feature.get("place_name", ""),
            latitude=float(lat),
            longitude=float(lng),
            provider=self.name,
            place_id=str(place_id) if place_id is not None else None,
        )
