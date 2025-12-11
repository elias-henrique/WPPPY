from __future__ import annotations

import pickle
from pathlib import Path
from typing import Iterable, Optional

from playwright.async_api import BrowserContext, Playwright


class AuthStrategy:
    """Interface para estratégias de autenticação."""

    async def create_context(
        self,
        playwright: Playwright,
        headless: bool = True,
        user_agent: Optional[str] = None,
        args: Optional[Iterable[str]] = None,
        proxy: Optional[dict] = None,
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
        proxy: Optional[dict] = None,
        bypass_csp: bool = True,
    ) -> BrowserContext:
        launch_args = list(args or [])
        # Remove duplicatas para evitar erros de chromium
        deduped_args = []
        for arg in launch_args:
            if arg not in deduped_args:
                deduped_args.append(arg)

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
        proxy: Optional[dict] = None,
        bypass_csp: bool = True,
    ) -> BrowserContext:
        launch_args = list(args or [])
        # Remove duplicatas para evitar erros de chromium
        deduped_args = []
        for arg in launch_args:
            if arg not in deduped_args:
                deduped_args.append(arg)

        # Tenta carregar sessão salva
        storage_state = None
        if self.pickle_file.exists():
            try:
                with open(self.pickle_file, "rb") as f:
                    storage_state = pickle.load(f)
                print(f"✓ Sessão carregada de {self.pickle_file}")
            except Exception as e:
                print(f"⚠ Não foi possível carregar sessão: {e}")
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
                                    pass
            except Exception as e:
                print(f"⚠ Erro ao restaurar estado: {e}")

        return self._context

    async def save_session(self) -> None:
        """Salva o estado atual da sessão em pickle."""
        if not self._context:
            return

        try:
            storage_state = await self._context.storage_state()
            with open(self.pickle_file, "wb") as f:
                pickle.dump(storage_state, f)
            print(f"✓ Sessão salva em {self.pickle_file}")
        except Exception as e:
            print(f"⚠ Erro ao salvar sessão: {e}")

    async def destroy(self) -> None:
        """Salva a sessão antes de destruir."""
        if self._context:
            await self.save_session()
        return None

    def __repr__(self) -> str:
        return f"<PickleAuth pickle_file={self.pickle_file}>"
