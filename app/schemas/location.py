"""Location schemas -- restaurant location upsert/response + geocoding results."""

from uuid import UUID

from pydantic import BaseModel, Field


class LocationUpsert(BaseModel):
    """Set or replace a restaurant's location (pin coordinates + typed address)."""
    formatted_address: str | None = Field(default=None, max_length=1000)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    provider: str | None = Field(default=None, max_length=50)
    provider_place_id: str | None = Field(default=None, max_length=255)


class RestaurantLocationResponse(BaseModel):
    """A restaurant's location in API responses, including a clickable map link."""
    id: UUID
    restaurant_id: UUID
    formatted_address: str | None
    latitude: float | None
    longitude: float | None
    provider: str | None
    # Provider-neutral Google Maps link built from the coordinates (model property).
    map_url: str | None

    model_config = {"from_attributes": True}


class GeocodeFeature(BaseModel):
    """A single normalized geocoding suggestion returned to the client."""
    formatted_address: str
    latitude: float
    longitude: float
    provider: str
    place_id: str | None = None


class GeocodeSearchResponse(BaseModel):
    """Ranked geocoding suggestions for an address query."""
    results: list[GeocodeFeature]
