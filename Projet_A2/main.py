import pygame
import math
import socket
import threading
import argparse
import Physics as physics

PORT = 5000


# ─────────────────────────────────────────────
#  Utilitaires
# ─────────────────────────────────────────────

def draw_arrow(surface: pygame.Surface, x: float, y: float, angle: float) -> None:
    L, W = 40, 20
    px = x + L * math.cos(angle);  py = y + L * math.sin(angle)
    lx = x + W * math.cos(angle + 2.5); ly = y + W * math.sin(angle + 2.5)
    rx = x + W * math.cos(angle - 2.5); ry = y + W * math.sin(angle - 2.5)
    pygame.draw.polygon(surface, (255, 220, 0), [(px, py), (lx, ly), (rx, ry)])


def recv_line(sock: socket.socket) -> str:
    buf = ""
    while "\n" not in buf:
        chunk = sock.recv(1024).decode("utf-8")
        if not chunk:
            break
        buf += chunk
    return buf.split("\n")[0].strip()


# ─────────────────────────────────────────────
#  Champ de texte interactif
# ─────────────────────────────────────────────

class TextInput:
    def __init__(self, x, y, w, h, placeholder="", font=None):
        self.rect        = pygame.Rect(x, y, w, h)
        self.placeholder = placeholder
        self.font        = font or pygame.font.SysFont("Arial", 20)
        self.text        = ""
        self.active      = False
        self.cursor_vis  = True
        self.cursor_tick = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.unicode.isprintable():
                self.text += event.unicode

    def update(self, dt):
        self.cursor_tick += dt
        if self.cursor_tick >= 0.5:
            self.cursor_vis  = not self.cursor_vis
            self.cursor_tick = 0

    def draw(self, surface):
        # Fond
        col_border = (96, 165, 250) if self.active else (59, 100, 180)
        pygame.draw.rect(surface, (20, 35, 65), self.rect, border_radius=8)
        pygame.draw.rect(surface, col_border,   self.rect, 2, border_radius=8)

        display = self.text + ("|" if self.active and self.cursor_vis else "")
        if display:
            txt_surf = self.font.render(display, True, (255, 255, 255))
        else:
            txt_surf = self.font.render(self.placeholder, True, (100, 120, 160))

        surface.blit(txt_surf, (self.rect.x + 12, self.rect.y + self.rect.height // 2 - txt_surf.get_height() // 2))


# ─────────────────────────────────────────────
#  Bouton simple
# ─────────────────────────────────────────────

class Button:
    def __init__(self, x, y, w, h, label, font=None, selected=False):
        self.rect     = pygame.Rect(x, y, w, h)
        self.label    = label
        self.font     = font or pygame.font.SysFont("Arial", 20)
        self.selected = selected

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                return True
        return False

    def draw(self, surface):
        if self.selected:
            bg  = (37, 99, 235)
            brd = (147, 197, 253)
        else:
            bg  = (20, 35, 65)
            brd = (59, 100, 180)
        pygame.draw.rect(surface, bg,  self.rect, border_radius=8)
        pygame.draw.rect(surface, brd, self.rect, 2, border_radius=8)
        txt = self.font.render(self.label, True, (255, 255, 255))
        surface.blit(txt, (self.rect.centerx - txt.get_width() // 2,
                           self.rect.centery - txt.get_height() // 2))


# ─────────────────────────────────────────────
#  Écran MENU
# ─────────────────────────────────────────────

def screen_menu(screen, clock, WIDTH, HEIGHT):
    """Retourne (username, role, server_ip) ou None si l'utilisateur ferme."""
    font_title  = pygame.font.SysFont("Arial", 64, bold=True)
    font_label  = pygame.font.SysFont("Arial", 18, bold=True)
    font_field  = pygame.font.SysFont("Arial", 20)
    font_error  = pygame.font.SysFont("Arial", 16)

    cx = WIDTH // 2

    input_user = TextInput(cx - 160, 240, 320, 44, "Ton pseudo...", font_field)
    input_ip   = TextInput(cx - 160, 360, 320, 44, "IP du serveur...", font_field)
    input_ip.text = "10.30.43.9"

    btn_left  = Button(cx - 170, 430, 150, 44, "◀  LEFT",  font_field, selected=True)
    btn_right = Button(cx +  20, 430, 150, 44, "RIGHT  ▶", font_field, selected=False)
    btn_play  = Button(cx - 100, 500, 200, 52, "PLAY",     pygame.font.SysFont("Arial", 22, bold=True))

    role  = "LEFT"
    error = ""

    while True:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None

            input_user.handle_event(event)
            input_ip.handle_event(event)

            if btn_left.handle_event(event):
                role = "LEFT";  btn_left.selected = True;  btn_right.selected = False
            if btn_right.handle_event(event):
                role = "RIGHT"; btn_right.selected = True; btn_left.selected = False

            if btn_play.handle_event(event) or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
                if not input_user.text.strip():
                    error = "Merci d'entrer un pseudo."
                elif not input_ip.text.strip():
                    error = "Merci d'entrer l'IP du serveur."
                else:
                    return input_user.text.strip(), role, input_ip.text.strip()

        input_user.update(dt)
        input_ip.update(dt)

        # Fond
        screen.fill((10, 20, 40))
        for i in range(4):
            alpha_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(alpha_surf, (59, 130, 246, 8),
                               (int(0.2 * WIDTH), int(0.5 * HEIGHT)), 300 - i * 40)
            screen.blit(alpha_surf, (0, 0))

        # Titre
        title = font_title.render("PUCK MASTER", True, (255, 255, 255))
        sub   = font_label.render("RULE THE ICE", True, (147, 197, 253))
        screen.blit(title, (cx - title.get_width() // 2, 120))
        screen.blit(sub,   (cx - sub.get_width()   // 2, 195))

        # Labels
        lbl_user = font_label.render("PSEUDO", True, (147, 197, 253))
        lbl_ip   = font_label.render("IP DU SERVEUR", True, (147, 197, 253))
        lbl_side = font_label.render("CÔTÉ", True, (147, 197, 253))
        screen.blit(lbl_user, (cx - 160, 220))
        screen.blit(lbl_ip,   (cx - 160, 340))
        screen.blit(lbl_side, (cx - 160, 412))

        input_user.draw(screen)
        input_ip.draw(screen)
        btn_left.draw(screen)
        btn_right.draw(screen)
        btn_play.draw(screen)

        if error:
            err_txt = font_error.render(error, True, (248, 113, 113))
            screen.blit(err_txt, (cx - err_txt.get_width() // 2, 478))

        pygame.display.flip()


# ─────────────────────────────────────────────
#  Écran ATTENTE
# ─────────────────────────────────────────────

def screen_wait(screen, clock, WIDTH, HEIGHT, username, role, incoming, incoming_lock):
    """Attend GAME_START du serveur. Retourne False si l'utilisateur ferme."""
    font_big   = pygame.font.SysFont("Arial", 40, bold=True)
    font_small = pygame.font.SysFont("Arial", 22)

    dots = 0; dots_timer = 0.0; angle = 0.0

    while True:
        dt = clock.tick(60) / 1000.0
        dots_timer += dt; angle += dt * 120
        if dots_timer >= 0.5:
            dots = (dots + 1) % 4; dots_timer = 0

        with incoming_lock:
            msgs = incoming[:]
            incoming.clear()
        for msg in msgs:
            if "GAME_START" in msg:
                return True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

        screen.fill((10, 20, 40))

        title = font_big.render("En attente d'un 2e joueur" + "." * dots, True, (255, 255, 255))
        info  = font_small.render(f"{username}  —  {role}", True, (147, 197, 253))
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, HEIGHT // 2 - 60))
        screen.blit(info,  (WIDTH // 2 - info.get_width()  // 2, HEIGHT // 2))

        # Spinner
        cx, cy, r = WIDTH // 2, HEIGHT // 2 + 70, 24
        for i in range(8):
            a   = math.radians(angle + i * 45)
            alpha = int(255 * (i + 1) / 8)
            px  = int(cx + r * math.cos(a))
            py  = int(cy + r * math.sin(a))
            pygame.draw.circle(screen, (59, 130, 246, alpha), (px, py), 5)

        pygame.display.flip()


# ─────────────────────────────────────────────
#  Boucle de JEU
# ─────────────────────────────────────────────

def screen_game(screen, clock, WIDTH, HEIGHT, sock, role, incoming, incoming_lock):
    font_small = pygame.font.SysFont("Arial", 22)

    has_triangle = (role == "LEFT")
    x, y = WIDTH / 4, HEIGHT / 2
    vx, vy = 150.0, 0.0
    angle_control = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        with incoming_lock:
            msgs = incoming[:]
            incoming.clear()

        for msg in msgs:
            content = msg.split(": ", 1)[1] if ": " in msg else msg
            parts   = content.split()
            if not parts:
                continue
            if parts[0] == "TRANSFER" and not has_triangle:
                _, ty, tvx, tvy, tangle = parts
                y = float(ty); vx = float(tvx); vy = float(tvy)
                angle_control = float(tangle)
                x = 1.0 if role == "RIGHT" else WIDTH - 2.0
                has_triangle = True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        if has_triangle:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                angle_control -= physics.TURN_SPEED * dt
            if keys[pygame.K_RIGHT]:
                angle_control += physics.TURN_SPEED * dt

            x, y, vx, vy, _ = physics.update_physics(
                x, y, vx, vy, angle_control, bool(keys[pygame.K_UP]), dt
            )

            if role == "LEFT" and x > WIDTH:
                sock.sendall(f"TRANSFER {y} {vx} {vy} {angle_control}\n".encode())
                has_triangle = False
            elif role == "RIGHT" and x < 0:
                sock.sendall(f"TRANSFER {y} {vx} {vy} {angle_control}\n".encode())
                has_triangle = False
            elif role == "LEFT"  and x < 0:        x = 0.0;            vx =  abs(vx)
            elif role == "RIGHT" and x > WIDTH:     x = float(WIDTH-1); vx = -abs(vx)

            if y < 0:            y = 0.0;            vy =  abs(vy)
            elif y > HEIGHT:     y = float(HEIGHT-1); vy = -abs(vy)

        screen.fill((30, 30, 30))
        if has_triangle:
            draw_arrow(screen, x, y, angle_control)
        else:
            lbl = font_small.render("En attente du triangle...", True, (150, 150, 150))
            screen.blit(lbl, (WIDTH // 2 - lbl.get_width() // 2, HEIGHT // 2))
        pygame.display.flip()


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    pygame.init()
    WIDTH, HEIGHT = 900, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Puck Master")
    clock = pygame.time.Clock()

    # ── Menu ──
    result = screen_menu(screen, clock, WIDTH, HEIGHT)
    if result is None:
        pygame.quit(); return
    username, role, server_ip = result

    pygame.display.set_caption(f"Puck Master — {username} ({role})")

    # ── Connexion TCP ──
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((server_ip, PORT))
        sock.settimeout(None)
        sock.sendall(username.encode("utf-8"))

        response = recv_line(sock)
        if response.startswith("USERNAME_REFUSED"):
            print("Refusé :", response)
            pygame.quit(); return

        role_msg      = recv_line(sock)
        assigned_role = role_msg.split()[1] if role_msg.startswith("ROLE") else role

    except Exception as e:
        # Affiche l'erreur dans une fenêtre pygame simple
        font = pygame.font.SysFont("Arial", 24)
        screen.fill((10, 20, 40))
        msg = font.render(f"Erreur de connexion : {e}", True, (248, 113, 113))
        screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2))
        pygame.display.flip()
        pygame.time.wait(4000)
        pygame.quit(); return

    # ── Thread réseau ──
    incoming      = []
    incoming_lock = threading.Lock()

    def receive_loop():
        buf = ""
        while True:
            try:
                data = sock.recv(4096).decode("utf-8")
                if not data: break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        with incoming_lock:
                            incoming.append(line)
            except: break

    threading.Thread(target=receive_loop, daemon=True).start()

    # ── Attente du 2e joueur ──
    ok = screen_wait(screen, clock, WIDTH, HEIGHT, username, assigned_role,
                     incoming, incoming_lock)
    if not ok:
        pygame.quit(); sock.close(); return

    # ── Jeu ──
    screen_game(screen, clock, WIDTH, HEIGHT, sock, assigned_role,
                incoming, incoming_lock)

    pygame.quit()
    sock.close()


if __name__ == "__main__":
    main()
