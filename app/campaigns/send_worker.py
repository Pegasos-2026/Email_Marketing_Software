"""Background campaign send worker (avoids HTTP timeouts on large batches)."""
import logging
import threading

from django.db import close_old_connections

logger = logging.getLogger(__name__)

_active_sends: set[int] = set()
_lock = threading.Lock()


def is_campaign_send_active(campaign_id: int) -> bool:
    with _lock:
        return campaign_id in _active_sends


def start_campaign_send_async(campaign_id: int) -> bool:
    """Start sending in a daemon thread. Returns False if already running."""
    with _lock:
        if campaign_id in _active_sends:
            return False
        _active_sends.add(campaign_id)

    def run():
        close_old_connections()
        try:
            from app.campaigns.services import CampaignService

            CampaignService().send_campaign(campaign_id)
        except Exception:
            logger.exception('Background campaign send failed for campaign %s', campaign_id)
        finally:
            close_old_connections()
            with _lock:
                _active_sends.discard(campaign_id)

    threading.Thread(target=run, daemon=True, name=f'campaign-send-{campaign_id}').start()
    return True
