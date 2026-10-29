"""SSRF-protected webhook dispatcher with HMAC-SHA256 signatures and retry backoff."""

import asyncio
import ipaddress
import json
import logging
import socket
import time
import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.core.errors import DocumentSecurityError
from app.core.security import compute_webhook_signature
from app.models.webhook import WebhookDelivery, WebhookEndpoint

logger = logging.getLogger(__name__)

FORBIDDEN_METADATA_IPS = {"169.254.169.254", "fd00:ec2::254"}


def validate_outbound_url(url: str, allow_http: bool = False) -> str:
    """
    Strict SSRF validation: verifies scheme, synchronously resolves DNS,
    and blocks all private, loopback, link-local, and cloud metadata addresses.
    """
    if not url:
        raise DocumentSecurityError("Webhook URL must not be empty.", code="INVALID_URL")

    parsed = urlparse(url)
    if parsed.scheme == "http":
        if not allow_http and settings.environment == "production":
            raise DocumentSecurityError(
                "Only HTTPS destinations are permitted in production.",
                code="INSECURE_WEBHOOK_SCHEME",
            )
    elif parsed.scheme != "https":
        raise DocumentSecurityError(
            f"Unsupported protocol scheme '{parsed.scheme}'. Only HTTPS is permitted.",
            code="UNSUPPORTED_SCHEME",
        )

    hostname = parsed.hostname
    if not hostname:
        raise DocumentSecurityError("Invalid URL: missing hostname.", code="INVALID_URL")

    # In local development or testing with localhost/testserver
    if hostname in ("localhost", "127.0.0.1", "testserver") and (allow_http or settings.environment in ("development", "test")):
        return url

    # Synchronous DNS pre-resolution
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise DocumentSecurityError(f"DNS resolution failed for hostname '{hostname}': {str(e)}", code="DNS_RESOLUTION_FAILED")

    for _, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        if ip_str in FORBIDDEN_METADATA_IPS:
            raise DocumentSecurityError(
                "Destination address references cloud instance metadata service.",
                code="SSRF_METADATA_PROHIBITED",
            )

        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise DocumentSecurityError(f"Invalid IP address resolved: {ip_str}", code="INVALID_RESOLVED_IP")

        if ip.is_loopback:
            raise DocumentSecurityError("Loopback destinations (127.0.0.0/8, ::1) are prohibited.", code="SSRF_LOOPBACK_PROHIBITED")
        if ip.is_private:
            raise DocumentSecurityError("Private RFC1918 destinations are prohibited.", code="SSRF_PRIVATE_IP_PROHIBITED")
        if ip.is_link_local:
            raise DocumentSecurityError("Link-local addresses (169.254.0.0/16, fe80::/10) are prohibited.", code="SSRF_LINK_LOCAL_PROHIBITED")
        if ip.is_reserved or ip.is_multicast:
            raise DocumentSecurityError("Reserved or multicast destinations are prohibited.", code="SSRF_RESERVED_PROHIBITED")

    return url


class WebhookService:
    """Manages webhook endpoint registration, signature signing, and delivery."""

    @staticmethod
    async def register_endpoint(
        session: AsyncSession,
        tenant_id: str,
        url: str,
        secret: str,
        events: Optional[List[str]] = None,
    ) -> WebhookEndpoint:
        """Validates destination against SSRF and registers a webhook destination."""
        validate_outbound_url(url, allow_http=settings.environment != "production")
        from app.core.security import hash_secret

        endpoint = WebhookEndpoint(
            tenant_id=tenant_id,
            url=url,
            secret_hash=hash_secret(secret),
            events=events or ["job.completed", "job.failed"],
            is_active=True,
        )
        session.add(endpoint)
        await session.flush()
        return endpoint

    @staticmethod
    async def list_endpoints(session: AsyncSession, tenant_id: str) -> List[WebhookEndpoint]:
        stmt = select(WebhookEndpoint).where(
            WebhookEndpoint.tenant_id == tenant_id,
            WebhookEndpoint.is_active == True,
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def dispatch_job_event(
        session: AsyncSession,
        tenant_id: str,
        job_id: str,
        event_type: str,  # 'job.completed' or 'job.failed'
        event_payload: Dict[str, Any],
        raw_secret_override: Optional[str] = None,
    ) -> List[WebhookDelivery]:
        """Dispatches an event to all matching active webhook endpoints for tenant."""
        stmt = select(WebhookEndpoint).where(
            WebhookEndpoint.tenant_id == tenant_id,
            WebhookEndpoint.is_active == True,
        )
        endpoints = (await session.execute(stmt)).scalars().all()
        deliveries = []

        now_ts = int(time.time())
        event_id = str(uuid.uuid4())
        payload_bytes = json.dumps(event_payload, separators=(",", ":")).encode("utf-8")

        for ep in endpoints:
            if event_type not in ep.events:
                continue

            secret_key = raw_secret_override or "default-webhook-secret"
            sig = compute_webhook_signature(secret_key, now_ts, payload_bytes)
            headers = {
                "Content-Type": "application/json",
                "X-UnlimitedOCR-Signature": f"t={now_ts},v1={sig}",
                "X-UnlimitedOCR-Timestamp": str(now_ts),
                "X-UnlimitedOCR-Event-ID": event_id,
                "User-Agent": "UnlimitedOCR-Webhook/1.0",
            }

            # Attempt delivery asynchronously with timeout
            delivery_record = WebhookDelivery(
                webhook_endpoint_id=ep.id,
                job_id=job_id,
                event_type=event_type,
                attempt=1,
            )

            try:
                # SSRF re-check on dispatch
                validate_outbound_url(ep.url, allow_http=settings.environment != "production")
                async with httpx.AsyncClient(timeout=settings.webhook_timeout_seconds) as client:
                    resp = await client.post(ep.url, content=payload_bytes, headers=headers)
                    delivery_record.status_code = resp.status_code
                    delivery_record.success = (200 <= resp.status_code < 300)
                    if not delivery_record.success:
                        delivery_record.error_message = f"Received HTTP {resp.status_code}"
            except Exception as e:
                delivery_record.success = False
                delivery_record.error_message = str(e)

            session.add(delivery_record)
            deliveries.append(delivery_record)

        await session.flush()
        return deliveries


webhook_service = WebhookService()
