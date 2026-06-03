import socket
import threading
import signal
import sys
import math
import random
import time as _time


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


HOST  = get_local_ip()
PORT  = 5000

# ── Dimensions (doivent correspondre à main.py) ──────────────────────────────
VWIDTH  = 1480
VHEIGHT = 600

# ── Paramètres balle ─────────────────────────────────────────────────────────
BALL_Z_MAX    = 220.0   # hauteur max de l'arc (unités arbitraires)
BALL_TOUCH_Z  = 55.0    # z en dessous duquel on détecte la touche
TOUCH_RADIUS  = 75      # distance joueur↔cible pour valider la touche
MARGIN        = 110     # marge aux bords pour les cibles aléatoires

# ── État global ──────────────────────────────────────────────────────────────
clients      = {}   # conn -> username
roles_map    = {}   # conn -> {"role": str}
lock         = threading.Lock()
game_started = False

# État du jeu (protégé par game_lock)
game_lock    = threading.Lock()
player_pos   = {}          # role -> {"x": float, "y": float}
scores       = {"LEFT": 0, "RIGHT": 0}
server_role  = "LEFT"      # qui sert prochain
last_toucher = None        # dernier joueur ayant touché la balle
ball_flight  = None        # BallFlight en cours ou None


# ── Balle ────────────────────────────────────────────────────────────────────

class BallFlight:
    """Trajectoire parabolique d'une balle d'un point à un autre."""

    def __init__(self, sx: float, sy: float, tx: float, ty: float,
                 T: float, from_role: str):
        self.sx = sx; self.sy = sy
        self.tx = tx; self.ty = ty
        self.T  = T
        self.t  = 0.0
        self.from_role = from_role
        self.x = sx; self.y = sy; self.z = 0.0

    def update(self, dt: float):
        self.t = min(self.t + dt, self.T)
        p       = self.t / self.T
        self.x  = self.sx + (self.tx - self.sx) * p
        self.y  = self.sy + (self.ty - self.sy) * p
        self.z  = BALL_Z_MAX * math.sin(math.pi * p)

    @property
    def progress(self) -> float:
        return self.t / self.T if self.T > 0 else 1.0

    @property
    def done(self) -> bool:
        return self.t >= self.T


def _random_target(from_role: str):
    """Choisit une position aléatoire sur le terrain adverse."""
    if from_role == "LEFT":
        x = random.uniform(VWIDTH / 2 + MARGIN, VWIDTH - MARGIN)
    else:
        x = random.uniform(MARGIN, VWIDTH / 2 - MARGIN)
    y = random.uniform(MARGIN, VHEIGHT - MARGIN)
    return x, y


def _launch(from_role: str, sx: float, sy: float) -> BallFlight:
    tx, ty = _random_target(from_role)
    T      = random.uniform(1.3, 2.2)
    return BallFlight(sx, sy, tx, ty, T, from_role)


# ── Réseau ───────────────────────────────────────────────────────────────────

def send(conn, message: str):
    try:
        conn.sendall((message + "\n").encode("utf-8"))
    except Exception:
        pass


def broadcast(message: str, sender_conn=None):
    with lock:
        for conn in list(clients):
            if conn != sender_conn:
                send(conn, message)


def broadcast_all(message: str):
    with lock:
        for conn in list(clients):
            send(conn, message)


# ── Logique de jeu ───────────────────────────────────────────────────────────

def _score_point(scorer: str):
    """Attribue un point au scorer et prépare le service suivant."""
    global scores, server_role, ball_flight, last_toucher
    with game_lock:
        scores[scorer] += 1
        server_role  = scorer
        last_toucher = None
        ball_flight  = None
        sl, sr = scores["LEFT"], scores["RIGHT"]
    # broadcast HORS de game_lock
    broadcast_all(f"SCORE {sl} {sr}")
    broadcast_all(f"SERVE_TURN {scorer}")
    print(f"[SCORE] {scorer} marque → {sl}-{sr}")


