import pygame
import math
from .constants import COLOR_LEFT, COLOR_RIGHT
from .network_client import NetworkClient


class WaitScreen:
    """Écran d'attente affiché jusqu'à la réception de GAME_START."""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock,
                 username: str, role: str, client: NetworkClient,
                 mode: str = "1v1", max_players: int = 2):
        self._screen      = screen
        self._clock       = clock
        self._username    = username
        self._role        = role
        self._client      = client
        self._mode        = mode
        self._max_players = max_players
        self._W, self._H  = screen.get_size()

    def run(self) -> bool:
        """Retourne True si le jeu démarre, False si l'utilisateur ferme."""
        f_big   = pygame.font.SysFont("Arial", 36, bold=True)
        f_small = pygame.font.SysFont("Arial", 22)

        team  = self._role.split("_")[0]
        color = COLOR_LEFT if team == "LEFT" else COLOR_RIGHT

        dots = 0; dots_t = 0.0; spin = 0.0
        # Nombre de joueurs connectés connu (peut être mis à jour par messages)
        player_count = 1  # nous-même

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
                # Optionnel : compter les joueurs d'après les messages SERVER
                if msg.startswith("SERVER") and "a rejoint" in msg:
                    player_count = min(player_count + 1, self._max_players)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False

            W, H = self._W, self._H
            self._screen.fill((10, 20, 40))

            wait_text = (f"En attente des joueurs ({player_count}/{self._max_players})"
                         + "." * dots)
            title = f_big.render(wait_text, True, (255, 255, 255))
            info  = f_small.render(
                f"{self._username}  —  {self._role}  [{self._mode}]", True, color)
            self._screen.blit(title, (W//2 - title.get_width() // 2, H//2 - 60))
            self._screen.blit(info,  (W//2 - info.get_width()  // 2, H//2))

            # Spinner
            cx, cy, r = W // 2, H // 2 + 70, 24
            for i in range(8):
                a = math.radians(spin + i * 45)
                c = tuple(int(v * (i + 1) / 8) for v in color)
                pygame.draw.circle(self._screen, c,
                                   (int(cx + r * math.cos(a)),
                                    int(cy + r * math.sin(a))), 5)

            pygame.display.flip()
