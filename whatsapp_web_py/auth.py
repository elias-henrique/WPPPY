from __future__ import annotations

import logging
import pickle
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from playwright.async_api import BrowserContext, Playwright

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def _dedupe_args(args: Optional[Iterable[str]]) -> List[str]:
    """Remove duplicatas preservando a ordem para evitar erros do Chromium."""

    deduped: List[str] = []
    for arg in args or []:
        if arg not in deduped:
            deduped.append(arg)
    return deduped


class AuthStrategy(ABC):
    """Interface para estratégias de autenticação."""

    @abstractmethod
    async def create_context(
        self,
        playwright: Playwright,
        headless: bool = True,
        user_agent: Optional[str] = None,
        args: Optional[Iterable[str]] = None,
        proxy: Optional[Dict[str, str]] = None,
        bypass_csp: bool = True,
    ) -> BrowserContext:
        raise NotImplementedError

    async def destroy(self) -> None:
        return None


class LocalAuth(AuthStrategy):
    """
    Usa um diretório persistente do Chromium para guardar a sessão,
    equivalente ao LocalAuth da versão em Node.
    """

    def __init__(self, session_name: str = "default", data_path: Optional[Path] = None):
        base_path = data_path or Path.home() / ".cache" / "wwebjs-py"
        self.user_data_dir = Path(base_path) / session_name
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

    async def create_context(
        self,
        playwright: Playwright,
        headless: bool = True,
        user_agent: Optional[str] = None,
        args: Optional[Iterable[str]] = None,
        proxy: Optional[Dict[str, str]] = None,
        bypass_csp: bool = True,
    ) -> BrowserContext:
        deduped_args = _dedupe_args(args)
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=headless,
            args=deduped_args,
            user_agent=user_agent,
            proxy=proxy,
            bypass_csp=bypass_csp,
        )
        return context

    async def destroy(self) -> None:
        return None

    def __repr__(self) -> str:  # pragma: no cover - representação simples
        return f"<LocalAuth user_data_dir={self.user_data_dir}>"


class PickleAuth(AuthStrategy):
    """
    Usa pickle para salvar e restaurar a sessão do navegador.
    Armazena os cookies e o storage state em um arquivo pickle para
    evitar a necessidade de autenticação repetida.
    """

    def __init__(self, session_name: str = "default", data_path: Optional[Path] = None):
        base_path = data_path or Path.home() / ".cache" / "wwebjs-py"
        self.session_dir = Path(base_path) / session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.pickle_file = self.session_dir / "session.pkl"
        self._context: Optional[BrowserContext] = None

    async def create_context(
        self,
        playwright: Playwright,
        headless: bool = True,
        user_agent: Optional[str] = None,
        args: Optional[Iterable[str]] = None,
        proxy: Optional[Dict[str, str]] = None,
        bypass_csp: bool = True,
    ) -> BrowserContext:
        deduped_args = _dedupe_args(args)

        storage_state: Optional[dict] = None
        if self.pickle_file.exists():
            try:
                with open(self.pickle_file, "rb") as f:
                    storage_state = pickle.load(f)
                logger.info("Sessão carregada de %s", self.pickle_file)
            except Exception as exc:  # pragma: no cover - resiliência de IO
                logger.warning("Não foi possível carregar sessão de %s: %s", self.pickle_file, exc)
                storage_state = None

        # Cria o contexto com ou sem storage_state
        self._context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.session_dir / "browser_data"),
            headless=headless,
            args=deduped_args,
            user_agent=user_agent,
            proxy=proxy,
            bypass_csp=bypass_csp,
        )

        # Se temos storage_state salvo, restaura cookies e localStorage
        if storage_state:
            try:
                # Adiciona cookies
                if "cookies" in storage_state:
                    await self._context.add_cookies(storage_state["cookies"])

                # Restaura localStorage/sessionStorage via script
                if "origins" in storage_state:
                    for origin_data in storage_state["origins"]:
                        if "localStorage" in origin_data:
                            for page in self._context.pages:
                                try:
                                    await page.evaluate(
                                        """(items) => {
                                            for (const [key, value] of Object.entries(items)) {
                                                localStorage.setItem(key, value);
                                            }
                                        }""",
                                        origin_data["localStorage"]
                                    )
                                except Exception:
                                    logger.debug("Falha ao restaurar localStorage em uma página.")
            except Exception as exc:  # pragma: no cover - resiliência de IO/JS
                logger.warning("Erro ao restaurar estado salvo: %s", exc)

        return self._context

    async def save_session(self) -> None:
        """Salva o estado atual da sessão em pickle."""
        if not self._context:
            return

        try:
            storage_state = await self._context.storage_state()
            with open(self.pickle_file, "wb") as f:
                pickle.dump(storage_state, f)
            logger.info("Sessão salva em %s", self.pickle_file)
        except Exception as exc:  # pragma: no cover - resiliência de IO
            logger.exception("Erro ao salvar sessão em %s", self.pickle_file, exc_info=exc)

    async def destroy(self) -> None:
        """Salva a sessão antes de destruir."""
        if self._context:
            await self.save_session()
        return None

    def __repr__(self) -> str:
        return f"<PickleAuth pickle_file={self.pickle_file}>"
