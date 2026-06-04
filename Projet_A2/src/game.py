import threading
import pygame
from .constants import WIDTH, HEIGHT, PORT
from .network_client import NetworkClient
from .screen_menu import MenuScreen
from .screen_wait import WaitScreen
from .screen_game import GameScreen


class Game:
    """Orchestrateur principal du client de jeu."""

    def run(self):
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Puck Master")
        clock  = pygame.time.Clock()
        client = NetworkClient()
        ai     = None

        try:
            # ── Menu ──────────────────────────────────────────────────────────
            result = MenuScreen(screen, clock).run()
            if result is None:
                return
            username, role, server_ip = result

            # ── Mode solo : serveur embarqué + IA ─────────────────────────────
            if server_ip == "solo":
                from .game_server import GameServer
                from .ai_client   import AIClient

                server = GameServer()
                threading.Thread(
                    target=server.run,
                    kwargs={"host": "127.0.0.1"},
                    daemon=True,
                ).start()

                ai_role = "RIGHT" if role == "LEFT" else "LEFT"
                ai = AIClient(role=ai_role, username="IA")
                threading.Thread(target=ai.start, daemon=True).start()

                server_ip = "127.0.0.1"

            # ── Connexion TCP ─────────────────────────────────────────────────
            pygame.display.set_caption(f"Puck Master — {username}")
            try:
                assigned_role = client.connect(server_ip, PORT, username, role)
            except Exception as e:
                self._show_error(screen, clock, f"Erreur de connexion : {e}")
                return

            if assigned_role is None:
                self._show_error(screen, clock, "Connexion refusée ou timeout.")
                return

            pygame.display.set_caption(f"Puck Master — {username} ({assigned_role})")

            # ── Attente du 2e joueur (sautée en solo car l'IA rejoint seule) ──
            if not WaitScreen(screen, clock, username, assigned_role, client).run():
                return

            # ── Jeu ───────────────────────────────────────────────────────────
            GameScreen(screen, clock, assigned_role, client).run()

        finally:
            if ai:
                ai.stop()
            client.disconnect()
            pygame.quit()

    @staticmethod
    def _show_error(screen: pygame.Surface, clock: pygame.time.Clock, msg: str):
        font = pygame.font.SysFont("Arial", 24)
        screen.fill((10, 20, 40))
        surf = font.render(msg, True, (248, 113, 113))
        screen.blit(surf, (screen.get_width()  // 2 - surf.get_width()  // 2,
                           screen.get_height() // 2 - surf.get_height() // 2))
        pygame.display.flip()
        pygame.time.wait(4000)
