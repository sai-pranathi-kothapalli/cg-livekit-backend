import httpx
import hashlib
import hmac
import json
import asyncio
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

WEBHOOK_RETRY_COUNT = int(os.getenv("WEBHOOK_RETRY_COUNT", "3"))
WEBHOOK_TIMEOUT = float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "15"))


class WebhookService:
    """
    Fires webhook notifications to registered endpoints.
    Used to notify LMS when evaluations complete.
    """

    def __init__(self, supabase_client):
        self.client = supabase_client

    def _sign_payload(self, payload: dict, secret: str) -> str:
        """Create HMAC-SHA256 signature for webhook payload verification."""
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    async def fire_webhook(self, event: str, payload: dict, batch: str = None):
        """
        Send webhook notifications for an event.
        
        Finds all active webhooks registered for this event,
        sends the payload to each, retries on failure.
        
        Args:
            event: "EVALUATION_COMPLETED"
            payload: { booking_token, student_id, batch, scores, ... }
            batch: optional batch filter (only notify webhooks for this batch)
        """
        # Find active webhooks for this event
        try:
            query = self.client.table('webhooks_registry').select('*').eq(
                'active', True
            ).contains('events', [event])

            # If batch filter is set on the webhook, match it
            # Webhooks with no batch_filter receive ALL events
            result = query.execute()

            if not result.data:
                logger.info(f"No active webhooks registered for event: {event}")
                return

            webhooks = result.data

        except Exception as e:
            logger.error(f"Failed to fetch webhooks: {str(e)}")
            return

        # Filter by batch if applicable
        matching_webhooks = []
        for wh in webhooks:
            wh_batch_filter = wh.get('batch_filter')
            if wh_batch_filter and batch and wh_batch_filter != batch:
                continue  # This webhook is for a different batch
            matching_webhooks.append(wh)

        if not matching_webhooks:
            logger.info(f"No matching webhooks for event={event}, batch={batch}")
            return

        # Send to all matching webhooks
        for webhook in matching_webhooks:
            await self._deliver_webhook(webhook, event, payload)

    async def _deliver_webhook(self, webhook: dict, event: str, payload: dict):
        """
        Deliver a webhook with retry logic.
        Logs every attempt to webhook_delivery_log.
        """
        target_url = webhook.get('target_url')
        secret = webhook.get('secret')
        webhook_id = webhook.get('id')

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event,
            "X-Webhook-Timestamp": datetime.utcnow().isoformat(),
        }

        # Add HMAC signature if secret is configured
        if secret:
            signature = self._sign_payload(payload, secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Add API key if configured by LMS
        if secret:
            headers["X-API-Key"] = secret

        # Retry loop with exponential backoff
        for attempt in range(1, WEBHOOK_RETRY_COUNT + 1):
            try:
                async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT) as client:
                    response = await client.post(
                        target_url,
                        json=payload,
                        headers=headers,
                    )

                success = 200 <= response.status_code < 300

                # Log the delivery attempt
                self._log_delivery(
                    webhook_id=webhook_id,
                    event=event,
                    payload=payload,
                    response_status=response.status_code,
                    response_body=response.text[:1000],
                    success=success,
                    attempt=attempt,
                )

                if success:
                    logger.info(
                        f"Webhook delivered: {event} → {target_url} "
                        f"(status={response.status_code}, attempt={attempt})"
                    )
                    # Update last_triggered_at
                    try:
                        self.client.table('webhooks_registry').update({
                            'last_triggered_at': datetime.utcnow().isoformat(),
                            'failure_count': 0,
                        }).eq('id', webhook_id).execute()
                    except Exception:
                        pass
                    return  # Success — done

                # Non-2xx response — retry
                logger.warning(
                    f"Webhook failed: {event} → {target_url} "
                    f"(status={response.status_code}, attempt={attempt}/{WEBHOOK_RETRY_COUNT})"
                )

            except httpx.TimeoutException:
                logger.warning(
                    f"Webhook timeout: {event} → {target_url} "
                    f"(attempt={attempt}/{WEBHOOK_RETRY_COUNT})"
                )
                self._log_delivery(
                    webhook_id=webhook_id,
                    event=event,
                    payload=payload,
                    response_status=0,
                    response_body="TIMEOUT",
                    success=False,
                    attempt=attempt,
                )

            except Exception as e:
                logger.error(
                    f"Webhook error: {event} → {target_url} "
                    f"(attempt={attempt}/{WEBHOOK_RETRY_COUNT}): {str(e)}"
                )
                self._log_delivery(
                    webhook_id=webhook_id,
                    event=event,
                    payload=payload,
                    response_status=0,
                    response_body=str(e)[:1000],
                    success=False,
                    attempt=attempt,
                )

            # Wait before retrying (exponential backoff: 2s, 4s, 8s)
            if attempt < WEBHOOK_RETRY_COUNT:
                delay = 2 ** attempt
                logger.info(f"Retrying webhook in {delay}s...")
                await asyncio.sleep(delay)

        # All retries failed
        logger.error(
            f"Webhook PERMANENTLY FAILED after {WEBHOOK_RETRY_COUNT} attempts: "
            f"{event} → {target_url}"
        )
        # Increment failure count
        try:
            self.client.table('webhooks_registry').update({
                'failure_count': webhook.get('failure_count', 0) + 1,
            }).eq('id', webhook_id).execute()
        except Exception:
            pass

    def _log_delivery(self, webhook_id, event, payload, response_status, response_body, success, attempt):
        """Log webhook delivery attempt for debugging."""
        try:
            self.client.table('webhook_delivery_log').insert({
                'webhook_id': webhook_id,
                'event': event,
                'payload': payload,
                'response_status': response_status,
                'response_body': response_body[:1000] if response_body else None,
                'success': success,
                'attempt_number': attempt,
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log webhook delivery: {str(e)}")
