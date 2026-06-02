import socket
import threading



def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Pas besoin que Google soit joignable, ça sert juste à choisir la bonne interface réseau
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

HOST = get_local_ip()
PORT = 5000

clients    = {}     # conn -> username
roles_map  = {}     # conn -> {"role": ..., "username": ...}
lock = threading.Lock()
connection_count = 0


def send(conn, message: str):
    try:
        conn.sendall((message + "\n").encode("utf-8"))
    except:
        pass


def broadcast(message: str, sender_conn=None):
    """Envoie à tous sauf l'expéditeur."""
    with lock:
        for conn in clients:
            if conn != sender_conn:
                send(conn, message)


def broadcast_all(message: str):
    """Envoie à tous les clients connectés."""
    with lock:
        for conn in clients:
            send(conn, message)


def handle_client(conn, addr):
    global connection_count
    username = None

    try:
        # Format reçu : "username|ROLE_DESIRE\n" (ex: "Alice|RIGHT\n")
        raw = conn.recv(1024).decode("utf-8").strip()
        if "|" in raw:
            username, desired_role = raw.split("|", 1)
            desired_role = desired_role.upper()
        else:
            username, desired_role = raw, None

        if username == "":
            send(conn, "USERNAME_REFUSED Pseudo vide interdit")
            conn.close()
            return

        with lock:
            if username in clients.values():
                send(conn, "USERNAME_REFUSED Pseudo déjà utilisé")
                conn.close()
                return

            # Rôles déjà pris
            taken = set(clients.values())  # pas les rôles, mais on track autrement
            taken_roles = {meta["role"] for meta in roles_map.values()}

            if desired_role in ("LEFT", "RIGHT") and desired_role not in taken_roles:
                role = desired_role
            elif "LEFT" not in taken_roles:
                role = "LEFT"
            else:
                role = "RIGHT"

            clients[conn]    = username
            roles_map[conn]  = {"role": role, "username": username}
            connection_count += 1
            current_count    = connection_count

        send(conn, "USERNAME_ACCEPTED")
        send(conn, f"ROLE {role}")
        print(f"[+] {username} connecté ({role}) depuis {addr}")
        broadcast(f"SERVER {username} a rejoint la partie", conn)

        # Quand 2 joueurs sont là, la partie peut commencer
        if current_count == 2:
            print("[*] 2 joueurs connectés — GAME_START")
            broadcast_all("GAME_START")

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
                print(f"[{username}] {line}")
                broadcast(f"{username}: {line}", conn)

    except ConnectionResetError:
        print(f"Connexion perdue avec {addr}")

    finally:
        with lock:
            if conn in clients:
                left_username = clients[conn]
                del clients[conn]
                roles_map.pop(conn, None)
                print(f"[-] {left_username} déconnecté")
                broadcast(f"SERVER {left_username} a quitté la partie")
        conn.close()


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()
print(f"Serveur en écoute sur {HOST}:{PORT}")

while True:
    conn, addr = server.accept()
    threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
