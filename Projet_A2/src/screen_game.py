import pygame
import math
import os
from .constants import VWIDTH, HEIGHT, COLOR_LEFT, COLOR_RIGHT
from .player import Player, OtherPlayer
from .ball import Ball
from .network_client import NetworkClient


class GameScreen:
    """Boucle principale de jeu."""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 role: str, client: NetworkClient):
        self._screen = screen
        self._clock  = clock
        self._role   = role
        self._client = client
        self._W, self._H = screen.get_size()

        other_role    = "RIGHT" if role == "LEFT" else "LEFT"
        self._player  = Player(role)
        self._other   = OtherPlayer(other_role)
        self._ball    = Ball()

        self._score_left  = 0
        self._score_right = 0
        self._my_serve    = False
        self._serve_sent  = False
        self._send_timer  = 0.0

        # Polices créées une seule fois
        self._f_hud = pygame.font.SysFont("Arial", 22, bold=True)
        self._f_sm  = pygame.font.SysFont("Arial", 17)

        self._terrain_surf = None
        self._bg_color     = (30, 30, 30)
        self._load_terrain()

    # ── Terrain ───────────────────────────────────────────────────────────────

    def _load_terrain(self):
        try:
            root = os.path.dirname(os.path.dirname(__file__))
            raw  = pygame.image.load(os.path.join(root, "terrain.png")).convert()
            self._terrain_surf = pygame.transform.scale(raw, (VWIDTH, self._H))
            # Couleur de fond = moyenne des pixels de bordure
            pw, ph   = raw.get_width(), raw.get_height()
            pixels   = []
            step     = 4
            for bx in range(0, pw, step):
                pixels += [raw.get_at((bx, 0))[:3], raw.get_at((bx, ph-1))[:3]]
            for by in range(0, ph, step):
                pixels += [raw.get_at((0, by))[:3], raw.get_at((pw-1, by))[:3]]
            n = len(pixels)
            self._bg_color = (
                sum(p[0] for p in pixels) // n,
                sum(p[1] for p in pixels) // n,
                sum(p[2] for p in pixels) // n,
            )
        except Exception as e:
            print(f"[terrain] {e}")

    # ── Traitement des messages réseau ────────────────────────────────────────

    def _process(self, msgs: list[str]):
        for msg in msgs:
            content = msg.split(": ", 1)[1] if ": " in msg else msg
            parts   = content.split()
            if not parts:
                continue

            if parts[0] == "POS" and len(parts) >= 6:
                self._other.update_from_pos(parts)

            elif parts[0] == "IMPULSE" and len(parts) >= 3:
                self._player.apply_impulse(float(parts[1]), float(parts[2]))

            elif parts[0] == "BALL" and len(parts) >= 7:
                self._ball.update_from_msg(parts)

            elif parts[0] == "SCORE" and len(parts) >= 3:
                self._score_left  = int(parts[1])
                self._score_right = int(parts[2])
                self._ball.deactivate()

            elif parts[0] == "SERVE_TURN" and len(parts) >= 2:
                self._my_serve    = (parts[1] == self._role)
                self._serve_sent  = False
                self._ball.deactivate()
                print(f"[SERVE_TURN] {parts[1]} — c'est moi ? {self._my_serve}")

            elif parts[0] in ("SERVING", "BOUNCE"):
                self._my_serve = False

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _draw_world(self, cam_x: float):
        self._screen.fill(self._bg_color)
        if self._terrain_surf:
            self._screen.blit(self._terrain_surf, (int(-cam_x), 0))
        # Murs du monde virtuel
        for vx_wall in (0, VWIDTH):
            sx = int(vx_wall - cam_x)
            if 0 <= sx <= self._W:
                pygame.draw.line(self._screen, (100, 100, 120),
                                 (sx, 0), (sx, self._H), 3)

    def _draw_hud(self):
        W, H = self._W, self._H

        # Score centré en haut
        sc = self._f_hud.render(
            f"{self._score_left}  —  {self._score_right}", True, (255, 255, 255))
        self._screen.blit(sc, (W//2 - sc.get_width()//2, 8))

        # Invite de service
        if self._my_serve and not self._serve_sent:
            srv = self._f_hud.render(
                "APPUIE SUR ESPACE POUR SERVIR", True, self._player.color)
            bg = pygame.Surface((srv.get_width()+20, srv.get_height()+8),
                                pygame.SRCALPHA)
            bg.fill((0, 0, 0, 150))
            self._screen.blit(bg,  (W//2 - bg.get_width() //2, H//2 - 24))
            self._screen.blit(srv, (W//2 - srv.get_width()//2, H//2 - 20))

        # Vitesses
        me  = self._f_sm.render(
            f"● Toi        {self._player.speed:5.0f} px/s", True, self._player.color)
        adv = self._f_sm.render(
            f"● Adversaire {self._other.speed:5.0f} px/s",  True, self._other.color)
        self._screen.blit(me,  (10, H - 46))
        self._screen.blit(adv, (10, H - 26))

    # ── Boucle principale ─────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            dt = self._clock.tick(60) / 1000.0
            self._send_timer += dt

            # Messages réseau
            self._process(self._client.get_messages())

            # Événements
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            keys = pygame.key.get_pressed()

            # Service
            if keys[pygame.K_SPACE] and self._my_serve and not self._serve_sent:
                self._client.send("SERVE")
                self._serve_sent = True

            # Physique joueur
            self._player.update(dt, keys)
            self._player.check_collision(self._other, self._client)

            # Envoi de position (~30/s)
            if self._send_timer >= 1 / 30:
                self._client.send(self._player.pos_message())
                self._send_timer = 0.0

            # Caméra centrée sur le joueur local
            cam_x = self._player.x - self._W / 2

            # Rendu
            self._draw_world(cam_x)
            self._ball.draw_landing_circle(self._screen, cam_x)
            self._other.draw(self._screen, cam_x)
            self._player.draw(self._screen, cam_x)
            self._ball.draw(self._screen, cam_x)
            self._draw_hud()

            pygame.display.flip()
