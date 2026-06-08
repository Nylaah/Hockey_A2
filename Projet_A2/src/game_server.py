import socket
import threading
import signal
import sys
from .constants import PORT, GAME_MODE_1V1, GAME_MODE_2V2
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


# Slots disponibles par mode
_SLOTS_1V1 = ["LEFT", "RIGHT"]
_SLOTS_2V2 = ["LEFT_1", "LEFT_2", "RIGHT_1", "RIGHT_2"]


class GameServer:
    """Serveur de jeu : gère les connexions, le score et délègue la balle à BallManager."""

    def __init__(self, mode: str = GAME_MODE_1V1):
        self._mode          = mode          # peut changer au 1er handshake
        self._max_players   = 2 if mode == GAME_MODE_1V1 else 4
        self._slots         = _SLOTS_1V1 if mode == GAME_MODE_1V1 else _SLOTS_2V2
        self._mode_locked   = False         # True dès qu'un client a défini le mode
        self._fill_done     = False         # True dès qu'un fill a été lancé

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
        """Envoie un message à tous les joueurs connectés."""
        with self._lock:
            for conn in self._connections.values():
                conn.send(msg)

    def _broadcast_except(self, msg: str, exclude_role: str):
        """Envoie un message à tous les joueurs sauf celui dont le rôle est exclude_role."""
        with self._lock:
            for role, conn in self._connections.items():
                if role != exclude_role:
                    conn.send(msg)

    # ── Score ─────────────────────────────────────────────────────────────────

    def _handle_score(self, scorer: str):
        """scorer est une ÉQUIPE ('LEFT' ou 'RIGHT')."""
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
            raw = str(raw.split("\n")[0]).strip()

            if "|" in raw:
                parts_hs = raw.split("|")
                username = parts_hs[0]
                desired  = parts_hs[1].upper() if len(parts_hs) > 1 else None
                req_mode = parts_hs[2].lower() if len(parts_hs) > 2 else GAME_MODE_1V1
            else:
                username, desired, req_mode = raw, None, GAME_MODE_1V1

            if not username:
                conn_obj.send("USERNAME_REFUSED Pseudo vide")
                return

            # Attribution du rôle
            with self._lock:
                # Le premier client fixe le mode pour toute la partie
                if not self._mode_locked:
                    self._mode        = req_mode
                    self._max_players = 2 if req_mode == GAME_MODE_1V1 else 4
                    self._slots       = _SLOTS_1V1 if req_mode == GAME_MODE_1V1 else _SLOTS_2V2
                    self._mode_locked = True
                    print(f"[MODE] fixé à {self._mode} par {username}")
                if username in self._usernames.values():
                    conn_obj.send("USERNAME_REFUSED Pseudo déjà utilisé")
                    return
                if len(self._connections) >= self._max_players:
                    conn_obj.send("USERNAME_REFUSED Partie déjà pleine")
                    return

                taken = set(self._connections.keys())

                if self._mode == GAME_MODE_1V1:
                    # Logique 1v1 : desired = "LEFT" ou "RIGHT"
                    if desired in ("LEFT", "RIGHT") and desired not in taken:
                        role = desired
                    elif "LEFT" not in taken:
                        role = "LEFT"
                    else:
                        role = "RIGHT"
                else:
                    # Logique 2v2 : desired = "LEFT" ou "RIGHT" (équipe souhaitée)
                    role = None
                    preferred_team = desired if desired in ("LEFT", "RIGHT") else None
                    search_order = self._slots[:]
                    if preferred_team:
                        search_order = (
                            [s for s in self._slots if s.startswith(preferred_team)]
                            + [s for s in self._slots if not s.startswith(preferred_team)]
                        )
                    for slot in search_order:
                        if slot not in taken:
                            role = slot
                            break
                    if role is None:
                        conn_obj.send("USERNAME_REFUSED Partie déjà pleine")
                        return

                self._connections[role] = conn_obj
                self._usernames[role]   = username
                count = len(self._connections)

            conn_obj.send("USERNAME_ACCEPTED")
            conn_obj.send(f"ROLE {role}")
            max_p = self._max_players
            print(f"[+] {username} ({role}) [{count}/{max_p}]")
            self._broadcast_except(f"SERVER {username} a rejoint ({role})", role)

            # En 2v2 : lancer un timer de 4 s après chaque nouvelle connexion.
            # Si la partie n'est toujours pas pleine à l'expiration → auto-fill.
            if self._mode != "1v1" and not self._game_started:
                threading.Thread(target=self._autofill_after_delay,
                                 args=(4.0,), daemon=True).start()

            if count >= self._max_players and not self._game_started:
                with self._lock:
                    self._game_started = True
                    sl = self._scores["LEFT"]
                    sr = self._scores["RIGHT"]
                self._broadcast_all("GAME_START")
                self._broadcast_all(f"SCORE {sl} {sr}")
                self._ball.start_game()
                print(f"[*] GAME_START — la partie commence ({self._mode})")

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
                if remaining < self._max_players:
                    self._game_started = False
                    self._fill_done    = False   # autoriser un nouveau fill
                    self._ball.stop_game()
            self._broadcast_all(f"SERVER {username} a quitté la partie")
            conn_obj.close()
            print(f"[-] {username} déconnecté  [{remaining}/{self._max_players}]")

    def _dispatch(self, line: str, role: str, username: str,
                  conn_obj: ClientConnection):
        """Traite un message reçu d'un client."""
        if line == "SERVE":
            with self._lock:
                pos = self._ball._positions.get(role, {})
            sx = pos.get("x", 370.0 if role.startswith("LEFT") else 1110.0)
            sy = pos.get("y", 300.0)
            self._ball.serve(role, sx, sy)

        elif line.startswith("POS"):
            parts = line.split()
            if len(parts) >= 3:
                self._ball.update_position(role, float(parts[1]), float(parts[2]))
            if len(parts) >= 6:
                self._broadcast_except(
                    f"{role}: POS {parts[1]} {parts[2]} {parts[3]} {parts[4]} {parts[5]}",
                    role
                )

        elif line.startswith("IMPULSE"):
            # Envoyer uniquement au joueur touché : le premier adversaire proche
            # (en pratique on broadcast à tous les adversaires, mais pas les coéquipiers)
            team = role.split("_")[0]
            self._broadcast_except_team(f"{role}: {line}", team)

        elif line == "FILL_AI":
            with self._lock:
                if self._fill_done or self._game_started:
                    return
                self._fill_done = True
            print(f"[FILL_AI] demandé par {username}")
            threading.Thread(target=self._fill_with_ai, daemon=True).start()

        else:
            print(f"[{username}] {line}")
            self._broadcast_except(f"{role}: {line}", role)

    def _autofill_after_delay(self, delay: float):
        """Attend `delay` secondes puis remplit les slots vides si la partie n'a pas démarré."""
        import time
        time.sleep(delay)
        with self._lock:
            started   = self._game_started
            count     = len(self._connections)
            already   = self._fill_done
            if not started and not already and count < self._max_players:
                self._fill_done = True   # verrouiller avant de sortir du lock
            else:
                return                   # un autre timer a déjà géré ça
        print(f"[AUTOFILL] {delay}s écoulées, {count}/{self._max_players} → remplissage IA")
        self._fill_with_ai()

    def _fill_with_ai(self):
        """Remplit les slots vides avec des bots IA (fonctionne en solo et en ligne)."""
        from .ai_client import AIClient
        with self._lock:
            taken      = set(self._connections.keys())
            empty_slots = [s for s in self._slots if s not in taken]

        for i, slot in enumerate(empty_slots):
            team = slot.split("_")[0] if "_" in slot else slot
            ai   = AIClient(role=team, username=f"BOT{i+1}")
            threading.Thread(target=ai.start, daemon=True).start()
            print(f"[FILL_AI] BOT{i+1} → équipe {team}")

    def _broadcast_except_team(self, msg: str, exclude_team: str):
        """Envoie un message uniquement aux joueurs d'une autre équipe."""
        with self._lock:
            for r, conn in self._connections.items():
                if r.split("_")[0] != exclude_team:
                    conn.send(msg)

    # ── Démarrage du serveur ──────────────────────────────────────────────────

    def run(self, host: str | None = None):
        """Lance l'écoute TCP ; bloque jusqu'à Ctrl+C ou fermeture du socket."""
        display_ip = _get_local_ip()
        # 0.0.0.0 : écoute sur toutes les interfaces (LAN + loopback)
        # Les bots peuvent ainsi se connecter via 127.0.0.1 même quand le
        # serveur est démarré sur une IP LAN.
        bind_host = host or "0.0.0.0"
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((bind_host, PORT))
        self._server_sock.listen()
        print(f"Serveur sur {display_ip}:{PORT}  mode={self._mode}  |  Ctrl+C pour arrêter\n")

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
