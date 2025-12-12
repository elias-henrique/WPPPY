import asyncio
import logging
import signal
from contextlib import suppress

import qrcode

from whatsapp_web_py import Client, ClientOptions, Events, PickleAuth

logger = logging.getLogger(__name__)


def display_qr(qr_string: str) -> None:
    """Gera e exibe o QR code no terminal e salva como imagem."""
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(qr_string)
    qr.make(fit=True)

    qr.print_ascii(invert=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save("whatsapp_qr.png")
    logger.info("QR Code salvo em whatsapp_qr.png. Escaneie para conectar.")


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    auth_strategy = PickleAuth(session_name="default")
    options = ClientOptions(auth_strategy=auth_strategy, headless=True)

    async with Client(options) as client:
        client.on(Events.QR, display_qr)

        async def on_ready() -> None:
            logger.info("Cliente pronto. Persistindo sessão.")
            await auth_strategy.save_session()

        async def on_message(msg) -> None:
            logger.info("[%s] %s", msg.chat_id, msg.body)

        client.on(Events.READY, on_ready)
        client.on(Events.MESSAGE, on_message)

        if not await client.wait_until_ready(timeout=120):
            raise TimeoutError(
                "Tempo excedido aguardando o WhatsApp ficar pronto.")

        stop_event = asyncio.Event()
        _install_signal_handlers(stop_event)
        logger.info("Conectado. Pressione Ctrl+C para encerrar.")
        await stop_event.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Encerrando por teclado.")
