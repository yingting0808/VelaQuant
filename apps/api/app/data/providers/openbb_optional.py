from datetime import UTC, datetime
from importlib.util import find_spec

from app.data.providers.base import EvidenceItem, ProviderStatus, Quote


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class OpenBBOptionalProvider:
    def __init__(self) -> None:
        self.available = find_spec("openbb") is not None

    def get_quote(self, ticker: str) -> Quote:
        normalized = ticker.strip().upper()
        raise ValueError(f"OpenBB quote adapter is not enabled for {normalized}")

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        return []

    def get_statuses(self) -> list[ProviderStatus]:
        if self.available:
            return [
                ProviderStatus(
                    name="OpenBB",
                    mode="openbb_optional",
                    available=True,
                    message="OpenBB package is installed; quote and historical adapters are reserved for the next provider task.",
                    checked_at=_utc_now(),
                    version="installed",
                )
            ]
        return [
            ProviderStatus(
                name="OpenBB",
                mode="openbb_optional",
                available=False,
                message="OpenBB package is not installed.",
                checked_at=_utc_now(),
                version=None,
            )
        ]
