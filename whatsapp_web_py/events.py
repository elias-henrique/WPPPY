class Events:
    QR = "qr"
    AUTHENTICATED = "authenticated"
    READY = "ready"
    MESSAGE = "message"
    MESSAGE_CREATED = "message_create"
    STATE_CHANGED = "change_state"
    DISCONNECTED = "disconnected"


ALL_EVENTS = {
    Events.QR,
    Events.AUTHENTICATED,
    Events.READY,
    Events.MESSAGE,
    Events.MESSAGE_CREATED,
    Events.STATE_CHANGED,
    Events.DISCONNECTED,
}
