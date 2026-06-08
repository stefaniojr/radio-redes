import ssl
import socket
import threading
import secrets
import hashlib
import os



HOST = "0.0.0.0"
AUTH_PORT = 5001

# usuários: senha armazenada como hash sha256
USUARIOS = {
    "aluno1": hashlib.sha256(b"senha123").hexdigest(),
    "aluno2": hashlib.sha256(b"senha456").hexdigest(),
}

# tokens válidos: {token: usuario}
tokens_validos = {}
tokens_lock = threading.Lock()


def gerar_token():
    return secrets.token_hex(32) 


def validar_token(token):
    with tokens_lock:
        return tokens_validos.get(token)


def handle_auth(conn, addr):
    try:
        # recebe "usuario|senha_em_hash"
        dados = conn.recv(512).decode().strip()
        partes = dados.split("|")

        if len(partes) != 2:
            conn.sendall(b"ERRO|formato_invalido\n")
            return

        usuario, senha_hash = partes

        if USUARIOS.get(usuario) == senha_hash:
            token = gerar_token()
            with tokens_lock:
                tokens_validos[token] = usuario
            conn.sendall(f"TOKEN|{token}\n".encode())
            print(f"✅ {usuario} autenticado ({addr}) → token gerado")
        else:
            conn.sendall(b"ERRO|credenciais_invalidas\n")
            print(f"❌ Falha: {usuario} ({addr})")

    except Exception as e:
        print(f"Erro no auth handler: {e}")
    finally:
        conn.close()


def iniciar_auth_server():
    # contexto TLS
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    # Pega o diretório onde o auth_server.py está salvo
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # Constrói o caminho até os certificados (ajuste se a pasta estiver em outro nível)
    crt_path = os.path.join(BASE_DIR, "..", "radio-tls", "server.crt")
    key_path = os.path.join(BASE_DIR, "..", "radio-tls", "server.key")

    ctx.load_cert_chain(crt_path, key_path)

    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, AUTH_PORT))
    sock.listen(10)

    tls_sock = ctx.wrap_socket(sock, server_side=True)
    print(f"🔐 Servidor TLS/TCP ouvindo na porta {AUTH_PORT}")

    while True:
        try:
            conn, addr = tls_sock.accept()
            threading.Thread(target=handle_auth, args=(conn, addr), daemon=True).start()
        except Exception as e:
            print(f"Erro ao aceitar auth: {e}")


if __name__ == "__main__":
    iniciar_auth_server()