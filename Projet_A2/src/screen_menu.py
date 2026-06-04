import pygame
from .widgets import TextInput, Button
from .constants import COLOR_LEFT, COLOR_RIGHT


class MenuScreen:
    """Écran de menu : saisie du pseudo, IP et choix du côté."""

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self._screen = screen
        self._clock  = clock
        self._W, self._H = screen.get_size()

    def run(self) -> tuple[str, str, str] | None:
        """Retourne (username, role, server_ip) ou None si fermeture."""
        W, H, cx = self._W, self._H, self._W // 2

        f_title = pygame.font.SysFont("Arial", 64, bold=True)
        f_label = pygame.font.SysFont("Arial", 18, bold=True)
        f_field = pygame.font.SysFont("Arial", 20)
        f_error = pygame.font.SysFont("Arial", 16)
        f_play  = pygame.font.SysFont("Arial", 22, bold=True)

        inp_user = TextInput(cx-160, 240, 320, 44, "Ton pseudo...",    f_field)
        inp_ip   = TextInput(cx-160, 360, 320, 44, "IP du serveur...", f_field)
        inp_ip.text = "10.30.43.9"

        btn_left  = Button(cx-170, 430, 150, 44, "◀  LEFT",  f_field, selected=True)
        btn_right = Button(cx+ 20, 430, 150, 44, "RIGHT  ▶", f_field)
        btn_play  = Button(cx-100, 500, 200, 52, "PLAY",     f_play)

        role  = "LEFT"
        error = ""

        while True:
            dt = self._clock.tick(60) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                inp_user.handle_event(event)
                inp_ip.handle_event(event)

                if btn_left.handle_event(event):
                    role = "LEFT";  btn_left.selected = True;  btn_right.selected = False
                if btn_right.handle_event(event):
                    role = "RIGHT"; btn_right.selected = True; btn_left.selected = False

                if btn_play.handle_event(event) or (
                        event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
                    if not inp_user.text.strip():
                        error = "Merci d'entrer un pseudo."
                    elif not inp_ip.text.strip():
                        error = "Merci d'entrer l'IP du serveur."
                    else:
                        return inp_user.text.strip(), role, inp_ip.text.strip()

            inp_user.update(dt)
            inp_ip.update(dt)

            self._screen.fill((10, 20, 40))

            title = f_title.render("PUCK MASTER", True, (255, 255, 255))
            sub   = f_label.render("RULE THE ICE", True, (147, 197, 253))
            self._screen.blit(title, (cx - title.get_width() // 2, 120))
            self._screen.blit(sub,   (cx - sub.get_width()   // 2, 195))

            for text, y in [("PSEUDO", 220), ("IP DU SERVEUR", 340), ("CÔTÉ", 412)]:
                lbl = f_label.render(text, True, (147, 197, 253))
                self._screen.blit(lbl, (cx - 160, y))

            inp_user.draw(self._screen)
            inp_ip.draw(self._screen)

            # Boutons côté avec leur couleur de joueur
            for btn, color in [(btn_left, COLOR_LEFT), (btn_right, COLOR_RIGHT)]:
                bg = color if btn.selected else (20, 35, 65)
                pygame.draw.rect(self._screen, bg,    btn.rect, border_radius=8)
                pygame.draw.rect(self._screen, color, btn.rect, 2, border_radius=8)
                txt = f_field.render(btn.label, True, (255, 255, 255))
                self._screen.blit(txt, (btn.rect.centerx - txt.get_width()  // 2,
                                        btn.rect.centery - txt.get_height() // 2))

            btn_play.draw(self._screen)

            if error:
                err = f_error.render(error, True, (248, 113, 113))
                self._screen.blit(err, (cx - err.get_width() // 2, 478))

            pygame.display.flip()
