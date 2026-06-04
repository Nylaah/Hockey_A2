import pygame
from .constants import BALL_Z_MAX, BALL_RADIUS, BALL_MIN_SCALE


class Ball:
    """Balle côté client : reçoit son état du serveur et se dessine."""

    def __init__(self):
        self.x        = 0.0
        self.y        = 0.0
        self.z        = 0.0   # hauteur au-dessus du sol
        self.tx       = 0.0   # cible (point d'atterrissage)
        self.ty       = 0.0
        self.progress = 0.0   # 0 = départ, 1 = impact
        self.active   = False

    # ── Mise à jour ───────────────────────────────────────────────────────────

    def update_from_msg(self, parts: list[str]):
        self.x        = float(parts[1])
        self.y        = float(parts[2])
        self.z        = float(parts[3])
        self.tx       = float(parts[4])
        self.ty       = float(parts[5])
        self.progress = float(parts[6])
        self.active   = True

    def deactivate(self):
        self.active = False

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, cam_x: float):
        """Dessine la balle avec ombre au sol et rétrécissement en hauteur."""
        if not self.active:
            return

        sx = int(self.x - cam_x)
        t  = self.z / BALL_Z_MAX if BALL_Z_MAX > 0 else 0.0

        # Taille selon la hauteur
        scale  = 1.0 - (1.0 - BALL_MIN_SCALE) * t
        radius = max(2, int(BALL_RADIUS * scale))

        # Position verticale à l'écran (monte visuellement)
        screen_y = int(self.y - self.z * 0.45)

        # Ombre au sol (ellipse)
        shadow_alpha = int(180 * (1 - t * 0.8))
        sr = max(3, int(BALL_RADIUS * 0.7))
        W  = surface.get_width()
        if -sr <= sx <= W + sr:
            shadow = pygame.Surface((sr * 2, max(1, sr // 2 * 2)), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, shadow_alpha), shadow.get_rect())
            surface.blit(shadow, (sx - sr, int(self.y) - sr // 2))

        # Balle jaune
        if -radius <= sx <= W + radius:
            pygame.draw.circle(surface, (255, 240, 80), (sx, screen_y), radius)
            if radius > 4:
                pygame.draw.circle(surface, (255, 255, 200),
                                   (sx - radius // 3, screen_y - radius // 3),
                                   max(1, radius // 3))

    def draw_landing_circle(self, surface: pygame.Surface, cam_x: float):
        """Cercle jaune qui rétrécit à mesure que la balle approche."""
        if not self.active:
            return

        MAX_R, MIN_R = 72, 14
        r     = int(MAX_R - (MAX_R - MIN_R) * self.progress)
        alpha = max(30, int(220 * (1 - self.progress * 0.6)))
        sx    = int(self.tx - cam_x)
        sy    = int(self.ty)

        if -MAX_R <= sx <= surface.get_width() + MAX_R:
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 230, 0, alpha), (r + 2, r + 2), r, 3)
            surface.blit(s, (sx - r - 2, sy - r - 2))
