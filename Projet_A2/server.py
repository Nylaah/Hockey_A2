import socket
import threading
import signal
import sys


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


HOST = get_local_ip()
PORT = 5000

clients      = {}     # conn -> username
roles_map    = {}     # conn -> {"role": ..., "username": ...}
lock         = threading.Lock()
game_started = False  # repassera à False quand les joueurs partent


def send(conn, message: str):
    try:
        conn.sendall((message + "\n").encode("utf-8"))
    except Exception:
        pass


def broadcast(message: str, sender_conn=None):
    """Envoie à tous sauf l'expéditeur."""
    with lock:
        for conn in list(clients):
            if conn != sender_conn:
                send(conn, message)


def broadcast_all(message: str):
    """Envoie à tous les clients connectés."""
    with lock:
        for conn in list(clients):
            send(conn, message)


def handle_client(conn, addr):
    global game_started
    username = None

    try:
        # Format reçu : "username|ROLE_DESIRE\n"
        raw = conn.recv(1024).decode("utf-8").strip()
        if "|" in raw:
            username, desired_role = raw.split("|", 1)
            desired_role = desired_role.upper()
        else:
            username, desired_role = raw, None

        if not username:
            send(conn, "USERNAME_REFUSED Pseudo vide interdit")
            return

        with lock:
            if username in clients.values():
                send(conn, "USERNAME_REFUSED Pseudo déjà utilisé")
                return

            if len(clients) >= 2:
                send(conn, "USERNAME_REFUSED Partie déjà pleine")
                return

            taken_roles = {meta["role"] for meta in roles_map.values()}
            if desired_role in ("LEFT", "RIGHT") and desired_role not in taken_roles:
                role = desired_role
            elif "LEFT" not in taken_roles:
                role = "LEFT"
            else:
                role = "RIGHT"

            clients[conn]   = username
            roles_map[conn] = {"role": role, "username": username}
            current_count   = len(clients)

        send(conn, "USERNAME_ACCEPTED")
        send(conn, f"ROLE {role}")
        print(f"[+] {username} connecté ({role}) depuis {addr}  [{current_count}/2]")
        broadcast(f"SERVER {username} a rejoint la partie", conn)

        # Lancer la partie dès que 2 joueurs sont présents
        if current_count == 2 and not game_started:
            with lock:
                game_started = True
            print("[*] 2 joueurs connectés — GAME_START")
            broadcast_all("GAME_START")

        # Boucle de lecture
        buf = ""
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data.decode("utf-8")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                if not line.startswith("POS"):   # POS est trop fréquent à afficher
                    print(f"[{username}] {line}")
                broadcast(f"{username}: {line}", conn)

    except (ConnectionResetError, OSError):
        pass

    finally:
        with lock:
            if conn in clients:
                del clients[conn]
                roles_map.pop(conn, None)
                remaining = len(clients)
                print(f"[-] {username} déconnecté  [{remaining}/2]")
                # Réinitialiser pour permettre une nouvelle partie
                if remaining < 2:
                    game_started = False
        broadcast(f"SERVER {username} a quitté la partie")
        try:
            conn.close()
        except Exception:
            pass


# ── Arrêt propre (Ctrl+C ou signal TERM) ────────────────────────────────────

server_sock = None


def shutdown(sig=None, frame=None):
    print("\n[!] Arrêt du serveur...")
    broadcast_all("SERVER Le serveur s'arrête.")
    with lock:
        for conn in list(clients):
            try:
                conn.close()
            except Exception:
                pass
    if server_sock:
        try:
            server_sock.close()
        except Exception:
            pass
    print("[!] Serveur arrêté proprement.")
    sys.exit(0)


signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

# ── Démarrage ────────────────────────────────────────────────────────────────

server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_sock.bind((HOST, PORT))
server_sock.listen()
print(f"Serveur en écoute sur {HOST}:{PORT}")
print("Appuie sur Ctrl+C pour arrêter proprement.\n")

try:
    while True:
        try:
            conn, addr = server_sock.accept()
        except OSError:
            break  # socket fermé par shutdown()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
except KeyboardInterrupt:
    shutdown()
