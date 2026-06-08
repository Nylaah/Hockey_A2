import pygame
import math
from .constants import COLOR_LEFT, COLOR_RIGHT
from .network_client import NetworkClient
from .widgets import Button


class WaitScreen:
    """Écran d'attente affiché jusqu'à la réception de GAME_START."""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 username: str, role: str, client: NetworkClient,
                 mode: str = "1v1", max_players: int = 2, is_solo: bool = False):
        """Prépare l'écran d'attente avec les infos du joueur et le nombre de joueurs attendus."""
        self._screen      = screen
        self._clock       = clock
        self._username    = username
        self._role        = role
        self._client      = client
        self._mode        = mode
        self._max_players = max_players
        self._is_solo     = is_solo
        self._W, self._H  = screen.get_size()

    def run(self) -> bool:
        """Retourne True si le jeu démarre, False si l'utilisateur ferme."""
        f_big   = pygame.font.SysFont("Arial", 36, bold=True)
        f_small = pygame.font.SysFont("Arial", 20)
        f_btn   = pygame.font.SysFont("Arial", 18, bold=True)

        team  = self._role.split("_")[0]
        color = COLOR_LEFT if team == "LEFT" else COLOR_RIGHT

        W, H  = self._W, self._H
        btn_fill = Button(W // 2 - 120, H // 2 + 60, 240, 44,
                          "Remplir avec IA", f_btn)
        fill_sent = self._is_solo   # en solo c'est déjà envoyé

        dots = 0; dots_t = 0.0; spin = 0.0
        player_count = 1

        while True:
            dt = self._clock.tick(60) / 1000.0
            dots_t += dt; spin += dt * 120
            if dots_t >= 0.5:
                dots = (dots + 1) % 4; dots_t = 0.0

            msgs = self._client.get_messages()
            for i, msg in enumerate(msgs):
                if "GAME_START" in msg:
                    remainder = msgs[i + 1:]
                    if remainder:
                        self._client.put_back(remainder)
                    return True
                if "a rejoint" in msg:
                    player_count = min(player_count + 1, self._max_players)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                # Bouton visible uniquement en multi (solo déjà géré)
                if not fill_sent and btn_fill.handle_event(event):
                    self._client.send("FILL_AI")
                    fill_sent = True

            self._screen.fill((10, 20, 40))

            wait_text = (f"En attente  {player_count}/{self._max_players}" + "." * dots)
            title = f_big.render(wait_text, True, (255, 255, 255))
            info  = f_small.render(
                f"{self._username}  —  {self._role}  [{self._mode}]", True, color)
            self._screen.blit(title, (W // 2 - title.get_width() // 2, H // 2 - 80))
            self._screen.blit(info,  (W // 2 - info.get_width()  // 2, H // 2 - 30))

            # Bouton "Remplir avec IA" (en multi et pas encore envoyé)
            if not fill_sent:
                ai_color = (34, 197, 94)
                bg = ai_color if btn_fill.hovered else (10, 50, 25)
                pygame.draw.rect(self._screen, bg,       btn_fill.rect, border_radius=8)
                pygame.draw.rect(self._screen, ai_color, btn_fill.rect, 2, border_radius=8)
                txt = f_btn.render(btn_fill.label, True, (255, 255, 255))
                self._screen.blit(txt, (btn_fill.rect.centerx - txt.get_width()  // 2,
                                        btn_fill.rect.centery - txt.get_height() // 2))

            # Spinner
            cy_spin = H // 2 + (120 if not fill_sent else 60)
            for i in range(8):
                a = math.radians(spin + i * 45)
                c = tuple(int(v * (i + 1) / 8) for v in color)
                pygame.draw.circle(self._screen, c,
                                   (int(W // 2 + 24 * math.cos(a)),
                                    int(cy_spin + 24 * math.sin(a))), 5)

            pygame.display.flip()
