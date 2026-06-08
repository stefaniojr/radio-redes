import socket
import subprocess
import threading
import time
import sctp
from playlist_manager import PlaylistManager
from auth_server import iniciar_auth_server, validar_token

HOST = "0.0.0.0"
PORT = 5000

clientes = []
clientes_lock = threading.Lock()

playlist = PlaylistManager()

# PCM s16le stereo 44100Hz: 44100 * 2 canais * 2 bytes = 176400 bytes/s
SAMPLE_RATE = 44100
CHANNELS = 2
BYTES_PER_SAMPLE = 2
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE  # 176400

# ~100ms de áudio por chunk — bom equilíbrio entre latência e overhead
CHUNK_SIZE = int(BYTES_PER_SECOND * 0.1)  # 17640 bytes
FRAME_TIME = CHUNK_SIZE / BYTES_PER_SECOND  # 0.1s

# Estado global protegido
now_playing = None
track_start_time = None
state_lock = threading.Lock()

def remover_cliente(cliente):
    with clientes_lock:
        if cliente in clientes:
            clientes.remove(cliente)
            print("Cliente removido.")
    try:
        cliente.close()
    except Exception:
        pass


def broadcast_meta(tipo, nome):
    mensagem = f"{tipo}|{nome}".encode()

    with state_lock:
        playing = now_playing
        start = track_start_time

    with clientes_lock:
        destino = list(clientes)

    para_remover = []

    for cliente in destino:
        try:
            cliente.sctp_send(mensagem, stream=1, ppid=0)

            if playing and start:
                sync = f"SYNC|{playing}|{start:.6f}".encode()
                cliente.sctp_send(sync, stream=1, ppid=0)

        except Exception:
            para_remover.append(cliente)

    for c in para_remover:
        remover_cliente(c)


def transmitir_audio_pcm(file_path):
    global now_playing, track_start_time

    print("▶ Streaming:", file_path.name)

    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-loglevel", "quiet",
            "-i", str(file_path),
            "-acodec", "pcm_s16le",
            "-ac", str(CHANNELS),
            "-ar", str(SAMPLE_RATE),
            "-f", "s16le",
            "pipe:1",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    # Marca início da faixa APÓS ffmpeg estar pronto
    with state_lock:
        track_start_time = time.time()

    proximo_envio = time.monotonic()

    while True:
        chunk = proc.stdout.read(CHUNK_SIZE)
        if not chunk:
            break

        with clientes_lock:
            destino = list(clientes)

        para_remover = []

        for cliente in destino:
            try:
                cliente.sctp_send(chunk, stream=0, ppid=0)
            except Exception:
                para_remover.append(cliente)

        for c in para_remover:
            remover_cliente(c)

        # Timing real: espera o tempo proporcional ao áudio enviado
        proximo_envio += FRAME_TIME
        agora = time.monotonic()
        espera = proximo_envio - agora
        if espera > 0:
            time.sleep(espera)

    proc.wait()


def broadcaster():
    global now_playing

    print("📻 Broadcaster iniciado")

    while True:
        # Toca música
        musica = playlist.proxima_musica()

        with state_lock:
            now_playing = musica.name

        print("🎵 Tocando:", musica.name)
        broadcast_meta("MUSIC", musica.name)
        transmitir_audio_pcm(musica)

        # Toca interrupção (propaganda ou easter egg)
        tipo, interrupcao = playlist.proxima_interrupcao()

        with state_lock:
            now_playing = interrupcao.name

        print(f"{'📢' if tipo == 'ADVERTISEMENT' else '🥚'} {tipo}: {interrupcao.name}")
        broadcast_meta(tipo, interrupcao.name)
        transmitir_audio_pcm(interrupcao)


def aceitar_clientes(server):
    while True:
        try:
            cliente, addr = server.accept()
            print(f"🔌 Conexão SCTP: {addr}")

            cliente.settimeout(5.0)
            _, _, msg, _ = cliente.sctp_recv(256)
            cliente.settimeout(None)

            token = msg.decode().strip()
            usuario = validar_token(token)

            if not usuario:
                print(f"❌ Token inválido de {addr}")
                cliente.sctp_send(b"ERRO|token_invalido", stream=1, ppid=0)
                cliente.close()
                continue

            cliente.sctp_send(b"OK", stream=1, ppid=0)
            print(f"🎧 {usuario} conectado ao stream ({addr})")

            with clientes_lock:
                clientes.append(cliente)

            # Envia estado atual imediatamente para o novo cliente
            with state_lock:
                playing = now_playing
                start = track_start_time

            if playing and start:
                try:
                    meta = f"MUSIC|{playing}".encode()
                    cliente.sctp_send(meta, stream=1, ppid=0)
                    sync = f"SYNC|{playing}|{start:.6f}".encode()
                    cliente.sctp_send(sync, stream=1, ppid=0)
                except Exception:
                    pass

        except Exception as e:
            print("Erro ao aceitar cliente:", e)


server = sctp.sctpsocket_tcp(socket.AF_INET)
server.initparams.num_ostreams = 5
server.initparams.max_instreams = 5
server.bind((HOST, PORT))
server.listen(10)
server.set_sndbuf(1024 * 1024 * 4)
server.set_rcvbuf(1024 * 1024 * 4)
server.set_nodelay(True)

print(f"📡 Servidor SCTP ouvindo na porta {PORT}")

threading.Thread(target=iniciar_auth_server, daemon=True).start()
threading.Thread(target=broadcaster, daemon=True).start()
aceitar_clientes(server)