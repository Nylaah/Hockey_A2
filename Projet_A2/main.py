import pygame
import math
import socket
import threading
import time
import Physics as physics

PORT = 5000

# Couleurs des joueurs
COLOR_LEFT  = (59,  130, 246)   # bleu  → joueur LEFT
COLOR_RIGHT = (239,  68,  68)   # rouge → joueur RIGHT


# ─────────────────────────────────────────────
#  Dessin du triangle (avec couleur)
# ─────────────────────────────────────────────

def draw_arrow(surface, x, y, angle, color):
    L, W = 40, 20
    px = x + L * math.cos(angle);      py = y + L * math.sin(angle)
    lx = x + W * math.cos(angle+2.5);  ly = y + W * math.sin(angle+2.5)
    rx = x + W * math.cos(angle-2.5);  ry = y + W * math.sin(angle-2.5)
    pygame.draw.polygon(surface, color, [(px, py), (lx, ly), (rx, ry)])


# ─────────────────────────────────────────────
#  Utilitaires réseau
# ─────────────────────────────────────────────

def make_receive_loop(sock, incoming, incoming_lock):
    """
    Lance un thread qui lit en continu le socket et met chaque ligne
    dans la file `incoming`. Retourne la fonction stop() pour l'arrêter.
    """
    def loop():
        buf = ""
        while True:
            try:
                data = sock.recv(4096).decode("utf-8")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        with incoming_lock:
                            incoming.append(line)
            except:
                break

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t


