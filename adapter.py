"""Platform lifecycle and durable, serial dispatch into the Hermes gateway."""
import asyncio
import contextlib
import logging

import aiohttp
from aiohttp import web
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, SendResult
from gateway.platforms.event import MessageEvent, ProcessingOutcome
from gateway.platforms._shared import extra_or_secret, get_scoped_secret, seed_extra_from_env

from .config import Settings
from .manychat import ManyChatClient
from .store import Inbox
from .webhook import create_app

logger = logging.getLogger(__name__)


class MessengerAdapter(BasePlatformAdapter):
    def __init__(self, config):
        super().__init__(config, Platform("messenger"))
        self.settings = Settings.from_platform(config)
        self.inbox = self.client = self._http = self._runner = self._worker_task = None
        self._wake = asyncio.Event()
        self._completion = {}
        self._stopping = False
        self._ready = False
        self.bound_port = None

    async def connect(self, *, is_reconnect=False):
        if self._ready:
            return True
        self._stopping = False
        try:
            self.inbox = Inbox(self.settings.database, self.settings.capacity, self.settings.retention_seconds)
            self.inbox.recover()
            self.inbox.prune()
            self._http = aiohttp.ClientSession()
            self.client = ManyChatClient(self._http, self.settings.token, timeout=self.settings.timeout)
            app = create_app(self.settings, self.inbox, self._wake.set, ready=lambda: self._ready)
            self._runner = web.AppRunner(app, access_log=None)
            await self._runner.setup()
            site = web.TCPSite(self._runner, self.settings.host, self.settings.port)
            await site.start()
            self.bound_port = self._runner.addresses[0][1]
            self._ready = True
            self._mark_connected()
            self._worker_task = asyncio.create_task(self._work(), name="messenger-inbox")
            self._wake.set()
            return True
        except Exception:
            logger.error("Messenger connection failed; verify configuration, database and listener port")
            await self.disconnect()
            return False

    async def disconnect(self):
        self._stopping = True
        self._ready = False
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None
        await self.cancel_background_tasks()
        self._completion.clear()
        if self._http is not None:
            await self._http.close()
            self._http = None
        self.client = None
        if self.inbox is not None:
            self.inbox.close()
            self.inbox = None
        self.bound_port = None
        self._mark_disconnected()

    async def _work(self):
        try:
            while not self._stopping:
                self._wake.clear()
                self.inbox.prune()
                # The gateway installs its handler before connecting, but never lose an
                # accepted event if that order changes or an adapter is manually tested.
                item = self.inbox.claim() if self._message_handler else None
                if item is None:
                    with contextlib.suppress(asyncio.TimeoutError):
                        await asyncio.wait_for(self._wake.wait(), timeout=1)
                    continue
                identifier, payload = item
                contact = payload["contact_id"]
                event = MessageEvent(
                    text=payload["message"], user_id=contact,
                    source=self.build_source(chat_id=contact, user_id=contact, chat_type="dm", message_id=identifier),
                    message_id=identifier, allow_gateway_control=False,
                    metadata={"messenger_inbox_id": identifier},
                )
                completed = asyncio.get_running_loop().create_future()
                self._completion[identifier] = completed
                try:
                    await self.handle_message(event)
                    if not event._gateway_accepted:
                        self.inbox.fail(identifier, "gateway_rejected")
                        continue
                    outcome = await asyncio.wait_for(asyncio.shield(completed), self.settings.processing_timeout)
                    if self._stopping:
                        break
                    if outcome == ProcessingOutcome.SUCCESS:
                        self.inbox.complete(identifier)
                    else:
                        self.inbox.fail(identifier, "processing_failed")
                finally:
                    self._completion.pop(identifier, None)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Keep the current processing row recoverable. Pause ingress and await
            # operator restart, rather than running subsequent turns over a stuck turn.
            self._ready = False
            self._set_fatal_error("messenger_worker_failed", "Messenger worker stopped; restart after checking runtime health", retryable=False)
            logger.error("Messenger worker stopped; accepted work remains in SQLite")

    async def on_processing_complete(self, event, outcome):
        future = self._completion.get(event.metadata.get("messenger_inbox_id"))
        if future is not None and not future.done():
            future.set_result(outcome)

    async def send(self, chat_id, content, reply_to=None, metadata=None):
        if self.client is None or self._stopping:
            return SendResult(success=False, error="messenger_disconnected", retryable=False)
        delivery = await self.client.send_text(str(chat_id), content)
        # ManyChat success does not provide a message ID or prove Messenger delivery.
        # Do not invent a remote ID or let gateway retries replay partial sends.
        return SendResult(success=delivery.success, error=delivery.error or None,
                          retryable=False, raw_response={"sent_chunks": delivery.sent_chunks, "uncertain": delivery.uncertain})

    async def get_chat_info(self, chat_id):
        return {"name": str(chat_id), "type": "dm"}

    def _send_retry_is_final(self, result):
        # Our client already sends plain text and owns safe retries. The base
        # fallback would replay partial or uncertain sends even with retryable=False.
        return True

    async def _record_delivery_obligation(self, event, session_key, text_content,
                                          delivery_adapter, is_ephemeral_response):
        # The generic Hermes outbox replays failed/uncertain full replies on boot,
        # including chunks ManyChat may already have accepted. This transport uses
        # its own durable inbox recovery instead; do not create a second retry owner.
        return None


def check_requirements():
    # Registry calls this before validate_config, including for YAML-only secrets.
    # aiohttp has already imported successfully; credential validation belongs below.
    return True


def validate_config(config):
    try:
        Settings.from_platform(config)
        return True
    except (ValueError, TypeError):
        return False


def _env_enablement():
    if not (get_scoped_secret("MANYCHAT_API_TOKEN", "").strip() and get_scoped_secret("MESSENGER_WEBHOOK_SECRET", "").strip()):
        return None
    return seed_extra_from_env((("MANYCHAT_API_TOKEN", "token", None), ("MESSENGER_WEBHOOK_SECRET", "webhook_secret", None)))


def register(ctx):
    ctx.register_platform(
        name="messenger", label="Facebook Messenger (ManyChat)",
        adapter_factory=MessengerAdapter, check_fn=check_requirements,
        validate_config=validate_config,
        required_env=["MANYCHAT_API_TOKEN", "MESSENGER_WEBHOOK_SECRET"],
        env_enablement_fn=_env_enablement,
        allowed_users_env="MESSENGER_ALLOWED_USERS",
        allow_all_env="MESSENGER_ALLOW_ALL_USERS",
        max_message_length=2000,
        platform_hint="You are answering a Facebook Messenger customer via ManyChat. Use plain text. Only text replies are supported.",
        emoji="💬",
    )
