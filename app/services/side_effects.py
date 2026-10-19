"""
Secondary Side-Effect Worker Service.
Executes non-critical background jobs (notifications, emails, webhooks) with retries.
Guarantees that side-effect failures never impact or fail the main submission transaction.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from app.config import settings

logger = logging.getLogger("side_effects")


class SafeSideEffectWorker:
    def __init__(self, max_retries: int = 2, base_delay: float = 0.5):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def _send_notification_attempt(
        self,
        submission_id: str,
        widget_id: str,
        recipient_email: str,
        payload: Dict[str, Any],
        force_fail: bool = False
    ) -> None:
        """Single notification attempt. Throws exception if simulated or failed."""
        if force_fail or settings.SIMULATE_SIDE_EFFECT_FAILURE:
            raise RuntimeError(f"Simulated notification failure for submission {submission_id}")

        # Simulated email notification (or webhook dispatch)
        logger.info(
            "[SIDE_EFFECT] Successfully dispatched lead notification to %s for widget %s (Submission ID: %s)",
            recipient_email, widget_id, submission_id
        )

    async def trigger_submission_notification(
        self,
        submission_id: str,
        widget_id: str,
        recipient_email: str,
        payload: Dict[str, Any],
        force_fail: bool = False
    ) -> None:
        """
        Background task entry point.
        Runs off the request path with retries and failure alerting.
        Never allows an exception to bubble up or crash the server.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                await self._send_notification_attempt(
                    submission_id=submission_id,
                    widget_id=widget_id,
                    recipient_email=recipient_email,
                    payload=payload,
                    force_fail=force_fail
                )
                return  # Success
            except Exception as exc:
                logger.warning(
                    "[SIDE_EFFECT_RETRY] Attempt %d/%d failed for submission %s: %s",
                    attempt, self.max_retries, submission_id, exc
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.base_delay * attempt)
                else:
                    # Final failure alert - alerts operations/sentry without breaking submission
                    logger.error(
                        "[SIDE_EFFECT_FAILURE_ALERT] All %d notification attempts failed for submission %s. "
                        "Lead is safely stored in database. Error: %s",
                        self.max_retries, submission_id, exc
                    )


side_effect_worker = SafeSideEffectWorker()
