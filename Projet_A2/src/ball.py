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
        self.progress     = 0.0
        self.bounce_ratio = 0.55
        self.active       = False

        # Effet d'impact au rebond
        self._bounce_triggered = False   # True dès qu'on passe bounce_ratio
        self._bounce_flash     = 0.0     # timer décroissant 0.5→0

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
            self.bx           = self.tx
            self.by           = self.ty
            self.bounce_ratio = 1.0
        self.active = True

        # Détecter le passage au 2ème arc → déclencher l'effet d'impact
        if (not self._bounce_triggered
                and prev_progress < self.bounce_ratio
                and self.progress >= self.bounce_ratio):
            self._bounce_triggered = True
            self._bounce_flash     = 0.5   # 500 ms d'animation

    def deactivate(self):
        self.active             = False
        self._bounce_triggered  = False
        self._bounce_flash      = 0.0

    def tick(self, dt: float):
        """Faire évoluer les timers locaux (appelé chaque frame)."""
        if self._bounce_flash > 0:
            self._bounce_flash = max(0.0, self._bounce_flash - dt)

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

        # ── Effet d'impact au rebond : anneau blanc qui s'agrandit ──
        if self._bounce_flash > 0:
            f    = self._bounce_flash / 0.5        # 1→0
            r_f  = int(6 + (1 - f) * 30)          # grandit de 6 à 36 px
            a_f  = int(220 * f)                    # s'efface
            bsx  = int(self.bx - cam_x)
            bsy  = int(self.by)
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
        Cercle bleu  → point de rebond (visible pendant le 1er arc).
        Cercle jaune → cible finale   (toujours visible, rétrécit jusqu'à l'impact).
        """
        if not self.active:
            return

        MAX_R, MIN_R = 72, 14
        W = surface.get_width()

        # Cercle 1 : rebond (bleu clair)
        if self.progress < self.bounce_ratio:
            local_p = self.progress / self.bounce_ratio
            r1  = int(MAX_R - (MAX_R - MIN_R) * local_p)
            a1  = max(40, int(200 * (1 - local_p * 0.5)))
            sx1 = int(self.bx - cam_x)
            if -MAX_R <= sx1 <= W + MAX_R:
                s = pygame.Surface((r1*2+4, r1*2+4), pygame.SRCALPHA)
                pygame.draw.circle(s, (160, 210, 255, a1), (r1+2, r1+2), r1, 3)
                surface.blit(s, (sx1-r1-2, int(self.by)-r1-2))

        # Cercle 2 : cible finale (jaune)
        r2  = int(MAX_R - (MAX_R - MIN_R) * self.progress)
        a2  = max(30, int(220 * (1 - self.progress * 0.6)))
        sx2 = int(self.tx - cam_x)
        if -MAX_R <= sx2 <= W + MAX_R:
            s = pygame.Surface((r2*2+4, r2*2+4), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 230, 0, a2), (r2+2, r2+2), r2, 3)
            surface.blit(s, (sx2-r2-2, int(self.ty)-r2-2))
