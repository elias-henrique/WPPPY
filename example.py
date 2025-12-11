import asyncio

import qrcode

from whatsapp_web_py import Client, ClientOptions, Events, PickleAuth


def display_qr(qr_string: str) -> None:
    """Gera e exibe o QR code no terminal e salva como imagem."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_string)
    qr.make(fit=True)

    # Exibe no terminal
    qr.print_ascii(invert=True)

    # Salva como imagem
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("whatsapp_qr.png")
    print("\n✓ QR Code salvo em: whatsapp_qr.png")
    print("Escaneie com seu WhatsApp para conectar!\n")


async def main() -> None:
    # PickleAuth salva a sessão automaticamente
    auth_strategy = PickleAuth(session_name="default")
    client = Client(ClientOptions(auth_strategy=auth_strategy))

    client.on(Events.QR, display_qr)

    # Salva a sessão quando estiver pronto
    async def on_ready():
        print("Client is ready!")
        await auth_strategy.save_session()

    client.on(Events.READY, on_ready)
    client.on(Events.MESSAGE, lambda msg: print(f"[{msg.chat_id}] {msg.body}"))

    await client.initialize()
    print("Aguardando autenticação...")

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        print("\n\nEncerrando...")
    finally:
        try:
            await client.destroy()
            print("✓ Cliente encerrado com sucesso")
        except Exception as e:
            print(f"Aviso: erro ao encerrar (pode ser ignorado): {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nEncerrando...")
