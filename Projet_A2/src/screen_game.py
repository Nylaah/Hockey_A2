import pygame
import math
import os
import time
from .constants import VWIDTH, HEIGHT, COLOR_LEFT, COLOR_RIGHT
from .player import Player, OtherPlayer
from .ball import Ball
from .network_client import NetworkClient


def _team_of(role: str) -> str:
    return role.split("_")[0]


class GameScreen:
    """Boucle principale de jeu."""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 role: str, client: NetworkClient):
        self._screen = screen
        self._clock  = clock
        self._role   = role
        self._client = client
        self._W, self._H = screen.get_size()

        self._player  = Player(role)
        # _others : dict[str, OtherPlayer] keyed par rôle complet
        self._others: dict[str, OtherPlayer] = {}
        self._ball    = Ball()

        self._score_left  = 0
        self._score_right = 0
        self._my_serve    = False
        self._serve_sent  = False
        self._send_timer  = 0.0

        # Indicateur réseau
        self._last_msg_t  = time.time()
        self._avg_gap     = 0.033
        self._net_bars    = 4

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

    def _get_or_create_other(self, role: str) -> OtherPlayer:
        if role not in self._others:
            self._others[role] = OtherPlayer(role)
        return self._others[role]

    def _process(self, msgs: list[str]):
        for msg in msgs:
            # Format normal côté jeu : "ROLE: COMMAND ..." ou "COMMAND ..."
            if ": " in msg:
                prefix, content = msg.split(": ", 1)
            else:
                prefix, content = "", msg

            parts = content.split()
            if not parts:
                continue

            if parts[0] == "POS" and len(parts) >= 6:
                # prefix est le rôle (ex. "LEFT_1" ou "RIGHT")
                if prefix:
                    other = self._get_or_create_other(prefix)
                    other.update_from_pos(parts)

            elif parts[0] == "IMPULSE" and len(parts) >= 3:
                self._player.apply_impulse(float(parts[1]), float(parts[2]))

            elif parts[0] == "BALL" and len(parts) >= 7:
                if not self._ball.active:
                    print(f"[CLIENT] Première BALL reçue ({len(parts)} champs)")
                self._ball.update_from_msg(parts)
                now = time.time()
                gap = now - self._last_msg_t
                self._last_msg_t = now
                self._avg_gap = 0.85 * self._avg_gap + 0.15 * gap
                g_ms = self._avg_gap * 1000
                self._net_bars = (4 if g_ms < 50 else
                                  3 if g_ms < 110 else
                                  2 if g_ms < 200 else
                                  1 if g_ms < 400 else 0)

            elif parts[0] == "SCORE" and len(parts) >= 3:
                self._score_left  = int(parts[1])
                self._score_right = int(parts[2])
                self._ball.deactivate()

            elif parts[0] == "SERVE_TURN" and len(parts) >= 2:
                # parts[1] est désormais une ÉQUIPE ("LEFT" ou "RIGHT")
                self._my_serve   = (parts[1] == _team_of(self._role))
                self._serve_sent = False
                self._ball.deactivate()
                print(f"[SERVE_TURN] {parts[1]} — c'est moi ? {self._my_serve}")

            elif parts[0] in ("SERVING", "BOUNCE"):
                self._my_serve = False

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _draw_world(self, cam_x: float):
        self._screen.fill(self._bg_color)
        if self._terrain_surf:
            self._screen.blit(self._terrain_surf, (int(-cam_x), 0))
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

        # Vitesse du joueur local
        me = self._f_sm.render(
            f"● {self._role}  {self._player.speed:5.0f} px/s", True, self._player.color)
        self._screen.blit(me, (10, H - 26 - 20 * len(self._others)))

        # Vitesses des autres joueurs
        for i, (r, op) in enumerate(self._others.items()):
            adv = self._f_sm.render(
                f"● {r}  {op.speed:5.0f} px/s", True, op.color)
            self._screen.blit(adv, (10, H - 26 - 20 * (len(self._others) - 1 - i)))

        # Indicateur réseau (coin supérieur droit)
        self._draw_net_bars(W - 12, 10)

    def _draw_net_bars(self, right_x: int, top_y: int):
        NB    = 4
        W_BAR = 6
        GAP   = 3
        total_w = NB * W_BAR + (NB - 1) * GAP

        colors = {4: (74, 222, 128),
                  3: (163, 230, 53),
                  2: (250, 204, 21),
                  1: (251, 146, 60),
                  0: (248, 113, 113)}
        color_on  = colors.get(self._net_bars, (100, 100, 100))
        color_off = (50, 60, 80)

        x0 = right_x - total_w
        for i in range(NB):
            h   = 6 + i * 5
            bx  = x0 + i * (W_BAR + GAP)
            by  = top_y + (21 - h)
            col = color_on if i < self._net_bars else color_off
            pygame.draw.rect(self._screen, col,
                             pygame.Rect(bx, by, W_BAR, h), border_radius=2)

    # ── Boucle principale ─────────────────────────────────────────────────────

    def run(self):
        running = True
        while running:
            dt = self._clock.tick(60) / 1000.0
            self._send_timer += dt

            # Messages réseau
            self._process(self._client.get_messages())
            self._ball.tick(dt)

            # Événements
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            keys = pygame.key.get_pressed()

            # Service
            if keys[pygame.K_SPACE] and self._my_serve and not self._serve_sent:
                self._client.send("SERVE")
                self._serve_sent = True

            # Physique joueur + interpolation adversaires
            self._player.update(dt, keys)
            for op in self._others.values():
                op.tick(dt)
            self._player.check_collision(list(self._others.values()), self._client)

            # Envoi de position (~30/s)
            if self._send_timer >= 1 / 30:
                self._client.send(self._player.pos_message())
                self._send_timer = 0.0

            # Caméra centrée sur le joueur local
            cam_x = self._player.x - self._W / 2

            # Rendu
            self._draw_world(cam_x)
            self._ball.draw_landing_circle(self._screen, cam_x)
            for op in self._others.values():
                op.draw(self._screen, cam_x)
            self._player.draw(self._screen, cam_x)
            self._ball.draw(self._screen, cam_x)
            self._draw_hud()

            pygame.display.flip()
