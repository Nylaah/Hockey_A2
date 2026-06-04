import pygame
from .constants import BALL_Z_MAX, BALL_RADIUS, BALL_MIN_SCALE


class Ball:
    """Balle côté client : reçoit son état du serveur et se dessine."""

    def __init__(self):
        self.x             = 0.0
        self.y             = 0.0
        self.z             = 0.0
        self.tx            = 0.0
        self.ty            = 0.0
        self.bx            = 0.0   # rebond 1
        self.by            = 0.0
        self.bx2           = 0.0   # rebond 2
        self.by2           = 0.0
        self.progress      = 0.0
        self.bounce_ratio  = 0.30
        self.bounce2_ratio = 0.60
        self.active        = False

        self._bounce1_triggered = False
        self._bounce1_flash     = 0.0
        self._bounce2_triggered = False
        self._bounce2_flash     = 0.0

    # ── Mise à jour ───────────────────────────────────────────────────────────

    def update_from_msg(self, parts: list[str]):
        prev_progress  = self.progress
        self.x         = float(parts[1])
        self.y         = float(parts[2])
        self.z         = float(parts[3])
        self.tx        = float(parts[4])
        self.ty        = float(parts[5])
        self.progress  = float(parts[6])
        if len(parts) >= 10:
            self.bx           = float(parts[7])
            self.by           = float(parts[8])
            self.bounce_ratio = float(parts[9])
        else:
            self.bx = self.tx; self.by = self.ty; self.bounce_ratio = 1.0
        if len(parts) >= 13:
            self.bx2           = float(parts[10])
            self.by2           = float(parts[11])
            self.bounce2_ratio = float(parts[12])
        else:
            self.bx2 = self.tx; self.by2 = self.ty; self.bounce2_ratio = 1.0
        self.active = True

        if (not self._bounce1_triggered
                and prev_progress < self.bounce_ratio
                and self.progress >= self.bounce_ratio):
            self._bounce1_triggered = True
            self._bounce1_flash     = 0.5

        if (not self._bounce2_triggered
                and prev_progress < self.bounce2_ratio
                and self.progress >= self.bounce2_ratio):
            self._bounce2_triggered = True
            self._bounce2_flash     = 0.5

    def deactivate(self):
        self.active              = False
        self._bounce1_triggered  = False
        self._bounce1_flash      = 0.0
        self._bounce2_triggered  = False
        self._bounce2_flash      = 0.0

    def tick(self, dt: float):
        if self._bounce1_flash > 0:
            self._bounce1_flash = max(0.0, self._bounce1_flash - dt)
        if self._bounce2_flash > 0:
            self._bounce2_flash = max(0.0, self._bounce2_flash - dt)

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, cam_x: float):
        """Balle jaune avec ombre, rétrécissement en hauteur et effet de rebond."""
        if not self.active:
            return

        sx = int(self.x - cam_x)
        t  = self.z / BALL_Z_MAX if BALL_Z_MAX > 0 else 0.0

        # Taille selon la hauteur (plus grande à la base pour mieux voir)
        scale  = 1.0 - (1.0 - BALL_MIN_SCALE) * t
        radius = max(2, int(BALL_RADIUS * scale))

        # Décalage vertical : hauteur bien visible (facteur 0.6)
        screen_y = int(self.y - self.z * 0.6)

        W = surface.get_width()

        # ── Effets d'impact aux rebonds ──
        for flash, bx_pt, by_pt in (
            (self._bounce1_flash, self.bx,  self.by),
            (self._bounce2_flash, self.bx2, self.by2),
        ):
            if flash > 0:
                f   = flash / 0.5
                r_f = int(6 + (1 - f) * 30)
                a_f = int(220 * f)
                bsx = int(bx_pt - cam_x)
                bsy = int(by_pt)
                if -40 <= bsx <= W + 40:
                    fs = pygame.Surface((r_f*2+4, r_f*2+4), pygame.SRCALPHA)
                    pygame.draw.circle(fs, (255, 255, 255, a_f), (r_f+2, r_f+2), r_f, 3)
                    surface.blit(fs, (bsx - r_f - 2, bsy - r_f - 2))

        # ── Ombre au sol ──
        shadow_alpha = int(160 * (1 - t * 0.8))
        sr = max(3, int(BALL_RADIUS * 0.7))
        if -sr <= sx <= W + sr:
            shadow = pygame.Surface((sr * 2, max(1, sr // 2 * 2)), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, shadow_alpha), shadow.get_rect())
            surface.blit(shadow, (sx - sr, int(self.y) - sr // 2))

        # ── Balle ──
        if -radius <= sx <= W + radius:
            pygame.draw.circle(surface, (255, 240, 80), (sx, screen_y), radius)
            if radius > 4:
                pygame.draw.circle(surface, (255, 255, 200),
                                   (sx - radius // 3, screen_y - radius // 3),
                                   max(1, radius // 3))

    def draw_landing_circle(self, surface: pygame.Surface, cam_x: float):
        """
        Cercle bleu   → rebond 1  (pendant arc1).
        Cercle vert   → rebond 2  (pendant arc1 et arc2).
        Cercle jaune  → cible finale (toujours visible).
        """
        if not self.active:
            return

        MAX_R, MIN_R = 72, 14
        W = surface.get_width()

        def draw_ring(bx, by, color, local_p):
            r  = int(MAX_R - (MAX_R - MIN_R) * local_p)
            a  = max(40, int(200 * (1 - local_p * 0.5)))
            sx = int(bx - cam_x)
            if -MAX_R <= sx <= W + MAX_R:
                s = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
                pygame.draw.circle(s, (*color, a), (r+2, r+2), r, 3)
                surface.blit(s, (sx-r-2, int(by)-r-2))

        # Rebond 1 (bleu) : visible pendant arc1
        if self.progress < self.bounce_ratio:
            draw_ring(self.bx, self.by, (160, 210, 255),
                      self.progress / max(self.bounce_ratio, 1e-6))

        # Rebond 2 (vert) : visible pendant arc1 et arc2
        if self.progress < self.bounce2_ratio:
            span = self.bounce2_ratio - self.bounce_ratio
            if self.progress < self.bounce_ratio:
                local_p = self.progress / max(self.bounce2_ratio, 1e-6)
            else:
                local_p = (self.progress - self.bounce_ratio) / max(span, 1e-6)
            draw_ring(self.bx2, self.by2, (100, 255, 160), local_p)

        # Cible finale (jaune) : toujours visible
        draw_ring(self.tx, self.ty, (255, 230, 0), self.progress)
