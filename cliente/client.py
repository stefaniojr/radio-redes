import sctp
import socket
import threading
import subprocess
import time
from queue import Queue, Full
from auth_client import autenticar

HOST = "127.0.0.1"
PORT = 5000

# Buffer
buffer_audio = Queue(maxsize=2000)

player_process = None
player_lock = threading.Lock()
player_morreu = threading.Event()

current_track = None
track_start_time = None

SAMPLE_RATE = 44100
CHANNELS = 2


def iniciar_player():
    global player_process

    with player_lock:
        player_process = subprocess.Popen(
                [
                "ffplay",
                "-f", "s16le",
                "-ar", "44100",
                "-ac", "2",
                "-nodisp",
                "-fflags", "nobuffer",        # latência mínima
                "-flags", "low_delay",         # sem buffer extra
                "-framedrop",                  # descarta frame se atrasado (evita acúmulo)
                "pipe:0",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        player_morreu.clear()
        print("▶ Player iniciado.")


def receber_audio(client):
    while True:
        try:
            fromaddr, flags, msg, notif = client.sctp_recv(65536)

            if notif.stream == 0:
                try:
                    buffer_audio.put(msg, timeout=0.5)
                except Full:
                    print("⚠ Buffer cheio, descartando")

            elif notif.stream == 1:
                processar_metadado(msg)

        except Full:
            print("⚠ CHUNK DESCARTADO")
            pass
        


def reproduzir_audio():
    iniciar_player()

    while True:
        # Se player morreu, reinicia
        if player_morreu.is_set():
            print("🔄 Reiniciando player...")
            iniciar_player()

        chunk = buffer_audio.get()

        if not chunk:
            continue

        with player_lock:
            proc = player_process

        try:
            proc.stdin.write(chunk)
            proc.stdin.flush()
        except (BrokenPipeError, OSError):
            print("⚠ Player encerrou, aguardando reinício...")
            player_morreu.set()
        except Exception as e:
            print("Erro no player:", e)
            player_morreu.set()


def processar_metadado(msg):
    global current_track, track_start_time

    try:
        texto = msg.decode()
        partes = texto.split("|")

        if partes[0] == "SYNC":
            _, music, start_time = partes
            current_track = music
            track_start_time = float(start_time)
            elapsed = time.time() - track_start_time

            print("\n====================")
            print(f"🎵 Música: {music}")
            print(f"⏱ Offset estimado: {elapsed:.2f}s") # apenas para depurar
            print("====================\n")
            return

        tipo, nome = partes

        icons = {"MUSIC": "🎵", "ADVERTISEMENT": "📢", "EASTER_EGG": "🥚"}
        labels = {"MUSIC": "Tocando música", "ADVERTISEMENT": "Propaganda", "EASTER_EGG": "Easter Egg"}

        print("\n====================")
        print(f"{icons.get(tipo, '?')} {labels.get(tipo, tipo)}")
        print(f"Arquivo: {nome}")
        print("====================\n")

    except Exception as e:
        print("Erro ao processar metadado:", e)

token = autenticar(HOST, usuario="aluno1", senha="senha143")

client = sctp.sctpsocket_tcp(socket.AF_INET)
client.events.data_io = True
client.events.sndrcvinfo = True

client.connect((HOST, PORT))

client.sctp_send(token.encode(), stream=0, ppid=0)

# aguarda confirmação
_, _, resp, _ = client.sctp_recv(64)
if resp != b"OK":
    print("❌ Token rejeitado pelo servidor SCTP")
    exit(1)

print("📻 Stream liberado!")

print(f"📻 Conectado a {HOST}:{PORT}")

threading.Thread(target=receber_audio, args=(client,), daemon=True).start()
threading.Thread(target=reproduzir_audio, daemon=True).start()

input("Pressione ENTER para encerrar...\n")