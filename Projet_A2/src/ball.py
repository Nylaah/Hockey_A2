import pygame
from .constants import BALL_Z_MAX, BALL_RADIUS, BALL_MIN_SCALE


class Ball:
    """Balle côté client : reçoit son état du serveur et se dessine."""

    def __init__(self):
        self.x            = 0.0
        self.y            = 0.0
        self.z            = 0.0
        self.tx           = 0.0   # cible finale
        self.ty           = 0.0
        self.bx           = 0.0   # point de rebond
        self.by           = 0.0
        self.progress     = 0.0   # 0 = départ, 1 = impact final
        self.bounce_ratio = 0.55  # fraction du temps pour le 1er arc
        self.active       = False

    # ── Mise à jour ───────────────────────────────────────────────────────────

    def update_from_msg(self, parts: list[str]):
        # Format : BALL x y z tx ty progress [bx by bounce_ratio]
        self.x        = float(parts[1])
        self.y        = float(parts[2])
        self.z        = float(parts[3])
        self.tx       = float(parts[4])
        self.ty       = float(parts[5])
        self.progress = float(parts[6])
        if len(parts) >= 10:
            self.bx           = float(parts[7])
            self.by           = float(parts[8])
            self.bounce_ratio = float(parts[9])
        else:
            # Pas de rebond (ancien format)
            self.bx           = self.tx
            self.by           = self.ty
            self.bounce_ratio = 1.0   # jamais de 1er cercle
        self.active = True

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
        """
        Dessine deux cercles :
          - Cercle bleu clair : point de rebond (visible pendant le 1er arc)
          - Cercle jaune      : cible finale (toujours visible, rétrécit jusqu'à l'impact)
        """
        if not self.active:
            return

        MAX_R, MIN_R = 72, 14
        W = surface.get_width()

        # ── Cercle 1 : point de rebond (disparaît après le rebond) ──
        if self.progress < self.bounce_ratio:
            local_p = self.progress / self.bounce_ratio  # 0→1 dans la phase 1
            r1    = int(MAX_R - (MAX_R - MIN_R) * local_p)
            a1    = max(40, int(200 * (1 - local_p * 0.5)))
            sx1   = int(self.bx - cam_x)
            sy1   = int(self.by)
            if -MAX_R <= sx1 <= W + MAX_R:
                s = pygame.Surface((r1*2+4, r1*2+4), pygame.SRCALPHA)
                pygame.draw.circle(s, (160, 210, 255, a1), (r1+2, r1+2), r1, 3)
                surface.blit(s, (sx1 - r1 - 2, sy1 - r1 - 2))

        # ── Cercle 2 : cible finale (jaune, rétrécit de 0 à 1) ──
        r2  = int(MAX_R - (MAX_R - MIN_R) * self.progress)
        a2  = max(30, int(220 * (1 - self.progress * 0.6)))
        sx2 = int(self.tx - cam_x)
        sy2 = int(self.ty)
        if -MAX_R <= sx2 <= W + MAX_R:
            s = pygame.Surface((r2*2+4, r2*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 230, 0, a2), (r2+2, r2+2), r2, 3)
            surface.blit(s, (sx2 - r2 - 2, sy2 - r2 - 2))
