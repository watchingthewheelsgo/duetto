"""Alert message templates for different output formats."""

from datetime import datetime
from typing import Optional

from duetto.models import Alert, AlertPriority, AlertType


class AlertTemplate:
    """Format alerts into various message templates."""

    @staticmethod
    def format_telegram(alert: Alert, with_ai_suggestion: bool = False, ai_suggestion: Optional[str] = None) -> str:
        """Format alert for Telegram message."""
        # Priority emoji
        priority_emoji = {
            AlertPriority.HIGH: "🔴",
            AlertPriority.MEDIUM: "🟡",
            AlertPriority.LOW: "🔵",
        }

        # Type emoji
        type_emoji = {
            AlertType.SEC_8K: "📄",
            AlertType.SEC_S3: "💰",
            AlertType.SEC_FORM4: "👤",
            AlertType.FDA_APPROVAL: "💊",
            AlertType.FDA_PDUFA: "📅",
            AlertType.FDA_TRIAL: "🔬",
            AlertType.PR_NEWS: "📰",
        }

        emoji = priority_emoji.get(alert.priority, "⚪")
        type_icon = type_emoji.get(alert.type, "📋")

        # Build message
        lines = [
            f"{emoji} *{alert.priority.upper()} Priority*",
            "",
            f"{type_icon} *{alert.title}*",
        ]

        # Add ticker if available
        if alert.ticker:
            lines.append(f"`{alert.ticker}` | {alert.company}")
        else:
            lines.append(f"{alert.company}")

        lines.append("")
        lines.append(f"📝 *Summary:*")
        lines.append(alert.summary)
        lines.append("")

        # Add catalysts if available
        if alert.raw_data and "catalysts" in alert.raw_data:
            catalysts = alert.raw_data["catalysts"]
            if catalysts:
                catalyst_labels = {
                    "merger_acquisition": "M&A",
                    "fda_catalyst": "FDA",
                    "offering_dilution": "Offering",
                    "contract_partnership": "Partnership",
                    "insider_activity": "Insider",
                    "bankruptcy_restructuring": "Bankruptcy",
                }
                tags = " ".join([f"#{catalyst_labels.get(c, c)}" for c in catalysts])
                lines.append(f"🏷 {tags}")
                lines.append("")

        # Add AI suggestion if available
        if with_ai_suggestion and ai_suggestion:
            lines.append(f"🤖 *AI Analysis:*")
            lines.append(ai_suggestion)
            lines.append("")

        # Add metadata
        lines.append(f"📅 {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"🔗 [View Source]({alert.url})")
        lines.append("")
        lines.append(f"_Source: {alert.source}_")

        return "\n".join(lines)

    @staticmethod
    def format_email(alert: Alert, with_ai_suggestion: bool = False, ai_suggestion: Optional[str] = None) -> str:
        """Format alert as HTML email."""
        priority_colors = {
            AlertPriority.HIGH: "#dc2626",  # Red
            AlertPriority.MEDIUM: "#f59e0b",  # Orange
            AlertPriority.LOW: "#3b82f6",  # Blue
        }

        color = priority_colors.get(alert.priority, "#6b7280")

        # Catalysts
        catalysts_html = ""
        if alert.raw_data and "catalysts" in alert.raw_data:
            catalyst_labels = {
                "merger_acquisition": "M&A",
                "fda_catalyst": "FDA",
                "offering_dilution": "Offering",
                "contract_partnership": "Partnership",
                "insider_activity": "Insider",
                "bankruptcy_restructuring": "Bankruptcy",
            }
            tags = [catalyst_labels.get(c, c) for c in alert.raw_data["catalysts"]]
            catalysts_html = f'<p style="color: #888; font-size: 12px;">Tags: {" | ".join(tags)}</p>'

        # AI suggestion
        ai_html = ""
        if with_ai_suggestion and ai_suggestion:
            ai_html = f"""
            <div style="background: #f0f9ff; border-left: 4px solid #0ea5e9; padding: 12px; margin: 16px 0;">
                <p style="margin: 0; font-weight: bold; color: #0284c7;">🤖 AI Analysis:</p>
                <p style="margin: 8px 0 0 0;">{ai_suggestion}</p>
            </div>
            """

        ticker_display = f"<strong>{alert.ticker}</strong>" if alert.ticker else "N/A"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ border-bottom: 3px solid {color}; padding-bottom: 16px; margin-bottom: 16px; }}
                .priority {{ display: inline-block; background: {color}; color: white; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
                .title {{ font-size: 20px; margin: 12px 0; }}
                .ticker {{ font-size: 24px; color: {color}; }}
                .summary {{ background: #f9fafb; padding: 16px; border-radius: 8px; margin: 16px 0; }}
                .footer {{ border-top: 1px solid #e5e7eb; padding-top: 16px; margin-top: 24px; font-size: 12px; color: #888; }}
                a {{ color: {color}; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <span class="priority">{alert.priority.upper()} PRIORITY</span>
                    <div class="title">{alert.title}</div>
                    <div class="ticker">{ticker_display} | {alert.company}</div>
                </div>

                <div class="summary">
                    <strong>Summary:</strong><br>
                    {alert.summary}
                </div>

                {catalysts_html}

                {ai_html}

                <div class="footer">
                    <p>Source: {alert.source}<br>
                    Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
                    <a href="{alert.url}">View Original Filing</a></p>
                </div>
            </div>
        </body>
        </html>
        """
        return html.strip()

    @staticmethod
    def format_markdown(alert: Alert, with_ai_suggestion: bool = False, ai_suggestion: Optional[str] = None) -> str:
        """Format alert as Markdown."""
        ticker_md = f"**{alert.ticker}**" if alert.ticker else "N/A"

        md = f"""# {alert.priority.upper()} Priority

## {alert.title}

**{ticker_md}** | {alert.company}

### Summary
{alert.summary}

"""

        if alert.raw_data and "catalysts" in alert.raw_data:
            catalysts = alert.raw_data["catalysts"]
            md += f"**Tags:** {' '.join([f'#{c}' for c in catalysts])}\n\n"

        if with_ai_suggestion and ai_suggestion:
            md += f"### 🤖 AI Analysis\n{ai_suggestion}\n\n"

        md += f"""---
*Source: {alert.source}* | *{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}* | [View Source]({alert.url})
"""
        return md

    @staticmethod
    def format_discord(alert: Alert, with_ai_suggestion: bool = False, ai_suggestion: Optional[str] = None) -> str:
        """Format alert for Discord webhook."""
        priority_colors = {
            AlertPriority.HIGH: 16711680,  # Red
            AlertPriority.MEDIUM: 15105570,  # Orange
            AlertPriority.LOW: 3447003,  # Blue
        }

        color = priority_colors.get(alert.priority, 10181038)  # Default gray

        # Build fields
        fields = [
            {"name": "Company", "value": alert.company, "inline": True},
        ]

        if alert.ticker:
            fields.append({"name": "Ticker", "value": alert.ticker, "inline": True})

        fields.append({"name": "Source", "value": alert.source, "inline": True})

        # Build embed
        embed = {
            "title": alert.title,
            "description": alert.summary[:4000],  # Discord limit
            "url": alert.url,
            "color": color,
            "fields": fields,
            "timestamp": alert.timestamp.isoformat(),
        }

        # Add catalysts
        if alert.raw_data and "catalysts" in alert.raw_data:
            catalysts = alert.raw_data["catalysts"]
            if catalysts:
                embed["footer"] = {"text": " | ".join(catalysts)}

        import json
        return json.dumps({"embeds": [embed]})

    @staticmethod
    def format_slack(alert: Alert, with_ai_suggestion: bool = False, ai_suggestion: Optional[str] = None) -> str:
        """Format alert for Slack webhook."""
        priority_emoji = {
            AlertPriority.HIGH: "🔴",
            AlertPriority.MEDIUM: "🟡",
            AlertPriority.LOW: "🔵",
        }

        emoji = priority_emoji.get(alert.priority, "⚪")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {alert.priority.upper()} Priority Alert",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{alert.title}*\n{alert.company}" + (f" | `{alert.ticker}`" if alert.ticker else ""),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary:*\n{alert.summary[:1000]}",
                },
            },
        ]

        # Add AI suggestion
        if with_ai_suggestion and ai_suggestion:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🤖 *AI Analysis:*\n{ai_suggestion}",
                },
            })

        # Add footer
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"{alert.source} | {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')} | <{alert.url}|View Source>",
                }
            ],
        })

        import json
        return json.dumps({"blocks": blocks})