def ball_loop():
    """Boucle ~30 fps : met à jour la balle et détecte les touches."""
    global ball_flight, last_toucher
    last_t        = _time.time()
    remind_timer  = 0.0   # réémet SERVE_TURN périodiquement si balle pas en jeu

    while True:
        _time.sleep(1 / 30)
        now = _time.time()
        dt  = now - last_t
        last_t = now

        # ── Lire l'état sans tenir les locks trop longtemps ──
        with game_lock:
            flight       = ball_flight
            cur_remind   = remind_timer
            cur_started  = game_started

        # ── Cas : pas de balle en jeu ──
        if flight is None:
            cur_remind += dt
            if cur_remind >= 1.0 and cur_started:
                with game_lock:
                    remind_timer = 0.0
                # broadcast HORS de game_lock pour éviter tout blocage
                broadcast_all(f"SCORE {scores['LEFT']} {scores['RIGHT']}")
                broadcast_all(f"SERVE_TURN {server_role}")
                print(f"[REMIND] SERVE_TURN {server_role}")
            else:
                with game_lock:
                    remind_timer = cur_remind
            continue

        # ── Balle en vol ──
        with game_lock:
            remind_timer = 0.0
            flight.update(dt)
            bx, by, bz = flight.x, flight.y, flight.z
            btx, bty   = flight.tx, flight.ty
            bprog      = flight.progress
            bdone      = flight.done
            bfrom      = flight.from_role
            target_role = "RIGHT" if bfrom == "LEFT" else "LEFT"
            pos_target  = player_pos.get(target_role)

        # Diffuser l'état de la balle HORS game_lock
        broadcast_all(
            f"BALL {bx:.1f} {by:.1f} {bz:.1f} {btx:.1f} {bty:.1f} {bprog:.3f}"
        )

        # Détection de touche
        touched = False
        if bz < BALL_TOUCH_Z and pos_target:
            if math.hypot(pos_target["x"] - btx, pos_target["y"] - bty) < TOUCH_RADIUS:
                touched = True

        if touched:
            with game_lock:
                if last_toucher == target_role:
                    other = "LEFT" if target_role == "RIGHT" else "RIGHT"
                    ball_flight = None
                broadcast_all(f"BOUNCE {target_role}")
            if last_toucher == target_role:
                _score_point(other)
            else:
                with game_lock:
                    last_toucher = target_role
                    ball_flight  = _launch(target_role, bx, by)
                print(f"[BOUNCE] {target_role} renvoie la balle")

        elif bdone:
            _score_point(bfrom)


threading.Thread(target=ball_loop, daemon=True).start()


# ── Gestion des clients ──────────────────────────────────────────────────────

def handle_serve(conn):
    """Traite une demande de service d'un joueur."""
    global ball_flight, last_toucher
    with game_lock:
        if ball_flight is not None:
            return   # balle déjà en jeu
        info = roles_map.get(conn)
        if not info:
            return
        r = info["role"]
        if r != server_role:
            return   # pas son tour de servir
        # Position de départ = position actuelle du serveur (ou défaut)
        pos = player_pos.get(r, {})
        sx  = pos.get("x", VWIDTH / 4 if r == "LEFT" else VWIDTH * 3 / 4)
        sy  = pos.get("y", VHEIGHT / 2)
        last_toucher = r
        ball_flight  = _launch(r, sx, sy)
        broadcast_all(f"SERVING {r}")
        print(f"[SERVE] {r} sert")


def handle_client(conn, addr):
    global game_started
    username = None

    try:
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
            taken_roles = {m["role"] for m in roles_map.values()}
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
        print(f"[+] {username} ({role}) depuis {addr}  [{current_count}/2]")
        broadcast(f"SERVER {username} a rejoint la partie", conn)

        if current_count == 2 and not game_started:
            with lock:
                game_started = True
            print("[*] GAME_START")
            broadcast_all("GAME_START")
            broadcast_all(f"SCORE {scores['LEFT']} {scores['RIGHT']}")
            broadcast_all(f"SERVE_TURN {server_role}")

        # Boucle de lecture des messages
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

                if line == "SERVE":
                    handle_serve(conn)

                elif line.startswith("POS"):
                    # Mettre à jour la position connue du joueur côté serveur
                    parts = line.split()
                    if len(parts) >= 3:
                        with game_lock:
                            player_pos[role] = {
                                "x": float(parts[1]),
                                "y": float(parts[2])
                            }
                    broadcast(f"{username}: {line}", conn)

                else:
                    if not line.startswith("POS"):
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
                if remaining < 2:
                    game_started = False
        with game_lock:
            player_pos.pop(role if 'role' in dir() else "", None)
        broadcast(f"SERVER {username} a quitté la partie")
        try:
            conn.close()
        except Exception:
            pass


# ── Arrêt propre ─────────────────────────────────────────────────────────────

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
    print("[!] Serveur arrêté.")
    sys.exit(0)


signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

# ── Démarrage ────────────────────────────────────────────────────────────────

server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_sock.bind((HOST, PORT))
server_sock.listen()
print(f"Serveur en écoute sur {HOST}:{PORT}")
print("Ctrl+C pour arrêter.\n")

try:
    while True:
        try:
            conn, addr = server_sock.accept()
        except OSError:
            break
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
except KeyboardInterrupt:
    shutdown()
