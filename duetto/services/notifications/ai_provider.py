"""AI analysis provider for trading suggestions."""

import os
from typing import Optional

import aiohttp
from loguru import logger

from duetto.models import Alert, AlertType, AlertPriority


class AIProvider:
    """Base class for AI analysis providers."""

    async def analyze(self, alert: Alert) -> Optional[str]:
        """Analyze an alert and return trading suggestion."""
        pass


class OpenAIProvider(AIProvider):
    """AI analysis using OpenAI API (or compatible APIs)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url
        self.model = model
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def analyze(self, alert: Alert) -> Optional[str]:
        """Analyze alert and provide brief trading insight."""
        if not self.api_key:
            return None

        try:
            prompt = self._build_prompt(alert)
            session = await self._get_session()

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                "max_tokens": 300,
                "temperature": 0.3,
            }

            async with session.post(f"{self.base_url}/chat/completions", json=payload) as response:
                if response.status != 200:
                    logger.warning(f"AI API error: HTTP {response.status}")
                    return None

                data = await response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                return content.strip() if content else None

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None

    def _get_system_prompt(self) -> str:
        """Get system prompt for AI."""
        return """You are a trading analyst specializing in news-driven catalyst trading.

Analyze the given market alert and provide:
1. Brief assessment of the catalyst (bullish/bearish/neutral)
2. Expected price action (short-term)
3. Key risks to watch

Keep it under 150 words. Be concise but actionable. Use emojis for clarity.

⚠️ IMPORTANT: This is NOT financial advice. Always do your own research."""

    def _build_prompt(self, alert: Alert) -> str:
        """Build analysis prompt from alert."""
        catalyst_info = ""
        if alert.raw_data and "catalysts" in alert.raw_data:
            catalyst_info = f"\nCatalysts: {', '.join(alert.raw_data['catalysts'])}"

        ticker_display = alert.ticker or "Unknown"

        return f"""Analyze this market alert:

Type: {alert.type.value}
Priority: {alert.priority.value}
Ticker: {ticker_display}
Company: {alert.company}
{catalyst_info}

Title: {alert.title}
Summary: {alert.summary}

Provide a brief trading analysis."""


class AnthropicProvider(AIProvider):
    """AI analysis using Anthropic Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-haiku-20241022",
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def analyze(self, alert: Alert) -> Optional[str]:
        """Analyze alert and provide brief trading insight."""
        if not self.api_key:
            return None

        try:
            prompt = self._build_prompt(alert)
            session = await self._get_session()

            payload = {
                "model": self.model,
                "max_tokens": 300,
                "system": self._get_system_prompt(),
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            }

            async with session.post("https://api.anthropic.com/v1/messages", json=payload) as response:
                if response.status != 200:
                    logger.warning(f"AI API error: HTTP {response.status}")
                    return None

                data = await response.json()
                content = data.get("content", [{}])[0].get("text", "")

                return content.strip() if content else None

        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return None

    def _get_system_prompt(self) -> str:
        return """You are a trading analyst specializing in news-driven catalyst trading.

Analyze the given market alert and provide:
1. Brief assessment of the catalyst (bullish/bearish/neutral)
2. Expected price action (short-term)
3. Key risks to watch

Keep it under 150 words. Be concise but actionable. Use emojis for clarity.

⚠️ IMPORTANT: This is NOT financial advice. Always do your own research."""

    def _build_prompt(self, alert: Alert) -> str:
        catalyst_info = ""
        if alert.raw_data and "catalysts" in alert.raw_data:
            catalyst_info = f"\nCatalysts: {', '.join(alert.raw_data['catalysts'])}"

        ticker_display = alert.ticker or "Unknown"

        return f"""Analyze this market alert:

Type: {alert.type.value}
Priority: {alert.priority.value}
Ticker: {ticker_display}
Company: {alert.company}
{catalyst_info}

Title: {alert.title}
Summary: {alert.summary}

Provide a brief trading analysis."""


class RuleBasedProvider(AIProvider):
    """Simple rule-based analysis (no API required)."""

    async def analyze(self, alert: Alert) -> Optional[str]:
        """Generate rule-based trading suggestion."""
        catalysts = alert.raw_data.get("catalysts", []) if alert.raw_data else []

        # Bullish catalysts
        bullish = []
        bearish = []
        risk = []

        if "merger_acquisition" in catalysts:
            bullish.append("🟢 M&A typically causes significant upward movement on announcement")
            risk.append("Watch for deal break risk and regulatory approval")

        if "fda_catalyst" in catalysts:
            bullish.append("🟢 FDA approval often drives biotech rallies")
            risk.append("Clinical trial results can be unpredictable")

        if "insider_activity" in catalysts and alert.type == AlertType.SEC_FORM4:
            bullish.append("🟢 Insider buying can signal management confidence")
            risk.append("Insider sells are less informative")

        if "offering_dilution" in catalysts:
            bearish.append("🔴 Offerings dilute existing shareholders")
            risk.append("Price often drops on offering news")

        if "contract_partnership" in catalysts:
            bullish.append("🟢 Major contracts/partnerships can be revenue catalysts")
            risk.append("Verify contract materiality vs market cap")

        if "bankruptcy_restructuring" in catalysts:
            bearish.append("🔴 Bankruptcy risk - extreme caution needed")
            risk.append("Avoid unless experienced in distressed situations")

        # Build suggestion
        if not bullish and not bearish:
            return None

        parts = []
        if bullish:
            parts.append("Bullish Signals:\n" + "\n".join(f"  {b}" for b in bullish))
        if bearish:
            parts.append("Bearish Signals:\n" + "\n".join(f"  {b}" for b in bearish))
        if risk:
            parts.append("Risks:\n" + "\n".join(f"  ⚠️ {r}" for r in risk))

        parts.append("\n⚠️ This is not financial advice. Do your own research.")

        return "\n\n".join(parts)
