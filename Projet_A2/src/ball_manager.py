import threading
import math
import random
import time
from .constants import (VWIDTH, HEIGHT, TOUCH_RADIUS,
                        BALL_TOUCH_Z, MARGIN, BALL_Z_MAX)


class _BallFlight:
    def __init__(self, sx, sy, tx, ty, T, from_role):
        self.sx = sx; self.sy = sy
        self.tx = tx; self.ty = ty
        self.T  = T;  self.t  = 0.0
        self.from_role = from_role
        self.x = sx; self.y = sy; self.z = 0.0

    def update(self, dt: float):
        self.t = min(self.t + dt, self.T)
        p      = self.t / self.T
        self.x = self.sx + (self.tx - self.sx) * p
        self.y = self.sy + (self.ty - self.sy) * p
        self.z = BALL_Z_MAX * math.sin(math.pi * p)

    @property
    def progress(self) -> float:
        return self.t / self.T if self.T > 0 else 1.0

    @property
    def done(self) -> bool:
        return self.t >= self.T


class BallManager:
    """
    Gère la physique de la balle côté serveur.
    Tourne dans son propre thread à ~30 fps.
    Communique via des callbacks (broadcast, on_score).
    Toutes les données partagées sont protégées par un Lock.
    Les broadcasts se font HORS du Lock pour éviter tout blocage.
    """

    def __init__(self, broadcast_fn, on_score_fn):
        self._broadcast  = broadcast_fn    # broadcast_fn(msg: str)
        self._on_score   = on_score_fn     # on_score_fn(scorer: str)

        self._lock        = threading.Lock()
        self._flight: _BallFlight | None = None
        self._last_touch: str | None     = None
        self._server_role: str           = "LEFT"
        self._positions: dict            = {}   # role → {x, y}
        self._game_on: bool              = False
        self._remind_t: float            = 0.0

        threading.Thread(target=self._loop, daemon=True).start()

    # ── API publique ──────────────────────────────────────────────────────────

    def start_game(self):
        with self._lock:
            self._game_on  = True
            self._remind_t = 0.0

    def stop_game(self):
        with self._lock:
            self._game_on = False
            self._flight  = None

    def update_position(self, role: str, x: float, y: float):
        with self._lock:
            self._positions[role] = {"x": x, "y": y}

    def serve(self, role: str, sx: float, sy: float) -> bool:
        """Lance la balle depuis (sx, sy). Retourne True si le service est valide."""
        with self._lock:
            if self._flight is not None or role != self._server_role:
                return False
            self._last_touch = role
            self._flight     = self._new_flight(role, sx, sy)
        self._broadcast(f"SERVING {role}")
        return True

    # ── Boucle interne ────────────────────────────────────────────────────────

    def _loop(self):
        last_t = time.time()
        while True:
            time.sleep(1 / 30)
            now = time.time()
            dt  = now - last_t
            last_t = now

            # ── Snapshot sous lock ──
            with self._lock:
                flight      = self._flight
                game_on     = self._game_on
                remind_t    = self._remind_t
                srv_role    = self._server_role
                positions   = dict(self._positions)
                last_touch  = self._last_touch

            # ── Pas de balle → rappel de service ──
            if flight is None:
                remind_t += dt
                if remind_t >= 1.0 and game_on:
                    self._broadcast(f"SERVE_TURN {srv_role}")
                    remind_t = 0.0
                    print(f"[REMIND] SERVE_TURN {srv_role}")
                with self._lock:
                    self._remind_t = remind_t
                continue

            # ── Mise à jour de la balle ──
            flight.update(dt)
            self._broadcast(
                f"BALL {flight.x:.1f} {flight.y:.1f} {flight.z:.1f} "
                f"{flight.tx:.1f} {flight.ty:.1f} {flight.progress:.3f}"
            )

            target = "RIGHT" if flight.from_role == "LEFT" else "LEFT"
            pos    = positions.get(target)
            near   = (pos is not None
                      and flight.z < BALL_TOUCH_Z
                      and math.hypot(pos["x"] - flight.tx,
                                     pos["y"] - flight.ty) < TOUCH_RADIUS)

            if near:
                if last_touch == target:
                    # Faute : même joueur deux fois → l'autre marque
                    other = "LEFT" if target == "RIGHT" else "RIGHT"
                    with self._lock:
                        self._flight      = None
                        self._last_touch  = None
                        self._server_role = other
                    self._on_score(other)
                else:
                    new_f = self._new_flight(target, flight.x, flight.y)
                    with self._lock:
                        self._last_touch = target
                        self._flight     = new_f
                    self._broadcast(f"BOUNCE {target}")
                    print(f"[BOUNCE] {target}")

            elif flight.done:
                scorer = flight.from_role
                with self._lock:
                    self._flight      = None
                    self._last_touch  = None
                    self._server_role = scorer
                self._on_score(scorer)

    # ── Utilitaires ───────────────────────────────────────────────────────────

    @staticmethod
    def _new_flight(from_role: str, sx: float, sy: float) -> _BallFlight:
        if from_role == "LEFT":
            tx = random.uniform(VWIDTH / 2 + MARGIN, VWIDTH - MARGIN)
        else:
            tx = random.uniform(MARGIN, VWIDTH / 2 - MARGIN)
        ty = random.uniform(MARGIN, HEIGHT - MARGIN)
        T  = random.uniform(1.3, 2.2)
        return _BallFlight(sx, sy, tx, ty, T, from_role)
