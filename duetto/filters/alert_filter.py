"""Alert filtering and classification engine."""

import re
from typing import Optional

from duetto.models import Alert, AlertType, AlertPriority


# Catalyst keywords for classification
CATALYST_PATTERNS = {
    "merger_acquisition": [
        r"\bmerger\b", r"\bacquisition\b", r"\bacquire[sd]?\b",
        r"\bbuyout\b", r"\btender offer\b", r"\bdefinitive agreement\b",
        r"\bgoing private\b", r"\btakeover\b",
    ],
    "fda_catalyst": [
        r"\bfda\b", r"\bpdufa\b", r"\bapproval\b", r"\bclearance\b",
        r"\bphase [123]\b", r"\bclinical trial\b", r"\bnda\b", r"\bbla\b",
        r"\binda\b", r"\bbreakthrough therapy\b",
    ],
    "offering_dilution": [
        r"\boffering\b", r"\bplacement\b", r"\bdilution\b",
        r"\bshelf registration\b", r"\bs-3\b", r"\bsecurities act\b",
        r"\bprospectus\b", r"\bwarrant\b",
    ],
    "contract_partnership": [
        r"\bcontract\b", r"\bagreement\b", r"\bpartnership\b",
        r"\blicense\b", r"\bcollaboration\b", r"\balliance\b",
        r"\bdistribution\b", r"\bsupply agreement\b",
    ],
    "insider_activity": [
        r"\bform 4\b", r"\binsider\b", r"\bdirector\b", r"\bofficer\b",
        r"\bpurchase\b", r"\bacquisition of\b", r"\bopen market\b",
    ],
    "bankruptcy_restructuring": [
        r"\bbankruptcy\b", r"\bchapter 11\b", r"\bchapter 7\b",
        r"\brestructuring\b", r"\bdefault\b", r"\binsolvency\b",
    ],
}

# Noise patterns to filter out
NOISE_PATTERNS = [
    r"\broutine\b.*\bfiling\b",
    r"\bquarterly report\b",
    r"\bannual report\b",
    r"\b10-k\b",
    r"\b10-q\b",
    r"\bproxy statement\b",
]


class AlertFilter:
    """Filter and classify market alerts."""

    def __init__(
        self,
        min_priority: AlertPriority = AlertPriority.LOW,
        filter_noise: bool = True,
        catalyst_types: Optional[list[str]] = None,
    ):
        self.min_priority = min_priority
        self.filter_noise = filter_noise
        self.catalyst_types = catalyst_types  # None = all types

        # Compile patterns for performance
        self._catalyst_patterns = {
            cat: [re.compile(p, re.IGNORECASE) for p in patterns]
            for cat, patterns in CATALYST_PATTERNS.items()
        }
        self._noise_patterns = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]

    def should_pass(self, alert: Alert) -> bool:
        """Check if alert passes the filter."""
        # Priority filter
        priority_order = [AlertPriority.LOW, AlertPriority.MEDIUM, AlertPriority.HIGH]
        if priority_order.index(alert.priority) < priority_order.index(self.min_priority):
            return False

        # Noise filter
        if self.filter_noise and self._is_noise(alert):
            return False

        # Catalyst type filter
        if self.catalyst_types:
            catalysts = self.classify_catalysts(alert)
            if not any(cat in self.catalyst_types for cat in catalysts):
                return False

        return True

    def classify_catalysts(self, alert: Alert) -> list[str]:
        """Classify alert into catalyst categories."""
        text = f"{alert.title} {alert.summary}".lower()
        catalysts = []

        for category, patterns in self._catalyst_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    catalysts.append(category)
                    break

        return catalysts

    def enhance_alert(self, alert: Alert) -> Alert:
        """Enhance alert with additional classification."""
        catalysts = self.classify_catalysts(alert)

        # Upgrade priority for high-value catalysts
        if any(cat in ["merger_acquisition", "fda_catalyst", "bankruptcy_restructuring"] for cat in catalysts):
            alert.priority = AlertPriority.HIGH
        elif any(cat in ["contract_partnership", "insider_activity"] for cat in catalysts):
            if alert.priority == AlertPriority.LOW:
                alert.priority = AlertPriority.MEDIUM

        # Add catalyst info to raw_data
        if alert.raw_data is None:
            alert.raw_data = {}
        alert.raw_data["catalysts"] = catalysts

        return alert

    def _is_noise(self, alert: Alert) -> bool:
        """Check if alert is routine noise."""
        text = f"{alert.title} {alert.summary}"

        for pattern in self._noise_patterns:
            if pattern.search(text):
                return True

        return False
