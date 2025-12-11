
# WPPPY · WhatsApp Web API em Python

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![WhatsApp](https://img.shields.io/badge/WhatsApp-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)

[![Typing SVG](https://readme-typing-svg.herokuapp.com?duration=3000&pause=1000&center=true&vCenter=true&width=550&lines=Automatize+o+WhatsApp+Web+com+Python;Envie+mensagens%2C+ou%C3%A7a+eventos%2C+crie+bots)](https://github.com/)

</div>

---

## Índice

- [WPPPY · WhatsApp Web API em Python](#wpppy--whatsapp-web-api-em-python)
  - [Índice](#índice)
  - [Visão Geral](#visão-geral)
  - [Funcionalidades](#funcionalidades)
  - [Instalação](#instalação)
  - [Uso Básico](#uso-básico)
    - [Primeiro acesso (QR Code)](#primeiro-acesso-qr-code)
    - [Próximas execuções (sessão persistente)](#próximas-execuções-sessão-persistente)
  - [Exemplos Rápidos](#exemplos-rápidos)
    - [Bot de resposta automática](#bot-de-resposta-automática)
    - [Enviar mensagem para um contato](#enviar-mensagem-para-um-contato)
    - [Listar todos os chats](#listar-todos-os-chats)
  - [Estrutura do Projeto](#estrutura-do-projeto)
  - [Autenticação e sessão](#autenticação-e-sessão)
    - [PickleAuth](#pickleauth)
    - [LocalAuth](#localauth)
  - [Eventos disponíveis](#eventos-disponíveis)
  - [Contribuição](#contribuição)
  - [Aviso Legal](#aviso-legal)

---

## Visão Geral

WPPPY é uma biblioteca Python para controlar o WhatsApp Web de forma programática, inspirada em [`whatsapp-web.js`](https://github.com/pedroslopez/whatsapp-web.js).

Permite:

- enviar mensagens de texto e mídia,
- receber eventos em tempo real,
- gerenciar contatos e conversas,
- construir bots e automações usando Python e Playwright.

---

## Funcionalidades

- Autenticação persistente (QR Code apenas na primeira vez)
- Sessão armazenada em arquivo pickle
- Envio de mensagens (texto, mídia, etc.)
- Recebimento de mensagens via listeners
- Gerenciamento de contatos e chats
- Arquitetura orientada a eventos (event-driven)
- API assíncrona baseada em `asyncio`

---

## Instalação

```bash
# Clone o repositório
git clone <seu-repo>
cd WPPPY

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Instale as dependências
pip install playwright qrcode pyee
playwright install chromium
````

---

## Uso Básico

### Primeiro acesso (QR Code)

```python
import asyncio
from whatsapp_web_py import Client, ClientOptions, Events, PickleAuth

async def main():
    client = Client(
        ClientOptions(
            auth_strategy=PickleAuth(session_name="minha_sessao")
        )
    )

    # Exibe o QR Code no terminal
    client.on(Events.QR, lambda qr: print(f"Escaneie este QR:\n{qr}"))

    # Dispara quando o cliente está pronto
    client.on(Events.READY, lambda: print("WhatsApp conectado."))

    # Recebe mensagens
    client.on(Events.MESSAGE, lambda msg: print(f"[{msg.from_}] {msg.body}"))

    await client.initialize()
    await asyncio.Event().wait()  # mantém o script em execução

asyncio.run(main())
```

### Próximas execuções (sessão persistente)

Depois do primeiro login bem-sucedido, a sessão será carregada automaticamente do arquivo pickle.
Na maioria dos casos, o mesmo código acima é suficiente; o QR Code não será solicitado novamente enquanto a sessão for válida.

---

## Exemplos Rápidos

### Bot de resposta automática

```python
from whatsapp_web_py import Events

async def responder_mensagem(msg):
    texto = (msg.body or "").lower()

    if texto == "oi":
        await msg.reply("Olá! Como posso ajudar?")
    elif "preço" in texto:
        await msg.reply("Nossos preços podem ser consultados no site ou com o time comercial.")

client.on(Events.MESSAGE, responder_mensagem)
```

### Enviar mensagem para um contato

```python
async def enviar_mensagem():
    # Número no formato internacional + domínio do WhatsApp
    jid = "5511999999999@c.us"

    await client.send_message(
        jid,
        "Mensagem enviada via WPPPY."
    )
```

### Listar todos os chats

```python
async def listar_chats():
    chats = await client.get_chats()
    for chat in chats:
        last = getattr(chat, "last_message", None)
        preview = getattr(last, "body", "") if last else ""
        print(f"{chat.name}  |  {preview}")
```

---

## Estrutura do Projeto

```bash
WPPPY/
├── example.py              # Exemplo de uso
├── whatsapp_web_py/        # Biblioteca principal
│   ├── __init__.py
│   ├── auth.py             # Estratégias de autenticação (LocalAuth, PickleAuth)
│   ├── client.py           # Cliente principal
│   ├── events.py           # Eventos expostos pela biblioteca
│   ├── structures.py       # Estruturas: Message, Chat, Contact, etc.
│   └── js/                 # Scripts JavaScript injetados no WhatsApp Web
├── .gitignore
└── README.md
```

---

## Autenticação e sessão

Os dados de autenticação são armazenados em:

```text
~/.cache/wwebjs-py/<session_name>/
├── session.pkl        # Sessão serializada
└── browser_data/      # Dados do navegador
```

Nunca compartilhe esses arquivos; eles permitem o uso da sua conta.

### PickleAuth

Estratégia simples e rápida, recomendada para desenvolvimento e ambientes controlados:

```python
from whatsapp_web_py import ClientOptions, PickleAuth

options = ClientOptions(
    auth_strategy=PickleAuth(session_name="bot_producao")
)
client = Client(options)
```

### LocalAuth

Utiliza o diretório persistente do Chromium, geralmente mais robusto para uso intensivo:

```python
from whatsapp_web_py import ClientOptions, LocalAuth

options = ClientOptions(
    auth_strategy=LocalAuth(session_name="bot_backup")
)
client = Client(options)
```

---

## Eventos disponíveis

| Evento           | Descrição                        | Exemplo de uso                                        |
| ---------------- | -------------------------------- | ----------------------------------------------------- |
| `QR`             | QR Code gerado                   | `client.on(Events.QR, handle_qr)`                     |
| `READY`          | Cliente conectado e pronto       | `client.on(Events.READY, on_ready)`                   |
| `MESSAGE`        | Nova mensagem recebida           | `client.on(Events.MESSAGE, on_message)`               |
| `MESSAGE_CREATE` | Mensagem criada (enviada ou não) | `client.on(Events.MESSAGE_CREATE, on_message_create)` |
| `AUTHENTICATED`  | Sessão autenticada               | `client.on(Events.AUTHENTICATED, on_auth)`            |
| `DISCONNECTED`   | Cliente desconectado             | `client.on(Events.DISCONNECTED, on_disconnect)`       |

Exemplo de definição de handlers:

```python
def on_ready():
    print("Cliente pronto.")

def on_disconnect(reason):
    print(f"Desconectado: {reason}")

client.on(Events.READY, on_ready)
client.on(Events.DISCONNECTED, on_disconnect)
```

---

## Contribuição

Contribuições são bem-vindas.

1. Faça um fork do repositório
2. Crie uma branch para sua feature ou correção
   `git checkout -b feature/minha-feature`
3. Faça commit das alterações
   `git commit -m "Add: minha-feature"`
4. Envie a branch para o seu fork
   `git push origin feature/minha-feature`
5. Abra um Pull Request descrevendo claramente a mudança

---

## Aviso Legal

Este projeto não é afiliado, associado, autorizado, endossado ou de qualquer forma oficialmente conectado ao WhatsApp ou à Meta Platforms, Inc.

O uso desta biblioteca é de responsabilidade do usuário. Automatizações podem violar os Termos de Serviço do WhatsApp.

---

