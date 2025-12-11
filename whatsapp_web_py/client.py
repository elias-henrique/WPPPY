from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from playwright.async_api import BrowserContext, Page, async_playwright
from pyee.asyncio import AsyncIOEventEmitter

from .auth import AuthStrategy, LocalAuth
from .events import Events
from .js_loader import load_scripts, wrap_commonjs
from .structures import Chat, Contact, Message, MessageMedia

WhatsWebURL = "https://web.whatsapp.com/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ClientOptions:
    auth_strategy: AuthStrategy = field(default_factory=LocalAuth)
    headless: bool = True
    user_agent: str = DEFAULT_USER_AGENT
    browser_args: Optional[List[str]] = None
    qr_max_retries: int = 0
    bypass_csp: bool = True
    proxy: Optional[Dict[str, Any]] = None


class Client(AsyncIOEventEmitter):
    """
    Reescrita em Python do Client principal do whatsapp-web.js.
    Usa Playwright para controlar o WhatsApp Web e injeta os utilitários JS
    originais para manter compatibilidade de comportamento.
    """

    def __init__(self, options: Optional[ClientOptions] = None) -> None:
        super().__init__()
        self.options = options or ClientOptions()
        self.logger = logging.getLogger("wwebjs-py")
        self._scripts = load_scripts()

        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._store_ready = False
        self._synced_emitted = False
        self._qr_retries = 0

    async def initialize(self) -> None:
        """Inicia o navegador, navega para o WhatsApp Web e realiza a injeção."""
        self.playwright = await async_playwright().start()
        args = list(self.options.browser_args or [])
        if not any("disable-blink-features=AutomationControlled" in a for a in args):
            args.append("--disable-blink-features=AutomationControlled")

        self.context = await self.options.auth_strategy.create_context(
            playwright=self.playwright,
            headless=self.options.headless,
            user_agent=self.options.user_agent,
            args=args,
            proxy=self.options.proxy,
            bypass_csp=self.options.bypass_csp,
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

        await self.page.add_init_script(self._scripts["moduleraid"])
        # Pequena proteção para evitar bloqueios de automação
        await self.page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        await self.page.goto(WhatsWebURL, wait_until="domcontentloaded")
        await self._inject()

    async def destroy(self) -> None:
        try:
            if self.context:
                await self.context.close()
                self.context = None
        except Exception:
            pass  # Ignora erros ao fechar contexto

        try:
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception:
            pass  # Ignora erros ao parar playwright

        try:
            await self.options.auth_strategy.destroy()
        except Exception:
            pass  # Ignora erros ao destruir auth strategy

    # ------------------------------------------------------------------ #
    # Injeção e listeners
    # ------------------------------------------------------------------ #
    async def _inject(self) -> None:
        if not self.page:
            raise RuntimeError("Página não inicializada.")

        # Aguarda o WhatsApp Web carregar verificando a presença do elemento principal
        await self.page.wait_for_selector("#app .landing-wrapper, #app canvas, #side", timeout=60000, state="attached")
        await self.page.expose_function("_py_on_qr", self._handle_qr)
        await self.page.expose_function("_py_on_state", self._handle_state_change)
        await self.page.expose_function("_py_on_synced", self._handle_synced)
        await self.page.expose_function("_py_on_logout", self._handle_logout)

        # Injeção mínima para acessar AuthStore e acompanhar estado.
        await self.page.evaluate(wrap_commonjs(self._scripts["auth_store"], "ExposeAuthStore"))

        await self.page.evaluate(
            """
            (async () => {
                const getQR = async (ref) => {
                    if (!ref) return null;
                    const registrationInfo = await window.AuthStore.RegistrationUtils.waSignalStore.getRegistrationInfo();
                    const noiseKeyPair = await window.AuthStore.RegistrationUtils.waNoiseInfo.get();
                    const staticKeyB64 = window.AuthStore.Base64Tools.encodeB64(noiseKeyPair.staticKeyPair.pubKey);
                    const identityKeyB64 = window.AuthStore.Base64Tools.encodeB64(registrationInfo.identityKeyPair.pubKey);
                    const advSecretKey = await window.AuthStore.RegistrationUtils.getADVSecretKey();
                    const platform = window.AuthStore.RegistrationUtils.DEVICE_PLATFORM;
                    return ref + ',' + staticKeyB64 + ',' + identityKeyB64 + ',' + advSecretKey + ',' + platform;
                };

                const emitQR = async (ref) => {
                    const qr = await getQR(ref);
                    if (qr) await window._py_on_qr(qr);
                };

                const state = window.AuthStore.AppState.state;
                if (state === 'UNPAIRED' || state === 'UNPAIRED_IDLE' || state === 'OPENING' || state === 'UNLAUNCHED' || state === 'PAIRING') {
                    await emitQR(window.AuthStore.Conn.ref);
                    window.AuthStore.Conn.on('change:ref', (_c, ref) => emitQR(ref));
                }

                window.AuthStore.AppState.on('change:state', (_a, s) => window._py_on_state(s));
                window.AuthStore.AppState.on('change:hasSynced', () => window._py_on_synced(true));
                window.AuthStore.Cmd.on('logout', async () => { await window._py_on_logout('LOGOUT'); });
            })();
            """
        )

        current_state = await self.page.evaluate("() => window.AuthStore.AppState.state")
        if current_state and current_state not in (
            "UNPAIRED",
            "UNPAIRED_IDLE",
            "OPENING",
            "UNLAUNCHED",
            "PAIRING",
        ):
            await self._handle_synced(True)

    async def _bootstrap_store(self) -> None:
        if self._store_ready:
            return
        await self.page.evaluate(wrap_commonjs(self._scripts["store"], "ExposeStore"))
        await self.page.evaluate(wrap_commonjs(self._scripts["utils"], "LoadUtils"))

        await self.page.expose_function("_py_on_message", self._handle_message)
        await self.page.expose_function("_py_on_message_created", self._handle_message_created)

        await self.page.evaluate(
            """
            (() => {
                window.Store.Msg.on('add', (msg) => {
                    if (!msg.isNewMsg) return;
                    const model = window.WWebJS.getMessageModel(msg);
                    window._py_on_message_created(model);
                    if (!model.id?.fromMe) window._py_on_message(model);
                });
            })();
            """
        )

        self._store_ready = True

    # ------------------------------------------------------------------ #
    # Event handlers chamados pelo contexto JS
    # ------------------------------------------------------------------ #
    async def _handle_qr(self, qr: str) -> None:
        if self.options.qr_max_retries and self._qr_retries >= self.options.qr_max_retries:
            self.logger.warning("Limite de QR codes atingido.")
            await self._emit(Events.DISCONNECTED, "qr_max_retries")
            return
        self._qr_retries += 1
        await self._emit(Events.QR, qr)

    async def _handle_state_change(self, state: str) -> None:
        await self._emit(Events.STATE_CHANGED, state)

    async def _handle_synced(self, _synced: bool) -> None:
        if self._synced_emitted:
            return
        self._synced_emitted = True
        await self._bootstrap_store()
        await self._emit(Events.AUTHENTICATED)
        await self._emit(Events.READY)

    async def _handle_logout(self, reason: str) -> None:
        await self._emit(Events.DISCONNECTED, reason)

    async def _handle_message(self, payload: Dict[str, Any]) -> None:
        await self._emit(Events.MESSAGE, Message.from_js(payload))

    async def _handle_message_created(self, payload: Dict[str, Any]) -> None:
        await self._emit(Events.MESSAGE_CREATED, Message.from_js(payload))

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    async def send_message(
        self,
        chat_id: str,
        content: Union[str, MessageMedia],
        *,
        options: Optional[Dict[str, Any]] = None,
    ) -> Optional[Message]:
        if not self.page:
            raise RuntimeError("Cliente não inicializado. Chame initialize().")
        await self._bootstrap_store()

        opts = options.copy() if options else {}
        payload = content
        if isinstance(content, MessageMedia):
            opts["media"] = content.to_json()
            payload = ""

        msg = await self.page.evaluate(
            "(chatId, body, opts) => window.WWebJS.sendMessage(chatId, body, opts)",
            chat_id,
            payload,
            opts,
        )
        return Message.from_js(msg) if msg else None

    async def get_chats(self) -> List[Chat]:
        await self._bootstrap_store()
        chats = await self.page.evaluate("() => window.WWebJS.getChats()")
        return [Chat.from_js(c) for c in chats]

    async def get_contacts(self) -> List[Contact]:
        await self._bootstrap_store()
        contacts = await self.page.evaluate("() => window.WWebJS.getContacts()")
        return [Contact.from_js(c) for c in contacts]

    async def get_chat_by_id(self, chat_id: str) -> Optional[Chat]:
        await self._bootstrap_store()
        chat = await self.page.evaluate("(cid) => window.WWebJS.getChat(cid)", chat_id)
        return Chat.from_js(chat) if chat else None

    async def get_message_by_id(self, message_id: str) -> Optional[Message]:
        await self._bootstrap_store()
        msg = await self.page.evaluate(
            "(mid) => { const m = window.Store.Msg.get(mid); return m ? window.WWebJS.getMessageModel(m) : null; }",
            message_id,
        )
        return Message.from_js(msg) if msg else None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _emit(self, event: str, *args: Any) -> None:
        try:
            result = self.emit(event, *args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:  # pragma: no cover - log defensivo
            self.logger.exception("Erro ao emitir evento %s: %s", event, exc)