def wait_message(incoming, incoming_lock, timeout=10):
    """Attend et retourne le prochain message de la file (bloquant)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        with incoming_lock:
            if incoming:
                return incoming.pop(0)
        time.sleep(0.01)
    return None


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
        self.cursor_tick = 0.0

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
            self.cursor_tick = 0.0

    def draw(self, surface):
        col_border = (96, 165, 250) if self.active else (59, 100, 180)
        pygame.draw.rect(surface, (20, 35, 65),  self.rect, border_radius=8)
        pygame.draw.rect(surface, col_border,    self.rect, 2, border_radius=8)
        display = self.text + ("|" if self.active and self.cursor_vis else "")
        if display:
            surf = self.font.render(display, True, (255, 255, 255))
        else:
            surf = self.font.render(self.placeholder, True, (100, 120, 160))
        surface.blit(surf, (self.rect.x + 12,
                            self.rect.centery - surf.get_height() // 2))


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
            return self.rect.collidepoint(event.pos)
        return False

    def draw(self, surface):
        bg  = (37, 99, 235) if self.selected else (20, 35, 65)
        brd = (147, 197, 253) if self.selected else (59, 100, 180)
        pygame.draw.rect(surface, bg,  self.rect, border_radius=8)
        pygame.draw.rect(surface, brd, self.rect, 2, border_radius=8)
        txt = self.font.render(self.label, True, (255, 255, 255))
        surface.blit(txt, (self.rect.centerx - txt.get_width()  // 2,
                           self.rect.centery - txt.get_height() // 2))


# ─────────────────────────────────────────────
#  Écran MENU
# ─────────────────────────────────────────────

def screen_menu(screen, clock, WIDTH, HEIGHT):
    font_title = pygame.font.SysFont("Arial", 64, bold=True)
    font_label = pygame.font.SysFont("Arial", 18, bold=True)
    font_field = pygame.font.SysFont("Arial", 20)
    font_error = pygame.font.SysFont("Arial", 16)
    font_play  = pygame.font.SysFont("Arial", 22, bold=True)

    cx = WIDTH // 2

    input_user = TextInput(cx-160, 240, 320, 44, "Ton pseudo...",    font_field)
    input_ip   = TextInput(cx-160, 360, 320, 44, "IP du serveur...", font_field)
    input_ip.text = "10.30.43.9"

    btn_left  = Button(cx-170, 430, 150, 44, "◀  LEFT",  font_field, selected=True)
    btn_right = Button(cx+ 20, 430, 150, 44, "RIGHT  ▶", font_field, selected=False)
    btn_play  = Button(cx-100, 500, 200, 52, "PLAY", font_play)

    # Couleurs pour les boutons de côté
    btn_left_color  = COLOR_LEFT
    btn_right_color = COLOR_RIGHT

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

        screen.fill((10, 20, 40))

        title = font_title.render("PUCK MASTER", True, (255, 255, 255))
        sub   = font_label.render("RULE THE ICE", True, (147, 197, 253))
        screen.blit(title, (cx - title.get_width() // 2, 120))
        screen.blit(sub,   (cx - sub.get_width()   // 2, 195))

        for lbl_text, y_pos in [("PSEUDO", 220), ("IP DU SERVEUR", 340), ("CÔTÉ", 412)]:
            lbl = font_label.render(lbl_text, True, (147, 197, 253))
            screen.blit(lbl, (cx - 160, y_pos))

        input_user.draw(screen)
        input_ip.draw(screen)

        # Boutons de côté avec leur couleur de joueur
        for btn, color in [(btn_left, COLOR_LEFT), (btn_right, COLOR_RIGHT)]:
            bg  = (*color, 180) if btn.selected else (20, 35, 65)
            brd = color if btn.selected else (59, 100, 180)
            pygame.draw.rect(screen, color if btn.selected else (20, 35, 65),
                             btn.rect, border_radius=8)
            pygame.draw.rect(screen, color, btn.rect, 2, border_radius=8)
            txt = font_field.render(btn.label, True, (255, 255, 255))
            screen.blit(txt, (btn.rect.centerx - txt.get_width()  // 2,
                              btn.rect.centery - txt.get_height() // 2))

        btn_play.draw(screen)

        if error:
            err = font_error.render(error, True, (248, 113, 113))
            screen.blit(err, (cx - err.get_width() // 2, 478))

        pygame.display.flip()


# ─────────────────────────────────────────────
#  Écran ATTENTE
# ─────────────────────────────────────────────

def screen_wait(screen, clock, WIDTH, HEIGHT, username, role,
                incoming, incoming_lock):
    font_big   = pygame.font.SysFont("Arial", 40, bold=True)
    font_small = pygame.font.SysFont("Arial", 22)
    color = COLOR_LEFT if role == "LEFT" else COLOR_RIGHT

    dots = 0; dots_timer = 0.0; spin_angle = 0.0

    while True:
        dt = clock.tick(60) / 1000.0
        dots_timer += dt; spin_angle += dt * 120
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

        title = font_big.render("En attente d'un 2e joueur" + "." * dots,
                                True, (255, 255, 255))
        info = font_small.render(f"{username}  —  côté {role}", True, color)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//2 - 60))
        screen.blit(info,  (WIDTH//2 - info.get_width() //2, HEIGHT//2))

        # Spinner
        cx, cy, r = WIDTH//2, HEIGHT//2 + 70, 24
        for i in range(8):
            a  = math.radians(spin_angle + i * 45)
            c  = tuple(int(v * (i+1)/8) for v in color)
            pygame.draw.circle(screen, c,
                               (int(cx + r*math.cos(a)), int(cy + r*math.sin(a))), 5)

        pygame.display.flip()


# ─────────────────────────────────────────────
#  Boucle de JEU
# ─────────────────────────────────────────────

COLLISION_RADIUS = 45   # rayon de collision (px) — un peu plus grand que le triangle


def apply_collision(x1, y1, vx1, vy1, x2, y2, vx2, vy2):
    """
    Collision élastique en masse égale : retourne la nouvelle vitesse du joueur 1.
    Le plus rapide repousse fort le plus lent ; même vitesse → rebond symétrique.
    """
    dx   = x1 - x2
    dy   = y1 - y2
    dist = math.hypot(dx, dy)
    if dist == 0:
        return vx1, vy1

    # Normale de collision (de 2 vers 1)
    nx = dx / dist
    ny = dy / dist

    # Composantes de vitesse le long de la normale
    v1n = vx1 * nx + vy1 * ny
    v2n = vx2 * nx + vy2 * ny

    # Si les deux s'éloignent déjà, pas d'impulsion
    if v1n - v2n > 0:
        return vx1, vy1

    # Échange des composantes normales (collision élastique, masses égales)
    dvn = v2n - v1n                    # impulsion reçue
    new_vx1 = vx1 + dvn * nx
    new_vy1 = vy1 + dvn * ny
    return new_vx1, new_vy1


def screen_game(screen, clock, WIDTH, HEIGHT, sock, role,
                incoming, incoming_lock):
    """
    Espace virtuel : 2 × WIDTH de large, HEIGHT de haut.
    La caméra est centrée sur le triangle du joueur local.
    Chaque joueur contrôle toujours son propre triangle.
    Collision élastique locale basée sur la dernière vitesse connue de l'adversaire.
    """
    font_ui = pygame.font.SysFont("Arial", 18)

    VWIDTH = WIDTH * 2

    my_color    = COLOR_LEFT  if role == "LEFT"  else COLOR_RIGHT
    other_color = COLOR_RIGHT if role == "LEFT"  else COLOR_LEFT

    # ── Chargement et mise à l'échelle du terrain ──
    terrain_surf = None
    terrain_vx   = 0.0   # coordonnée virtuelle du bord gauche du terrain
    try:
        import os
        terrain_path = os.path.join(os.path.dirname(__file__), "terrain.png")
        raw = pygame.image.load(terrain_path).convert()
        # Mise à l'échelle : hauteur = HEIGHT, largeur proportionnelle
        scale        = HEIGHT / raw.get_height()
        t_w          = int(raw.get_width()  * scale)
        t_h          = HEIGHT
        terrain_surf = pygame.transform.scale(raw, (t_w, t_h))
        # On centre l'image sur la ligne virtuelle x = WIDTH
        terrain_vx   = WIDTH - t_w / 2
    except Exception as e:
        print(f"[terrain] impossible de charger terrain.png : {e}")

    x  = WIDTH / 4         if role == "LEFT" else WIDTH + WIDTH * 3 / 4
    y  = HEIGHT / 2
    vx, vy        = 150.0, 0.0
    angle_control = 0.0

    other: dict = {"x": None, "y": None, "angle": 0.0, "vx": 0.0, "vy": 0.0}
    send_timer  = 0.0

    # Flash visuel à la collision
    hit_flash   = 0.0   # secondes restantes de flash

    def world_to_screen(wx, cam_x):
        return wx - cam_x

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        send_timer += dt
        hit_flash   = max(0.0, hit_flash - dt)

        # ── Messages réseau ──
        with incoming_lock:
            msgs = incoming[:]
            incoming.clear()

        for msg in msgs:
            content = msg.split(": ", 1)[1] if ": " in msg else msg
            parts   = content.split()
            # Format : POS x y angle vx vy
            if len(parts) >= 6 and parts[0] == "POS":
                other["x"]     = float(parts[1])
                other["y"]     = float(parts[2])
                other["angle"] = float(parts[3])
                other["vx"]    = float(parts[4])
                other["vy"]    = float(parts[5])

        # ── Événements ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # ── Contrôles ──
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            angle_control -= physics.TURN_SPEED * dt
        if keys[pygame.K_RIGHT]:
            angle_control += physics.TURN_SPEED * dt

        x, y, vx, vy, _ = physics.update_physics(
            x, y, vx, vy, angle_control, bool(keys[pygame.K_UP]), dt
        )
        if keys[pygame.K_DOWN]:
            speed = math.hypot(vx, vy)
            if speed > 0:
                brake_strength = min(300 * dt, speed)  
                vx -= (vx / speed) * brake_strength
                vy -= (vy / speed) * brake_strength

        # ── Collision avec l'autre triangle ──
        if other["x"] is not None:
            dist = math.hypot(x - other["x"], y - other["y"])
            if dist < COLLISION_RADIUS:
                # Séparation : pousser mon triangle hors de la zone de collision
                if dist > 0:
                    overlap = COLLISION_RADIUS - dist
                    nx_sep  = (x - other["x"]) / dist
                    ny_sep  = (y - other["y"]) / dist
                    x += nx_sep * overlap * 0.5
                    y += ny_sep * overlap * 0.5

                # Impulsion élastique
                vx, vy = apply_collision(
                    x, y, vx, vy,
                    other["x"], other["y"], other["vx"], other["vy"]
                )
                hit_flash = 0.12   # flash blanc 120 ms

        # ── Rebonds sur les murs ──
        if x < 0:           x = 0.0;            vx =  abs(vx)
        elif x > VWIDTH:    x = float(VWIDTH);   vx = -abs(vx)
        if y < 0:           y = 0.0;            vy =  abs(vy)
        elif y > HEIGHT:    y = float(HEIGHT);   vy = -abs(vy)

        # ── Envoi de position + vitesse ~30×/s ──
        if send_timer >= 1 / 30:
            sock.sendall(f"POS {x} {y} {angle_control} {vx} {vy}\n".encode())
            send_timer = 0.0

        # ── Caméra ──
        cam_x = x - WIDTH / 2

        # ── Rendu ──
        screen.fill((30, 30, 30))

        # Terrain centré sur la ligne virtuelle x = WIDTH
        if terrain_surf is not None:
            screen.blit(terrain_surf, (int(world_to_screen(terrain_vx, cam_x)), 0))

        # Mur gauche
        lw = int(world_to_screen(0, cam_x))
        if 0 <= lw <= WIDTH:
            pygame.draw.line(screen, (100, 100, 120), (lw, 0), (lw, HEIGHT), 3)

        # Mur droit
        rw = int(world_to_screen(VWIDTH, cam_x))
        if 0 <= rw <= WIDTH:
            pygame.draw.line(screen, (100, 100, 120), (rw, 0), (rw, HEIGHT), 3)

        # Couleur de mon triangle (blanc pendant le flash de collision)
        tri_color = (255, 255, 255) if hit_flash > 0 else my_color

        draw_arrow(screen, world_to_screen(x, cam_x), y, angle_control, tri_color)

        if other["x"] is not None:
            draw_arrow(screen,
                       world_to_screen(other["x"], cam_x),
                       other["y"], other["angle"], other_color)

        # Légende + vitesses
        my_speed    = math.hypot(vx, vy)
        other_speed = math.hypot(other["vx"], other["vy"])
        me_lbl  = font_ui.render(f"● Toi        {my_speed:5.0f} px/s", True, my_color)
        adv_lbl = font_ui.render(f"● Adversaire {other_speed:5.0f} px/s", True, other_color)
        screen.blit(me_lbl,  (10, HEIGHT - 50))
        screen.blit(adv_lbl, (10, HEIGHT - 28))

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
    incoming      = []
    incoming_lock = threading.Lock()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((server_ip, PORT))
        sock.settimeout(None)

        # Thread réseau lancé AVANT l'envoi pour ne perdre aucune ligne
        make_receive_loop(sock, incoming, incoming_lock)

        # Envoie "username|ROLE_DESIRE" pour que le serveur respecte le choix
        sock.sendall(f"{username}|{role}\n".encode("utf-8"))

        response = wait_message(incoming, incoming_lock)
        if response is None or response.startswith("USERNAME_REFUSED"):
            raise ConnectionError(response or "Pas de réponse du serveur")

        role_msg      = wait_message(incoming, incoming_lock)
        assigned_role = role_msg.split()[1] if role_msg and role_msg.startswith("ROLE") else role

    except Exception as e:
        font = pygame.font.SysFont("Arial", 24)
        screen.fill((10, 20, 40))
        msg = font.render(f"Erreur de connexion : {e}", True, (248, 113, 113))
        screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2))
        pygame.display.flip()
        pygame.time.wait(4000)
        pygame.quit(); return

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
