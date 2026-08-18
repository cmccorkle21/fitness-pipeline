from .config import PUSHOVER_API_TOKEN, PUSHOVER_USER_KEY

def notify_failure(message: str) -> None:
    """Best-effort alert; notification failure never breaks a sync."""
    if not (PUSHOVER_USER_KEY and PUSHOVER_API_TOKEN):
        return
    try:
        from pushover import Client
        Client(PUSHOVER_USER_KEY, api_token=PUSHOVER_API_TOKEN).send_message(message, title="Fitness sync failed")
    except Exception:
        pass
