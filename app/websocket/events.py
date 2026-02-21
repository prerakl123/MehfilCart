"""WebSocket event type constants for real-time communication."""


class WSEvent:
    """Event names for server-to-client and client-to-server WebSocket messages."""

    # Cart events
    CART_ITEM_ADDED = "cart:item-added"
    CART_ITEM_REMOVED = "cart:item-removed"
    CART_ITEM_UPDATED = "cart:item-updated"

    # Session events
    SESSION_MEMBER_JOINED = "session:member-joined"
    SESSION_MEMBER_LEFT = "session:member-left"
    SESSION_JOIN_REQUEST = "session:join-request"
    SESSION_STATUS_CHANGED = "session:status-changed"
    SESSION_ADDITIONS_TOGGLED = "session:additions-toggled"
    SESSION_TIMEOUT_WARNING = "session:timeout-warning"

    # Order events
    ORDER_STATUS_UPDATED = "order:status-updated"
    ORDER_CANCELLED = "order:cancelled"
    ORDER_SUBMITTED = "order:submitted"
