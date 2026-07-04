"""
RestaurantLocation model -- geocoded address + map coordinates for a restaurant.

Stored in a dedicated table (rather than columns on `restaurants`) so that:
  * the PostGIS `geog` column can carry its own GIST index for fast
    "restaurants near me" proximity queries (ST_DWithin), and
  * a restaurant can grow to multiple branches/locations later by dropping the
    one-to-one uniqueness constraint -- no data migration of the parent table.

We keep BOTH plain `latitude`/`longitude` floats AND the PostGIS `geog` column:
the floats are vendor-neutral, always readable, and used to build the public
map link; `geog` is the indexed column that powers spatial queries.
"""

import uuid

from geoalchemy2 import Geography
from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class RestaurantLocation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A restaurant's physical location: typed address + map coordinates."""
    __tablename__ = "restaurant_locations"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # The full address the admin types out manually.
    formatted_address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Plain coordinates -- portable, used to build the public map link.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # PostGIS geography point (WGS84 / SRID 4326). Indexed via GIST for
    # ST_DWithin proximity searches. `spatial_index=True` lets metadata
    # create_all() build the GIST index automatically; the Alembic migration
    # creates the same index explicitly for migration-based deploys.
    geog = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
    )

    # Provenance of the geocode (which provider, and its opaque id) so we can
    # re-resolve or debug later without coupling to any one vendor.
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_place_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True)

    # Relationships
    restaurant = relationship("Restaurant", back_populates="location")

    @property
    def map_url(self) -> str | None:
        """
        Build a provider-neutral, clickable map link from the coordinates.

        Uses Google Maps' universal URL scheme, which opens the native maps app
        on mobile and Google/Apple Maps on desktop -- no API key required.
        """
        if self.latitude is None or self.longitude is None:
            return None
        return (
            "https://www.google.com/maps/search/?api=1"
            f"&query={self.latitude},{self.longitude}"
        )

    def __repr__(self):
        """Return a human-readable representation of the RestaurantLocation."""
        return f"<RestaurantLocation restaurant={self.restaurant_id}>"
