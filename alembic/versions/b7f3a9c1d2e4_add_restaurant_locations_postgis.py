"""Add restaurant_locations table with PostGIS geography

Revision ID: b7f3a9c1d2e4
Revises: 3c42bcca272b
Create Date: 2026-06-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geography


# revision identifiers, used by Alembic.
revision: str = 'b7f3a9c1d2e4'
down_revision: Union[str, Sequence[str], None] = '3c42bcca272b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # PostGIS provides the geography type + spatial indexing used below.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        'restaurant_locations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('restaurant_id', sa.Uuid(), nullable=False),
        sa.Column('formatted_address', sa.Text(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        # spatial_index=False here: the GIST index is created explicitly below
        # so its name is stable and we avoid a duplicate-index emission.
        sa.Column('geog', Geography(geometry_type='POINT', srid=4326,
                                    spatial_index=False), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('provider_place_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('restaurant_id'),
    )
    op.create_index('ix_restaurant_locations_restaurant_id',
                    'restaurant_locations', ['restaurant_id'])
    # GIST index powers ST_DWithin "restaurants near me" proximity queries.
    op.create_index('idx_restaurant_locations_geog', 'restaurant_locations',
                    ['geog'], postgresql_using='gist')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_restaurant_locations_geog',
                  table_name='restaurant_locations')
    op.drop_index('ix_restaurant_locations_restaurant_id',
                  table_name='restaurant_locations')
    op.drop_table('restaurant_locations')
