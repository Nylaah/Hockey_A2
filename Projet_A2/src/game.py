import threading
import time
import pygame
from .constants import WIDTH, HEIGHT, PORT, GAME_MODE_1V1
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
        is_solo = False

        try:
            # ── Menu ──────────────────────────────────────────────────────────
            result = MenuScreen(screen, clock).run()
            if result is None:
                return
            username, team, server_ip, mode = result

            # ── Mode solo : serveur embarqué, les bots seront demandés via FILL_AI
            if server_ip == "solo":
                from .game_server import GameServer
                server = GameServer(mode=mode)
                threading.Thread(
                    target=server.run,
                    kwargs={"host": "127.0.0.1"},
                    daemon=True,
                ).start()
                time.sleep(0.25)   # laisser le serveur s'initialiser
                server_ip = "127.0.0.1"
                is_solo   = True

            # ── Connexion TCP ─────────────────────────────────────────────────
            pygame.display.set_caption(f"Puck Master — {username}")
            try:
                assigned_role = client.connect(server_ip, PORT, username, team)
            except Exception as e:
                self._show_error(screen, clock, f"Erreur de connexion : {e}")
                return

            if assigned_role is None:
                self._show_error(screen, clock, "Connexion refusée ou timeout.")
                return

            pygame.display.set_caption(f"Puck Master — {username} ({assigned_role})")

            # En solo, on remplit immédiatement les slots vides avec des bots
            if is_solo:
                client.send("FILL_AI")

            # ── Attente des autres joueurs ─────────────────────────────────────
            max_players = 2 if mode == GAME_MODE_1V1 else 4
            if not WaitScreen(screen, clock, username, assigned_role, client,
                               mode=mode, max_players=max_players,
                               is_solo=is_solo).run():
                return

            # ── Jeu ───────────────────────────────────────────────────────────
            GameScreen(screen, clock, assigned_role, client).run()

        finally:
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
