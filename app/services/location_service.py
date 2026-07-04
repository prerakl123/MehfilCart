"""
Location service -- manage a restaurant's geocoded location and proxy geocoding.

The `find_nearby` helper is the payoff of storing a PostGIS geography column
now: it is the building block for the upcoming "discover restaurants near me"
feature and runs as an index-backed ST_DWithin query.
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.restaurant import Restaurant
from app.models.restaurant_location import RestaurantLocation
from app.schemas.location import LocationUpsert
from app.services.geocoding import GeocodeResult, get_geocoder


# -- Geocoding proxy (keeps the provider key server-side) --

async def search_addresses(
    query: str, *, proximity: tuple[float, float] | None = None,
) -> list[GeocodeResult]:
    """Forward-geocode an address query via the configured provider."""
    return await get_geocoder().search(query, proximity=proximity)


async def reverse_geocode(
    latitude: float, longitude: float,
) -> GeocodeResult | None:
    """Reverse-geocode a coordinate via the configured provider."""
    return await get_geocoder().reverse(latitude, longitude)


# -- Restaurant location CRUD --

async def get_location(
    db: AsyncSession, restaurant_id: UUID,
) -> RestaurantLocation | None:
    """Fetch a restaurant's location, or None if not set."""
    result = await db.execute(
        select(RestaurantLocation)
        .where(RestaurantLocation.restaurant_id == restaurant_id)
    )
    return result.scalar_one_or_none()


async def upsert_location(
    db: AsyncSession, restaurant_id: UUID, data: LocationUpsert,
) -> RestaurantLocation:
    """
    Create or replace a restaurant's location.

    :raises NotFoundException: If the restaurant does not exist.
    """
    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id)
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundException("Restaurant not found.")

    location = await get_location(db, restaurant_id)
    if location is None:
        location = RestaurantLocation(restaurant_id=restaurant_id)
        db.add(location)

    location.formatted_address = data.formatted_address
    location.latitude = data.latitude
    location.longitude = data.longitude
    location.provider = data.provider
    location.provider_place_id = data.provider_place_id
    # Keep the indexed geography point in sync with the plain coordinates.
    location.geog = f"SRID=4326;POINT({data.longitude} {data.latitude})"

    await db.flush()
    return location


async def delete_location(db: AsyncSession, restaurant_id: UUID) -> None:
    """Remove a restaurant's location.

    :raises NotFoundException: If no location is set for the restaurant.
    """
    location = await get_location(db, restaurant_id)
    if location is None:
        raise NotFoundException("No location set for this restaurant.")
    await db.delete(location)
    await db.flush()


# -- Discovery (future "restaurants near me") --

async def find_nearby(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    *,
    radius_meters: float = 5000,
    limit: int = 50,
) -> list[tuple[Restaurant, float]]:
    """
    Find active restaurants within `radius_meters` of a point, nearest first.

    Index-backed by the GIST index on `restaurant_locations.geog`. Returns
    (Restaurant, distance_in_meters) tuples. Not yet exposed via an endpoint --
    this is the foundation for the upcoming discovery feature.
    """
    point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    distance = func.ST_Distance(RestaurantLocation.geog, point).label("distance_m")
    stmt = (
        select(Restaurant, distance)
        .join(RestaurantLocation,
              RestaurantLocation.restaurant_id == Restaurant.id)
        .where(
            func.ST_DWithin(RestaurantLocation.geog, point, radius_meters),
            Restaurant.is_active.is_(True),
        )
        .order_by(distance)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [(row[0], float(row[1])) for row in result.all()]
