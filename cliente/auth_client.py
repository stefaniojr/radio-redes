# auth_client.py
import ssl
import socket
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
crt_path = os.path.join(BASE_DIR, "..", "radio-tls", "server.crt")

AUTH_PORT = 5001

# conexão ao servidor TLS/TCP
def autenticar(host, usuario, senha):
    senha_hash = hashlib.sha256(senha.encode()).hexdigest()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(crt_path)
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.check_hostname = False
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    with socket.create_connection((host, AUTH_PORT)) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls_conn:  # renomeia aqui
            print(f"🔐 Conexão TLS estabelecida com {host}:{AUTH_PORT}")

            tls_conn.sendall(f"{usuario}|{senha_hash}\n".encode())
            resposta = tls_conn.recv(256).decode().strip()

    partes = resposta.split("|")
    if partes[0] == "TOKEN":
        print(f"✅ Token recebido!")
        return partes[1]
    else:
        raise Exception(f"Autenticação falhou: {resposta}")