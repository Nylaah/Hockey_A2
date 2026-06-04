import pygame


class TextInput:
    """Champ de saisie texte interactif."""

    def __init__(self, x: int, y: int, w: int, h: int,
                 placeholder: str = "", font: pygame.font.Font = None):
        self.rect        = pygame.Rect(x, y, w, h)
        self.placeholder = placeholder
        self.font        = font or pygame.font.SysFont("Arial", 20)
        self.text        = ""
        self.active      = False
        self._cursor_vis = True
        self._cursor_t   = 0.0

    def handle_event(self, event: pygame.event.Event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.unicode.isprintable():
                self.text += event.unicode

    def update(self, dt: float):
        self._cursor_t += dt
        if self._cursor_t >= 0.5:
            self._cursor_vis = not self._cursor_vis
            self._cursor_t   = 0.0

    def draw(self, surface: pygame.Surface):
        border = (96, 165, 250) if self.active else (59, 100, 180)
        pygame.draw.rect(surface, (20, 35, 65), self.rect, border_radius=8)
        pygame.draw.rect(surface, border,       self.rect, 2, border_radius=8)

        display = self.text + ("|" if self.active and self._cursor_vis else "")
        if display:
            surf = self.font.render(display, True, (255, 255, 255))
        else:
            surf = self.font.render(self.placeholder, True, (100, 120, 160))
        surface.blit(surf, (self.rect.x + 12,
                            self.rect.centery - surf.get_height() // 2))


class Button:
    """Bouton cliquable."""

    def __init__(self, x: int, y: int, w: int, h: int,
                 label: str, font: pygame.font.Font = None, selected: bool = False):
        self.rect     = pygame.Rect(x, y, w, h)
        self.label    = label
        self.font     = font or pygame.font.SysFont("Arial", 20)
        self.selected = selected

    @property
    def hovered(self) -> bool:
        return self.rect.collidepoint(pygame.mouse.get_pos())

    def handle_event(self, event: pygame.event.Event) -> bool:
        return (event.type == pygame.MOUSEBUTTONDOWN
                and self.rect.collidepoint(event.pos))

    def draw(self, surface: pygame.Surface, override_bg=None):
        bg  = override_bg or ((37, 99, 235) if self.selected else (20, 35, 65))
        brd = (147, 197, 253) if self.selected else (59, 100, 180)
        pygame.draw.rect(surface, bg,  self.rect, border_radius=8)
        pygame.draw.rect(surface, brd, self.rect, 2, border_radius=8)
        txt = self.font.render(self.label, True, (255, 255, 255))
        surface.blit(txt, (self.rect.centerx - txt.get_width()  // 2,
                           self.rect.centery - txt.get_height() // 2))
