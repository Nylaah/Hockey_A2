import threading
import math
import random
import time
import traceback
from .constants import (VWIDTH, HEIGHT, TOUCH_RADIUS,
                        BALL_TOUCH_Z, MARGIN, BALL_Z_MAX)


class _BallFlight:
    """
    Trajectoire en 5 phases :
      arc1   (0 → B1)           départ → rebond 1
      dwell1 (B1 → B1+D)        balle au sol au rebond 1
      arc2   (B1+D → B2)        rebond 1 → rebond 2
      dwell2 (B2 → B2+D)        balle au sol au rebond 2
      arc3   (B2+D → 1)         rebond 2 → cible finale
    """

    B1    = 0.28   # fin arc1
    DWELL = 0.05   # durée de chaque dwell
    B2    = 0.58   # fin arc2

    def __init__(self, sx, sy, bx, by, bx2, by2, tx, ty, T, from_role):
        self.sx = sx; self.sy = sy
        self.bx = bx; self.by = by
        self.bx2 = bx2; self.by2 = by2
        self.tx = tx; self.ty = ty
        self.T  = T;  self.t  = 0.0
        self.from_role = from_role
        self.x = sx; self.y = sy; self.z = 0.0

    def update(self, dt: float):
        self.t = min(self.t + dt, self.T)
        p      = self.t / self.T
        b1     = self.B1
        d1_end = b1 + self.DWELL
        b2     = self.B2
        d2_end = b2 + self.DWELL

        if p <= b1:
            lp     = p / b1
            self.x = self.sx + (self.bx - self.sx) * lp
            self.y = self.sy + (self.by - self.sy) * lp
            self.z = BALL_Z_MAX * math.sin(math.pi * lp)

        elif p <= d1_end:
            self.x = self.bx
            self.y = self.by
            self.z = 0.0

        elif p <= b2:
            lp     = (p - d1_end) / (b2 - d1_end)
            self.x = self.bx  + (self.bx2 - self.bx)  * lp
            self.y = self.by  + (self.by2 - self.by)  * lp
            self.z = BALL_Z_MAX * 0.72 * math.sin(math.pi * lp)

        elif p <= d2_end:
            self.x = self.bx2
            self.y = self.by2
            self.z = 0.0

        else:
            lp     = (p - d2_end) / (1.0 - d2_end)
            self.x = self.bx2 + (self.tx - self.bx2) * lp
            self.y = self.by2 + (self.ty - self.by2) * lp
            self.z = BALL_Z_MAX * 0.50 * math.sin(math.pi * lp)

    @property
    def progress(self) -> float:
        return self.t / self.T if self.T > 0 else 1.0

    @property
    def bounce_ratio(self) -> float:
        """Premier seuil de rebond envoyé au client."""
        return self.B1

    @property
    def bounce2_ratio(self) -> float:
        return self.B2

    @property
    def in_arc2(self) -> bool:
        p = self.progress
        return self.B1 + self.DWELL < p <= self.B2

    @property
    def in_arc3(self) -> bool:
        return self.progress > self.B2 + self.DWELL

    @property
    def in_touchable_phase(self) -> bool:
        return self.in_arc2 or self.in_arc3

    @property
    def touch_target(self) -> tuple[float, float]:
        """Point de chute courant (rebond 2 ou cible finale)."""
        if self.in_arc2:
            return self.bx2, self.by2
        return self.tx, self.ty

    @property
    def done(self) -> bool:
        return self.t >= self.T


class BallManager:
    """
    Physique de la balle côté serveur (~30 fps).
    Tous les broadcasts sont effectués HORS du Lock.
    """

    def __init__(self, broadcast_fn, on_score_fn):
        self._broadcast  = broadcast_fn
        self._on_score   = on_score_fn

        self._lock        = threading.Lock()
        self._flight: _BallFlight | None = None
        self._last_touch: str | None     = None
        self._server_role: str           = "LEFT"
        self._positions: dict            = {}
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
        with self._lock:
            if self._flight is not None:
                print(f"[SERVE] refusé — balle déjà en vol")
                return False
            if role != self._server_role:
                print(f"[SERVE] refusé — {role} ≠ serveur ({self._server_role})")
                return False
            self._last_touch = role
            self._flight     = self._new_flight(role, sx, sy)
        print(f"[SERVE] {role} sert depuis ({sx:.0f}, {sy:.0f})")
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
            try:
                self._tick(dt)
            except Exception:
                print("[BALL_LOOP ERREUR]")
                traceback.print_exc()

    def _tick(self, dt: float):
        # Snapshot sous lock
        with self._lock:
            flight     = self._flight
            game_on    = self._game_on
            remind_t   = self._remind_t
            srv_role   = self._server_role
            positions  = dict(self._positions)
            last_touch = self._last_touch

        # Pas de balle : rappel de service
        if flight is None:
            remind_t += dt
            if remind_t >= 1.0 and game_on:
                self._broadcast(f"SERVE_TURN {srv_role}")
                remind_t = 0.0
                print(f"[REMIND] SERVE_TURN {srv_role}")
            with self._lock:
                self._remind_t = remind_t
            return

        # Mise à jour et broadcast
        flight.update(dt)
        ttx, tty = flight.touch_target
        self._broadcast(
            f"BALL {flight.x:.1f} {flight.y:.1f} {flight.z:.1f} "
            f"{flight.tx:.1f} {flight.ty:.1f} {flight.progress:.3f} "
            f"{flight.bx:.1f} {flight.by:.1f} {flight.bounce_ratio:.2f} "
            f"{flight.bx2:.1f} {flight.by2:.1f} {flight.bounce2_ratio:.2f}"
        )

        target = "RIGHT" if flight.from_role == "LEFT" else "LEFT"
        pos    = positions.get(target)
        near   = (
            pos is not None
            and flight.in_touchable_phase
            and flight.z < BALL_TOUCH_Z
            and math.hypot(pos["x"] - ttx, pos["y"] - tty) < TOUCH_RADIUS
        )

        if near:
            if last_touch == target:
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

    # ── Utilitaire ────────────────────────────────────────────────────────────

    @staticmethod
    def _new_flight(from_role: str, sx: float, sy: float) -> _BallFlight:
        if from_role == "LEFT":
            tx = random.uniform(VWIDTH / 2 + MARGIN, VWIDTH - MARGIN)
        else:
            tx = random.uniform(MARGIN, VWIDTH / 2 - MARGIN)
        ty = random.uniform(MARGIN, HEIGHT - MARGIN)

        # Rebond 1 : entre départ et rebond 2
        f1   = random.uniform(0.25, 0.40)
        bx   = sx + (tx - sx) * f1 + random.uniform(-60, 60)
        by   = sy + (ty - sy) * f1 + random.uniform(-60, 60)
        bx   = max(MARGIN // 2, min(VWIDTH - MARGIN // 2, bx))
        by   = max(MARGIN // 2, min(HEIGHT - MARGIN // 2, by))

        # Rebond 2 : entre rebond 1 et cible finale
        f2   = random.uniform(0.55, 0.70)
        bx2  = bx + (tx - bx) * f2 + random.uniform(-50, 50)
        by2  = by + (ty - by) * f2 + random.uniform(-50, 50)
        bx2  = max(MARGIN // 2, min(VWIDTH - MARGIN // 2, bx2))
        by2  = max(MARGIN // 2, min(HEIGHT - MARGIN // 2, by2))

        T = random.uniform(3.5, 5.0)
        return _BallFlight(sx, sy, bx, by, bx2, by2, tx, ty, T, from_role)
