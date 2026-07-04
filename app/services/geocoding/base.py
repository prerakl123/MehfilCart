"""
Geocoding abstraction -- the provider-neutral boundary.

Every geocoding provider returns the same `GeocodeResult` shape, so swapping
providers (free -> paid, or vendor A -> B) only means adding a new class and
flipping `settings.GEOCODING_PROVIDER` -- no call site changes.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class GeocodeResult:
    """A single normalized geocoding hit, independent of the provider."""
    formatted_address: str
    latitude: float
    longitude: float
    provider: str
    place_id: str | None = None


@runtime_checkable
class GeocodingProvider(Protocol):
    """
    Contract every geocoding provider implements.

    `name` is recorded on saved locations so we know which provider resolved
    them. Coordinates are always WGS84 (lat/lng in degrees).
    """

    name: str

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        proximity: tuple[float, float] | None = None,
    ) -> list[GeocodeResult]:
        """
        Forward-geocode / autocomplete a free-text address query.

        :param query: Partial or full address text.
        :param limit: Max number of suggestions to return.
        :param proximity: Optional (latitude, longitude) to bias results toward.
        :returns: Ranked list of GeocodeResult (best match first).
        """
        ...

    async def reverse(
        self, latitude: float, longitude: float,
    ) -> GeocodeResult | None:
        """
        Reverse-geocode a coordinate into a formatted address.

        :returns: The best GeocodeResult, or None if nothing was found.
        """
        ...
