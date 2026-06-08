# 📻 Radio Streaming com SCTP + TLS

Sistema de rádio em tempo real usando SCTP (Stream Control Transmission Protocol) para transmissão de áudio PCM com metadados em stream separado, e TLS/TCP para autenticação segura de clientes.

## 🛠 Requisitos do Sistema

- Python 3.8+
- FFmpeg/FFplay
- libsctp-dev
- OpenSSL

## 📦 Instalação

### 1. Dependências do Sistema (Linux)

```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y ffmpeg python3-dev libsctp-dev openssl

# Fedora/RHEL
sudo dnf install -y ffmpeg python3-devel lksctp-tools-devel openssl

# Arch
sudo pacman -S ffmpeg python lksctp-tools openssl
```

### 2. Clone/Copie o Projeto e Crie o Ambiente Virtual

```bash
cd radio-redes
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependências Python

```bash
pip install --upgrade pip
pip install pysctp
```

### 4. Gerar o Certificado TLS

```bash
mkdir -p radio-tls

openssl req -x509 -newkey rsa:2048 \
  -keyout radio-tls/server.key \
  -out radio-tls/server.crt \
  -days 365 -nodes \
  -subj "/CN=127.0.0.1" \
  -addext "subjectAltName=IP:127.0.0.1"
```

> Para rodar em outra máquina, substitua `127.0.0.1` pelo IP do servidor tanto no comando acima quanto no `client.py`.

## 🏗 Arquitetura

O sistema usa **dois canais independentes**:

**Canal de autenticação — TLS/TCP (porta 5001)**
- Cliente envia usuário + hash SHA-256 da senha
- Servidor valida e retorna um token de sessão (64 chars)
- Todo o tráfego é encriptado via TLS 1.2+

**Canal de streaming — SCTP (porta 5000)**
- Cliente apresenta o token antes de receber áudio
- `STREAM 0`: chunks de áudio PCM s16le (~100ms por chunk)
- `STREAM 1`: metadados (tipo de faixa, nome do arquivo, SYNC)

Esta separação segue o padrão de canal de controle + canal de dados — o mesmo usado em protocolos como SIP/RTP.

### Fluxo de conexão

```
1. cliente  →  auth_server  : TLS handshake + usuário|hash_senha
2. auth_server  →  cliente  : TOKEN
3. cliente  →  server       : TOKEN via SCTP
4. server   →  cliente      : OK
5. server   →  cliente      : stream de áudio PCM (stream 0)
                              metadados e SYNC (stream 1)
```

### Por que PCM e não MP3?

O PCM (s16le) é áudio bruto — cada 4 bytes representa um instante de som (2 bytes canal esquerdo + 2 bytes canal direito). Isso simplifica a transmissão: qualquer sequência de bytes é válida, sem necessidade de decodificar frames MP3 no lado do cliente. O ffmpeg converte os arquivos `.mp3` para PCM no servidor antes de transmitir.

## 🎧 Como Usar

### Terminal 1 — Iniciar o Servidor

```bash
source .venv/bin/activate
python3 servidor/server.py
```

Saída esperada:
```
🔐 Servidor TLS/TCP ouvindo na porta 5001
📡 Servidor SCTP ouvindo na porta 5000
📻 Broadcaster iniciado
🎵 Tocando: track01.mp3
```

### Terminal 2 — Iniciar o Cliente

```bash
source .venv/bin/activate
python3 cliente/client.py
```

Saída esperada:
```
🔐 Conexão TLS estabelecida com 127.0.0.1:5001
✅ Token recebido!
📻 Stream liberado!
▶ Player iniciado.

====================
🎵 Tocando música
Arquivo: track01.mp3
====================
```

### Múltiplos Clientes

Abra novos terminais e rode `python3 cliente/client.py` em cada um. Todos receberão o mesmo stream sincronizado simultaneamente.

## 🎵 Adicionando Áudio

Coloque arquivos `.mp3` em:
- `audios/musicas/` — faixas principais (ordem sequencial)
- `audios/propagandas/` — tocadas entre músicas (70% de chance)
- `audios/eastereggs/` — surpresas aleatórias (30% de chance)

Reinicie o servidor para carregar as novas faixas.

## 👤 Gerenciando Usuários

Os usuários estão definidos em `servidor/auth_server.py`:

```python
USUARIOS = {
    "aluno1": hashlib.sha256(b"senha123").hexdigest(),
    "aluno2": hashlib.sha256(b"senha456").hexdigest(),
}
```

Para adicionar um usuário, gere o hash da senha no terminal:

```bash
python3 -c "import hashlib; print(hashlib.sha256(b'sua_senha').hexdigest())"
```

## 🌐 Rodar em Outra Máquina

1. Regere o certificado com o IP real do servidor:
```bash
openssl req -x509 -newkey rsa:2048 \
  -keyout radio-tls/server.key \
  -out radio-tls/server.crt \
  -days 365 -nodes \
  -subj "/CN=192.168.1.100" \
  -addext "subjectAltName=IP:192.168.1.100"
```

2. Copie `radio-tls/server.crt` para a máquina do cliente.

3. Edite `cliente/client.py`:
```python
HOST = "192.168.1.100"  # IP do servidor
```

4. Libere as portas no firewall:
```bash
sudo ufw allow 5000
sudo ufw allow 5001
```

## 🐛 Troubleshooting

| Erro | Solução |
|------|---------|
| `ModuleNotFoundError: sctp` | `pip install pysctp` |
| `No such file or directory: ffplay` | `sudo apt-get install ffmpeg` |
| `FileNotFoundError: server.crt` | Gere o certificado (passo 4 da instalação) |
| `CERTIFICATE_VERIFY_FAILED` | Certificado não contém o IP correto — regere com o IP certo no `-addext` |
| `Connection refused` porta 5000 | Verifique se `server.py` está rodando |
| `Connection refused` porta 5001 | O servidor TLS sobe junto com `server.py` — cheque erros no terminal |
| `Token inválido` | Verifique usuário/senha em `auth_server.py` e `client.py` |
| Áudio com gaps/cortes | `ffprobe audios/musicas/track01.mp3` — verifique se os arquivos são válidos |

## 📚 Referências

- [pysctp Documentation](https://github.com/philpraxis/pysctp)
- [FFplay Documentation](https://ffmpeg.org/ffplay.html)
- [SCTP — RFC 4960](https://datatracker.ietf.org/doc/html/rfc4960)
- [DTLS over SCTP — RFC 6083](https://datatracker.ietf.org/doc/html/rfc6083)
- [Python ssl module](https://docs.python.org/3/library/ssl.html)
