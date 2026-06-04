import socket
import threading
import time


class NetworkClient:
    """Gère la connexion TCP vers le serveur de jeu."""

    def __init__(self):
        self._sock     = None
        self._incoming = []          # messages reçus en attente
        self._lock     = threading.Lock()
        self._running  = False

    # ── Connexion ─────────────────────────────────────────────────────────────

    def connect(self, server_ip: str, port: int,
                username: str, role: str) -> str | None:
        """
        Se connecte au serveur, effectue le handshake.
        Retourne le rôle assigné par le serveur, ou None en cas d'échec.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(5)
        self._sock.connect((server_ip, port))
        self._sock.settimeout(None)

        self._running = True
        threading.Thread(target=self._recv_loop, daemon=True).start()

        # Envoi du pseudo + rôle souhaité
        self._sock.sendall(f"{username}|{role}\n".encode("utf-8"))

        response = self._wait_one(timeout=10)
        if response is None or response.startswith("USERNAME_REFUSED"):
            return None

        role_msg = self._wait_one(timeout=10)
        if role_msg and role_msg.startswith("ROLE"):
            return role_msg.split()[1]
        return role

    # ── Thread de réception ───────────────────────────────────────────────────

    def _recv_loop(self):
        buf = ""
        while self._running:
            try:
                data = self._sock.recv(4096).decode("utf-8")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        with self._lock:
                            self._incoming.append(line)
            except Exception:
                break

    # ── API publique ──────────────────────────────────────────────────────────

    def get_messages(self) -> list[str]:
        """Retourne et vide la file des messages reçus."""
        with self._lock:
            msgs = self._incoming[:]
            self._incoming.clear()
        return msgs

    def put_back(self, msgs: list[str]):
        """Réinsère des messages en tête de file (ex. après GAME_START)."""
        with self._lock:
            self._incoming[:0] = msgs

    def send(self, msg: str):
        try:
            self._sock.sendall((msg + "\n").encode("utf-8"))
        except Exception:
            pass

    def disconnect(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    # ── Interne ───────────────────────────────────────────────────────────────

    def _wait_one(self, timeout: float = 5) -> str | None:
        """Attend et retourne le prochain message (bloquant, avec timeout)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._incoming:
                    return self._incoming.pop(0)
            time.sleep(0.01)
        return None
