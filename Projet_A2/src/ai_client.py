"""
Client IA : se connecte au serveur en localhost et joue un rôle (LEFT, RIGHT, LEFT_1, etc.).
"""
import socket
import threading
import time
import math
import random

from .constants import PORT, VWIDTH, HEIGHT, MARGIN


def _team_of(role: str) -> str:
    return role.split("_")[0]


# Physique IA (identique aux constantes du moteur physique réel)
_ACCEL     = 300.0
_MAX_SPEED = 320.0   # un peu moins rapide que le joueur humain
_FRICTION  = 0.98


class AIClient:
    """IA basique qui essaie d'aller sur le cercle de chute qui lui est destiné."""

    def __init__(self, role: str = "RIGHT", username: str = "IA"):
        self._role     = role
        self._username = username
        self._team     = _team_of(role)

        # Position de départ selon l'équipe
        self._x  = VWIDTH * 3 / 4 if self._team == "RIGHT" else VWIDTH / 4
        self._y  = HEIGHT / 2
        self._vx = 0.0
        self._vy = 0.0
        self._angle = math.pi if self._team == "RIGHT" else 0.0

        # État balle (depuis messages serveur)
        self._ball_active   = False
        self._ball_progress = 0.0
        self._ball_bx       = 0.0
        self._ball_by       = 0.0
        self._ball_tx       = 0.0
        self._ball_ty       = 0.0
        self._ball_br       = 0.5   # bounce_ratio

        # Service
        self._my_serve      = False
        self._serve_delay   = 0.0

        self._sock    = None
        self._running = False
        self._buf     = ""
        self._lock    = threading.Lock()

    # ── Connexion ─────────────────────────────────────────────────────────────

    def start(self):
        """Bloque jusqu'à la connexion réussie, puis lance les threads."""
        for attempt in range(20):
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(2)
                self._sock.connect(("127.0.0.1", PORT))
                self._sock.settimeout(None)
                break
            except OSError:
                time.sleep(0.3)
        else:
            print("[AI] Impossible de se connecter au serveur")
            return

        self._running = True
        # Envoyer l'équipe souhaitée (LEFT ou RIGHT) ; le serveur attribue le slot
        self._send_raw(f"{self._username}|{self._team}\n")

        threading.Thread(target=self._recv_loop, daemon=True).start()
        threading.Thread(target=self._game_loop, daemon=True).start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    # ── Réception ─────────────────────────────────────────────────────────────

    def _recv_loop(self):
        while self._running:
            try:
                data = self._sock.recv(4096).decode("utf-8")
                if not data:
                    break
                self._buf += data
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._handle(line)
            except Exception:
                break

    def _handle(self, msg: str):
        content = msg.split(": ", 1)[1] if ": " in msg else msg
        parts   = content.split()
        if not parts:
            return

        cmd = parts[0]

        if cmd == "ROLE" and len(parts) >= 2:
            # Le serveur nous assigne le slot exact ; mettre à jour _role
            with self._lock:
                self._role = parts[1]
                self._team = _team_of(self._role)

        elif cmd == "BALL" and len(parts) >= 7:
            with self._lock:
                self._ball_active   = True
                self._ball_progress = float(parts[6])
                self._ball_tx       = float(parts[4])
                self._ball_ty       = float(parts[5])
                if len(parts) >= 10:
                    self._ball_bx = float(parts[7])
                    self._ball_by = float(parts[8])
                    self._ball_br = float(parts[9])

        elif cmd == "IMPULSE" and len(parts) >= 3:
            with self._lock:
                self._vx += float(parts[1])
                self._vy += float(parts[2])

        elif cmd in ("SCORE", "BOUNCE", "SERVING"):
            with self._lock:
                self._ball_active = False

        elif cmd == "SERVE_TURN" and len(parts) >= 2:
            # parts[1] est désormais une ÉQUIPE ("LEFT" ou "RIGHT")
            with self._lock:
                self._ball_active = False
                if parts[1] == self._team:
                    self._my_serve    = True
                    self._serve_delay = random.uniform(0.6, 1.4)

    # ── Boucle de jeu ─────────────────────────────────────────────────────────

    def _game_loop(self):
        """~30 fps : physique IA + envoi POS + service."""
        last_t = time.time()
        while self._running:
            time.sleep(1 / 30)
            now = time.time()
            dt  = now - last_t
            last_t = now

            # Service différé
            with self._lock:
                serve_now = False
                if self._my_serve and self._serve_delay > 0:
                    self._serve_delay -= dt
                    if self._serve_delay <= 0:
                        self._my_serve = False
                        serve_now = True

            if serve_now:
                self._send("SERVE")

            # Calcul de la cible
            tx, ty = self._choose_target()

            # Physique simple
            self._move_toward(tx, ty, dt)

            # Envoi position
            self._send(f"POS {self._x:.1f} {self._y:.1f} "
                       f"{self._angle:.4f} {self._vx:.2f} {self._vy:.2f}")

    def _choose_target(self) -> tuple[float, float]:
        """Retourne le point vers lequel l'IA doit se déplacer."""
        with self._lock:
            active   = self._ball_active
            progress = self._ball_progress
            br       = self._ball_br
            bx       = self._ball_bx
            by       = self._ball_by
            tx       = self._ball_tx
            ty       = self._ball_ty
            team     = self._team

        if not active:
            home_x = VWIDTH * 3 / 4 if team == "RIGHT" else VWIDTH / 4
            return home_x, HEIGHT / 2

        # Après le rebond → cible finale, sinon point de rebond
        if progress > br:
            target_x, target_y = tx, ty
        else:
            target_x, target_y = bx, by

        # La balle est-elle destinée à l'IA ?
        if team == "RIGHT":
            ball_for_me = target_x > VWIDTH / 2
        else:
            ball_for_me = target_x < VWIDTH / 2

        if ball_for_me:
            return target_x, target_y

        # Balle destinée à l'adversaire → recul vers son propre côté
        home_x = VWIDTH * 3 / 4 if team == "RIGHT" else VWIDTH / 4
        return home_x, HEIGHT / 2

    def _move_toward(self, tx: float, ty: float, dt: float):
        dx = tx - self._x
        dy = ty - self._y
        dist = math.hypot(dx, dy)

        if dist > 8:
            desired_angle = math.atan2(dy, dx)
            delta = (desired_angle - self._angle + math.pi) % (2 * math.pi) - math.pi
            self._angle += delta * min(1.0, 6 * dt)

            throttle = min(1.0, dist / 120)
            ax = _ACCEL * throttle * math.cos(self._angle)
            ay = _ACCEL * throttle * math.sin(self._angle)
        else:
            ax, ay = 0.0, 0.0
            self._vx *= 0.80
            self._vy *= 0.80

        self._vx = self._vx * _FRICTION + ax * dt
        self._vy = self._vy * _FRICTION + ay * dt

        speed = math.hypot(self._vx, self._vy)
        if speed > _MAX_SPEED:
            self._vx = self._vx / speed * _MAX_SPEED
            self._vy = self._vy / speed * _MAX_SPEED

        self._x += self._vx * dt
        self._y += self._vy * dt

        self._x = max(0.0, min(VWIDTH, self._x))
        self._y = max(0.0, min(HEIGHT, self._y))

    # ── Réseau ────────────────────────────────────────────────────────────────

    def _send(self, msg: str):
        self._send_raw(msg + "\n")

    def _send_raw(self, raw: str):
        try:
            self._sock.sendall(raw.encode("utf-8"))
        except Exception:
            pass
