import socket
import threading
import signal
import sys
from .constants import PORT
from .connection import ClientConnection
from .ball_manager import BallManager


def _get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class GameServer:
    """Serveur de jeu : gère les connexions, le score et délègue la balle à BallManager."""

    def __init__(self):
        self._lock          = threading.Lock()
        self._connections: dict[str, ClientConnection] = {}   # role → conn
        self._usernames:   dict[str, str]              = {}   # role → username
        self._game_started  = False
        self._scores        = {"LEFT": 0, "RIGHT": 0}
        self._server_sock   = None
        self._ball          = BallManager(
            broadcast_fn = self._broadcast_all,
            on_score_fn  = self._handle_score,
        )

    # ── Broadcast ─────────────────────────────────────────────────────────────

    def _broadcast_all(self, msg: str):
        with self._lock:
            for conn in self._connections.values():
                conn.send(msg)

    def _broadcast_except(self, msg: str, exclude_role: str):
        with self._lock:
            for role, conn in self._connections.items():
                if role != exclude_role:
                    conn.send(msg)

    # ── Score ─────────────────────────────────────────────────────────────────

    def _handle_score(self, scorer: str):
        with self._lock:
            self._scores[scorer] += 1
            sl, sr = self._scores["LEFT"], self._scores["RIGHT"]
        self._broadcast_all(f"SCORE {sl} {sr}")
        self._broadcast_all(f"SERVE_TURN {scorer}")
        print(f"[SCORE] {scorer} marque → {sl}-{sr}")

    # ── Gestion d'un client ───────────────────────────────────────────────────

    def _handle_client(self, conn_obj: ClientConnection):
        role     = None
        username = "?"
        buf      = ""

        try:
            # Lecture du handshake (username|ROLE\n)
            raw = ""
            while "\n" not in raw:
                chunk = conn_obj.recv(1024).decode("utf-8")
                if not chunk:
                    return
                raw += chunk
            raw = raw.split("\n")[0].strip()

            if "|" in raw:
                username, desired = raw.split("|", 1)
                desired = desired.upper()
            else:
                username, desired = raw, None

            if not username:
                conn_obj.send("USERNAME_REFUSED Pseudo vide")
                return

            # Attribution du rôle
            with self._lock:
                if username in self._usernames.values():
                    conn_obj.send("USERNAME_REFUSED Pseudo déjà utilisé")
                    return
                if len(self._connections) >= 2:
                    conn_obj.send("USERNAME_REFUSED Partie déjà pleine")
                    return

                taken = set(self._connections.keys())
                if desired in ("LEFT", "RIGHT") and desired not in taken:
                    role = desired
                elif "LEFT" not in taken:
                    role = "LEFT"
                else:
                    role = "RIGHT"

                self._connections[role] = conn_obj
                self._usernames[role]   = username
                count = len(self._connections)

            conn_obj.send("USERNAME_ACCEPTED")
            conn_obj.send(f"ROLE {role}")
            print(f"[+] {username} ({role}) [{count}/2]")
            self._broadcast_except(f"SERVER {username} a rejoint", role)

            if count == 2 and not self._game_started:
                with self._lock:
                    self._game_started = True
                    sl = self._scores["LEFT"]
                    sr = self._scores["RIGHT"]
                self._broadcast_all("GAME_START")
                self._broadcast_all(f"SCORE {sl} {sr}")
                self._ball.start_game()
                print("[*] GAME_START — la partie commence")

            # Boucle de messages
            while True:
                data = conn_obj.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    self._dispatch(line, role, username, conn_obj)

        except (ConnectionResetError, OSError):
            pass
        finally:
            with self._lock:
                if role is not None:
                    self._connections.pop(role, None)
                    self._usernames.pop(role, None)
                remaining = len(self._connections)
                if remaining < 2:
                    self._game_started = False
                    self._ball.stop_game()
            self._broadcast_all(f"SERVER {username} a quitté la partie")
            conn_obj.close()
            print(f"[-] {username} déconnecté  [{remaining}/2]")

    def _dispatch(self, line: str, role: str, username: str,
                  conn_obj: ClientConnection):
        """Traite un message reçu d'un client."""
        if line == "SERVE":
            with self._lock:
                pos = self._ball._positions.get(role, {})
            sx = pos.get("x", 370.0 if role == "LEFT" else 1110.0)
            sy = pos.get("y", 300.0)
            self._ball.serve(role, sx, sy)

        elif line.startswith("POS"):
            parts = line.split()
            if len(parts) >= 3:
                self._ball.update_position(role, float(parts[1]), float(parts[2]))
            # Transmettre à l'autre joueur
            self._broadcast_except(f"{username}: {line}", role)

        else:
            if not line.startswith("IMPULSE"):
                print(f"[{username}] {line}")
            self._broadcast_except(f"{username}: {line}", role)

    # ── Démarrage du serveur ──────────────────────────────────────────────────

    def run(self, host: str | None = None):
        host = host or _get_local_ip()
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((host, PORT))
        self._server_sock.listen()
        print(f"Serveur sur {host}:{PORT}  |  Ctrl+C pour arrêter\n")

        def _shutdown(sig=None, frame=None):
            print("\n[!] Arrêt du serveur...")
            self._broadcast_all("SERVER Le serveur s'arrête.")
            with self._lock:
                for conn in list(self._connections.values()):
                    conn.close()
            if self._server_sock:
                try:
                    self._server_sock.close()
                except Exception:
                    pass
            sys.exit(0)

        # Les signaux ne peuvent être enregistrés que depuis le thread principal
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT,  _shutdown)
            signal.signal(signal.SIGTERM, _shutdown)

        try:
            while True:
                try:
                    conn, addr = self._server_sock.accept()
                except OSError:
                    break
                conn_obj = ClientConnection(conn, addr)
                threading.Thread(
                    target=self._handle_client,
                    args=(conn_obj,), daemon=True
                ).start()
        except KeyboardInterrupt:
            _shutdown()
