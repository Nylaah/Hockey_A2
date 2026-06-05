import threading
import pygame
from .constants import WIDTH, HEIGHT, PORT, GAME_MODE_1V1, GAME_MODE_2V2
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
        ais    = []

        try:
            # ── Menu ──────────────────────────────────────────────────────────
            result = MenuScreen(screen, clock).run()
            if result is None:
                return
            username, team, server_ip, mode = result

            # ── Mode solo : serveur embarqué + IA(s) ──────────────────────────
            if server_ip == "solo":
                from .game_server import GameServer
                from .ai_client   import AIClient

                server = GameServer(mode=mode)
                threading.Thread(
                    target=server.run,
                    kwargs={"host": "127.0.0.1"},
                    daemon=True,
                ).start()

                if mode == GAME_MODE_1V1:
                    # 1 IA côté opposé
                    ai_team = "RIGHT" if team == "LEFT" else "LEFT"
                    ai = AIClient(role=ai_team, username="IA")
                    threading.Thread(target=ai.start, daemon=True).start()
                    ais.append(ai)
                else:
                    # 2v2 solo : 3 IA (RIGHT_1, RIGHT_2, LEFT_2 si humain = LEFT)
                    # On envoie l'équipe souhaitée ; le serveur attribue le slot
                    ai_configs = [
                        ("RIGHT", "IA-R1"),
                        ("RIGHT", "IA-R2"),
                        ("LEFT",  "IA-L2"),
                    ] if team == "LEFT" else [
                        ("LEFT",  "IA-L1"),
                        ("LEFT",  "IA-L2"),
                        ("RIGHT", "IA-R2"),
                    ]
                    for ai_team_req, ai_name in ai_configs:
                        ai = AIClient(role=ai_team_req, username=ai_name)
                        threading.Thread(target=ai.start, daemon=True).start()
                        ais.append(ai)

                server_ip = "127.0.0.1"

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

            # ── Attente des autres joueurs ─────────────────────────────────────
            max_players = 2 if mode == GAME_MODE_1V1 else 4
            if not WaitScreen(screen, clock, username, assigned_role, client,
                               mode=mode, max_players=max_players).run():
                return

            # ── Jeu ───────────────────────────────────────────────────────────
            GameScreen(screen, clock, assigned_role, client).run()

        finally:
            for ai in ais:
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
