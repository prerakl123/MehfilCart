"""Add session_events audit log table

Revision ID: f4a8c2e91b3d
Revises: b7f3a9c1d2e4
Create Date: 2026-07-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a8c2e91b3d'
down_revision: Union[str, Sequence[str], None] = 'b7f3a9c1d2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SESSION_EVENT_TYPES = (
    'SESSION_CREATED', 'SESSION_STATUS_CHANGED', 'SESSION_CLOSED',
    'MEMBER_JOIN_REQUESTED', 'MEMBER_APPROVED', 'MEMBER_REJECTED', 'MEMBER_LEFT',
    'ORDER_SUBMITTED', 'ORDER_STATUS_CHANGED', 'ORDER_CANCELLED',
    'SERVICE_ACTION_REQUESTED', 'SERVICE_ACTION_CLAIMED', 'SERVICE_ACTION_COMPLETED',
)


def upgrade() -> None:
    """Upgrade schema."""
    session_event_type = sa.Enum(*SESSION_EVENT_TYPES, name='session_event_type')
    session_event_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'session_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', session_event_type, nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_events_session_id', 'session_events', ['session_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_session_events_session_id', table_name='session_events')
    op.drop_table('session_events')
    sa.Enum(name='session_event_type').drop(op.get_bind(), checkfirst=True)
