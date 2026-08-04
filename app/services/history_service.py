"""History Service — retrieves past generated signals for the dashboard/history page."""

from typing import Optional, List
from app.firebase.firestore_repo import get_history, get_live_signal, get_all_live_signals
from app.utils.logger import get_logger

logger = get_logger("history_service")


class HistoryService:
    def get_signal_history(self, instrument: Optional[str] = None, limit: int = 50) -> List[dict]:
        return get_history(instrument=instrument, limit=limit)

    def get_current_signal(self, instrument: str) -> Optional[dict]:
        return get_live_signal(instrument)

    def get_all_current_signals(self) -> List[dict]:
        return get_all_live_signals()


history_service = HistoryService()
