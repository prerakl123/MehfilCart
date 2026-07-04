"""
Geocoding package -- pick the configured provider behind a stable interface.

Call sites use `get_geocoder()` and never import a concrete provider, so
switching providers (e.g. to a paid tier or a different OSM vendor) is a
one-line config change plus a new provider class.
"""

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.services.geocoding.base import GeocodeResult, GeocodingProvider
from app.services.geocoding.maptiler import MapTilerProvider

__all__ = ["GeocodeResult", "GeocodingProvider", "get_geocoder"]

# Registry of available providers, keyed by their config name.
_PROVIDERS = {
    "maptiler": lambda: MapTilerProvider(settings.MAPTILER_API_KEY),
}


def get_geocoder() -> GeocodingProvider:
    """Return the geocoding provider selected by settings.GEOCODING_PROVIDER."""
    key = (settings.GEOCODING_PROVIDER or "maptiler").lower()
    factory = _PROVIDERS.get(key)
    if factory is None:
        raise BadRequestException(
            f"Unsupported geocoding provider: '{key}'. "
            f"Available: {', '.join(sorted(_PROVIDERS))}.")
    return factory()
