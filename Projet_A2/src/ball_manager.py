import threading
import math
import random
import time
import traceback
from .constants import (VWIDTH, HEIGHT, TOUCH_RADIUS,
                        BALL_TOUCH_Z, MARGIN, BALL_Z_MAX)


def team_of(role: str) -> str:
    """Retourne l'équipe d'un rôle ('LEFT_1' → 'LEFT', 'RIGHT' → 'RIGHT')."""
    return role.split("_")[0]


class _BallFlight:
    """
    Trajectoire en 3 phases :
      arc1  (0 → BOUNCE)           départ → rebond
      dwell (BOUNCE → BOUNCE+DWELL) balle immobile au sol
      arc2  (BOUNCE+DWELL → 1)     rebond → cible finale
    """

    BOUNCE = 0.45
    DWELL  = 0.08

    def __init__(self, sx, sy, bx, by, tx, ty, T, from_role):
        self.sx = sx; self.sy = sy
        self.bx = bx; self.by = by
        self.tx = tx; self.ty = ty
        self.T  = T;  self.t  = 0.0
        self.from_role = from_role
        self.x = sx; self.y = sy; self.z = 0.0

    def update(self, dt: float):
        self.t  = min(self.t + dt, self.T)
        p       = self.t / self.T
        b       = self.BOUNCE
        d_end   = b + self.DWELL

        if p <= b:
            lp     = p / b
            self.x = self.sx + (self.bx - self.sx) * lp
            self.y = self.sy + (self.by - self.sy) * lp
            self.z = BALL_Z_MAX * math.sin(math.pi * lp)

        elif p <= d_end:
            self.x = self.bx
            self.y = self.by
            self.z = 0.0

        else:
            lp     = (p - d_end) / (1.0 - d_end)
            self.x = self.bx + (self.tx - self.bx) * lp
            self.y = self.by + (self.ty - self.by) * lp
            self.z = BALL_Z_MAX * 0.70 * math.sin(math.pi * lp)

    @property
    def progress(self) -> float:
        return self.t / self.T if self.T > 0 else 1.0

    @property
    def bounce_ratio(self) -> float:
        return self.BOUNCE

    @property
    def in_phase2(self) -> bool:
        return self.progress > self.BOUNCE + self.DWELL

    @property
    def touch_target(self) -> tuple[float, float]:
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
        self._server_team: str           = "LEFT"   # équipe dont c'est le service
        self._positions: dict            = {}        # role → {"x": float, "y": float}
        self._game_on: bool              = False
        self._remind_t: float            = 0.0

        threading.Thread(target=self._loop, daemon=True).start()

    # ── API publique ──────────────────────────────────────────────────────────

    def start_game(self):
        """Autorise la balle à être servie et remet à zéro le rappel de service."""
        with self._lock:
            self._game_on  = True
            self._remind_t = 0.0

    def stop_game(self):
        """Interrompt le jeu et supprime la balle en cours de vol."""
        with self._lock:
            self._game_on = False
            self._flight  = None

    def update_position(self, role: str, x: float, y: float):
        """Enregistre la dernière position connue d'un joueur (utilisée pour la détection de touche)."""
        with self._lock:
            self._positions[role] = {"x": x, "y": y}

    def serve(self, role: str, sx: float, sy: float) -> bool:
        with self._lock:
            if self._flight is not None:
                print(f"[SERVE] refusé — balle déjà en vol")
                return False
            if team_of(role) != self._server_team:
                print(f"[SERVE] refusé — équipe {team_of(role)} ≠ serveur ({self._server_team})")
                return False
            self._last_touch = role
            self._flight     = self._new_flight(role, sx, sy)
        print(f"[SERVE] {role} sert depuis ({sx:.0f}, {sy:.0f})")
        self._broadcast(f"SERVING {role}")
        return True

    # ── Boucle interne ────────────────────────────────────────────────────────

    def _loop(self):
        """Thread interne : appelle _tick() à ~30 fps indéfiniment."""
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
        """Avance la simulation d'un pas dt : déplace la balle, détecte les touches et les points."""
        # Snapshot sous lock
        with self._lock:
            flight      = self._flight
            game_on     = self._game_on
            remind_t    = self._remind_t
            srv_team    = self._server_team
            positions   = dict(self._positions)
            last_touch  = self._last_touch

        # Pas de balle : rappel de service
        if flight is None:
            remind_t += dt
            if remind_t >= 1.0 and game_on:
                self._broadcast(f"SERVE_TURN {srv_team}")
                remind_t = 0.0
                print(f"[REMIND] SERVE_TURN {srv_team}")
            with self._lock:
                self._remind_t = remind_t
            return

        # Mise à jour et broadcast
        flight.update(dt)
        self._broadcast(
            f"BALL {flight.x:.1f} {flight.y:.1f} {flight.z:.1f} "
            f"{flight.tx:.1f} {flight.ty:.1f} {flight.progress:.3f} "
            f"{flight.bx:.1f} {flight.by:.1f} {flight.bounce_ratio:.2f}"
        )

        from_team   = team_of(flight.from_role)
        target_team = "RIGHT" if from_team == "LEFT" else "LEFT"

        # Vérifie si un joueur de l'équipe cible touche la balle
        near = (
            flight.progress > flight.BOUNCE
            and flight.z < BALL_TOUCH_Z
            and any(
                math.hypot(pos["x"] - flight.x, pos["y"] - flight.y) < TOUCH_RADIUS
                for key, pos in positions.items()
                if team_of(key) == target_team
            )
        )

        if near:
            if last_touch is not None and team_of(last_touch) == target_team:
                # Double touche → point pour l'équipe adverse
                other_team = from_team
                with self._lock:
                    self._flight      = None
                    self._last_touch  = None
                    self._server_team = other_team
                self._on_score(other_team)
            else:
                # Touche valide → nouveau vol depuis la position actuelle
                toucher_role = next(
                    (k for k, pos in positions.items()
                     if team_of(k) == target_team
                     and math.hypot(pos["x"] - flight.x, pos["y"] - flight.y) < TOUCH_RADIUS),
                    target_team  # fallback
                )
                new_f = self._new_flight(toucher_role, flight.x, flight.y)
                with self._lock:
                    self._last_touch = toucher_role
                    self._flight     = new_f
                self._broadcast(f"BOUNCE {target_team}")
                print(f"[BOUNCE] {target_team}")

        elif flight.done:
            scorer_team = from_team
            with self._lock:
                self._flight      = None
                self._last_touch  = None
                self._server_team = scorer_team
            self._on_score(scorer_team)

    # ── Utilitaire ────────────────────────────────────────────────────────────

    @staticmethod
    def _new_flight(from_role: str, sx: float, sy: float) -> _BallFlight:
        from_team = team_of(from_role)
        if from_team == "LEFT":
            tx = random.uniform(VWIDTH / 2 + MARGIN, VWIDTH - MARGIN)
        else:
            tx = random.uniform(MARGIN, VWIDTH / 2 - MARGIN)
        ty = random.uniform(MARGIN, HEIGHT - MARGIN)

        frac = random.uniform(0.40, 0.60)
        bx   = sx + (tx - sx) * frac + random.uniform(-70, 70)
        by   = sy + (ty - sy) * frac + random.uniform(-70, 70)
        bx   = max(MARGIN // 2, min(VWIDTH - MARGIN // 2, bx))
        by   = max(MARGIN // 2, min(HEIGHT - MARGIN // 2, by))

        T = random.uniform(6.0, 8.5)   # balle lente
        return _BallFlight(sx, sy, bx, by, tx, ty, T, from_role)
