import pygame
import math
import socket
import threading
import time
import Physics as physics

PORT = 5000

# ── Dimensions de l'espace virtuel ──────────────────────────────────────────
# Image terrain : 740×444 px.  On l'étire à k × 740  par  HEIGHT pour garder
# un rapport entier (k=2) entre VWIDTH et la largeur originale de l'image.
IMG_ORIGINAL_W = 740
TERRAIN_SCALE  = 2                        # rapport entier souhaité
VWIDTH         = IMG_ORIGINAL_W * TERRAIN_SCALE   # = 1480 px

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

        leftover = []
        game_start_found = False
        for msg in msgs:
            if "GAME_START" in msg:
                game_start_found = True
            else:
                # Conserver tous les autres messages pour la boucle de jeu
                leftover.append(msg)

        if leftover:
            with incoming_lock:
                incoming[:0] = leftover   # réinsère en tête de file

        if game_start_found:
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

COLLISION_RADIUS = 45   # rayon de collision (px)
BALL_Z_MAX       = 220.0
BALL_RADIUS      = 13   # rayon au sol
BALL_MIN_SCALE   = 0.25 # taille minimale en hauteur de l'arc


# ─────────────────────────────────────────────
#  Rendu balle
# ─────────────────────────────────────────────

def draw_ball(screen, bx, by, bz, cam_x, HEIGHT):
    """Balle avec ombre au sol et réduction de taille à l'apogée."""
    sx = int(bx - cam_x)

    # Facteur d'échelle selon la hauteur
    t      = bz / BALL_Z_MAX if BALL_Z_MAX > 0 else 0
    scale  = 1.0 - (1.0 - BALL_MIN_SCALE) * t
    radius = max(2, int(BALL_RADIUS * scale))

    # Décalage vertical (la balle remonte visuellement)
    screen_y = int(by - bz * 0.45)

    # Ombre : ellipse sombre au sol, s'estompe en hauteur
    shadow_alpha = int(180 * (1 - t * 0.8))
    sr = max(3, int(BALL_RADIUS * 0.7))
    if -sr <= sx <= screen.get_width() + sr:
        shadow_surf = pygame.Surface((sr * 2, max(1, sr // 2 * 2)), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (0, 0, 0, shadow_alpha), shadow_surf.get_rect())
        screen.blit(shadow_surf, (sx - sr, int(by) - sr // 2))

    # Balle
    if -radius <= sx <= screen.get_width() + radius:
        pygame.draw.circle(screen, (255, 240, 80), (sx, screen_y), radius)
        if radius > 4:
            pygame.draw.circle(screen, (255, 255, 200),
                               (sx - radius // 3, screen_y - radius // 3),
                               max(1, radius // 3))


def draw_landing_circle(screen, tx, ty, progress, cam_x):
    """
    Cercle jaune qui rétrécit à mesure que la balle approche.
    progress : 0 = vient d'être lancée, 1 = impact.
    """
    MAX_R = 72
    MIN_R = 14
    r     = int(MAX_R - (MAX_R - MIN_R) * progress)
    alpha = max(30, int(220 * (1 - progress * 0.6)))
    sx    = int(tx - cam_x)
    sy    = int(ty)

    if -MAX_R <= sx <= screen.get_width() + MAX_R:
        surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 230, 0, alpha), (r + 2, r + 2), r, 3)
        screen.blit(surf, (sx - r - 2, sy - r - 2))


def screen_game(screen, clock, WIDTH, HEIGHT, sock, role,
                incoming, incoming_lock):
    """
    Espace virtuel : VWIDTH × HEIGHT.
    Caméra centrée sur le joueur local.
    Balle gérée par le serveur, rendue localement.
    """
    font_ui = pygame.font.SysFont("Arial", 18)

    # VWIDTH défini globalement (IMG_ORIGINAL_W * TERRAIN_SCALE)
    my_color    = COLOR_LEFT  if role == "LEFT"  else COLOR_RIGHT
    other_color = COLOR_RIGHT if role == "LEFT"  else COLOR_LEFT

    # ── Chargement du terrain ──
    # Étirement à VWIDTH × HEIGHT : rapport VWIDTH/IMG_ORIGINAL_W = TERRAIN_SCALE (entier)
    terrain_surf = None
    bg_color     = (30, 30, 30)   # fallback si pas de terrain
    try:
        import os
        terrain_path = os.path.join(os.path.dirname(__file__), "terrain.png")
        raw          = pygame.image.load(terrain_path).convert()
        terrain_surf = pygame.transform.scale(raw, (VWIDTH, HEIGHT))

        # ── Couleur de fond = moyenne des pixels de bordure du terrain ──
        # On lit directement sur l'image originale (plus rapide, pixels non étirés)
        pw, ph = raw.get_width(), raw.get_height()
        border_pixels = []
        step = 4   # on ne prend qu'1 pixel sur 4 pour aller vite
        for bx in range(0, pw, step):          # bord haut et bas
            border_pixels.append(raw.get_at((bx, 0))[:3])
            border_pixels.append(raw.get_at((bx, ph - 1))[:3])
        for by in range(0, ph, step):          # bord gauche et droit
            border_pixels.append(raw.get_at((0, by))[:3])
            border_pixels.append(raw.get_at((pw - 1, by))[:3])

        r = int(sum(p[0] for p in border_pixels) / len(border_pixels))
        g = int(sum(p[1] for p in border_pixels) / len(border_pixels))
        b = int(sum(p[2] for p in border_pixels) / len(border_pixels))
        bg_color = (r, g, b)
        print(f"[terrain] {pw}×{ph} → {VWIDTH}×{HEIGHT}  bg={bg_color}")
    except Exception as e:
        print(f"[terrain] impossible de charger terrain.png : {e}")

    x  = WIDTH / 4         if role == "LEFT" else WIDTH + WIDTH * 3 / 4
    y  = HEIGHT / 2
    vx, vy        = 0.0, 0.0
    # LEFT fait face à droite (angle 0), RIGHT fait face à gauche (angle π)
    angle_control = 0.0 if role == "LEFT" else math.pi

    other: dict        = {"x": None, "y": None, "angle": 0.0, "vx": 0.0, "vy": 0.0}
    send_timer         = 0.0
    hit_flash          = 0.0
    collision_cooldown = 0.0

    # ── État balle (reçu du serveur) ──
    ball            = None   # dict x y z tx ty progress, ou None
    score_left      = 0
    score_right     = 0
    my_serve        = False  # c'est mon tour de servir
    serve_sent      = False  # j'ai déjà envoyé SERVE ce tour

    def world_to_screen(wx, cam_x):
        return wx - cam_x

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        send_timer         += dt
        hit_flash           = max(0.0, hit_flash - dt)
        collision_cooldown  = max(0.0, collision_cooldown - dt)

        # ── Messages réseau ──
        with incoming_lock:
            msgs = incoming[:]
            incoming.clear()

        for msg in msgs:
            content = msg.split(": ", 1)[1] if ": " in msg else msg
            parts   = content.split()
            if not parts:
                continue

            # DEBUG — affiche tout sauf les POS (trop fréquents)
            if parts[0] != "POS":
                print(f"[CLIENT {role}] msg={content!r}  my_serve={my_serve}")

            if parts[0] == "POS" and len(parts) >= 6:
                other["x"]     = float(parts[1])
                other["y"]     = float(parts[2])
                other["angle"] = float(parts[3])
                other["vx"]    = float(parts[4])
                other["vy"]    = float(parts[5])

            elif parts[0] == "IMPULSE" and len(parts) >= 3:
                vx += float(parts[1])
                vy += float(parts[2])
                hit_flash          = 0.15
                collision_cooldown = 0.15

            elif parts[0] == "BALL" and len(parts) >= 7:
                ball = {
                    "x": float(parts[1]), "y": float(parts[2]),
                    "z": float(parts[3]),
                    "tx": float(parts[4]), "ty": float(parts[5]),
                    "progress": float(parts[6])
                }

            elif parts[0] == "SCORE" and len(parts) >= 3:
                score_left  = int(parts[1])
                score_right = int(parts[2])
                ball        = None   # balle remise à zéro

            elif parts[0] == "SERVE_TURN" and len(parts) >= 2:
                my_serve   = (parts[1] == role)
                serve_sent = False
                ball       = None

            elif parts[0] in ("SERVING", "BOUNCE"):
                my_serve = False   # la balle est en jeu

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

        # Servir la balle (espace)
        if keys[pygame.K_SPACE] and my_serve and not serve_sent:
            sock.sendall("SERVE\n".encode())
            serve_sent = True

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
        if other["x"] is not None and collision_cooldown <= 0:
            dist = math.hypot(x - other["x"], y - other["y"])
            if dist < COLLISION_RADIUS and dist > 0:
                # Normale de collision : de l'autre vers moi
                nx_c = (x - other["x"]) / dist
                ny_c = (y - other["y"]) / dist

                # Vitesse relative le long de la normale
                vrel_n = (vx - other["vx"]) * nx_c + (vy - other["vy"]) * ny_c

                if vrel_n < 0:   # on se rapproche
                    # e = 1.5 : super-élastique → le plus rapide repousse fort le plus lent
                    e = 1.5
                    j = -(1 + e) / 2 * vrel_n   # j > 0

                    # Ma propre réaction (je ralentis / rebondis)
                    vx += j * nx_c
                    vy += j * ny_c

                    # J'envoie l'impulsion opposée à l'autre joueur
                    # (il l'appliquera à sa propre vitesse dès réception)
                    sock.sendall(
                        f"IMPULSE {-j * nx_c:.4f} {-j * ny_c:.4f}\n".encode()
                    )

                    hit_flash          = 0.15
                    collision_cooldown = 0.15

                # Séparation pour éviter le chevauchement
                overlap = COLLISION_RADIUS - dist
                x += nx_c * overlap * 0.5
                y += ny_c * overlap * 0.5

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
        screen.fill(bg_color)

        # Terrain : bord gauche à virtual x=0, couvre tout le monde virtuel
        if terrain_surf is not None:
            screen.blit(terrain_surf, (int(world_to_screen(0, cam_x)), 0))

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

        # Cercle d'atterrissage (derrière les joueurs)
        if ball is not None:
            draw_landing_circle(screen, ball["tx"], ball["ty"],
                                ball["progress"], cam_x)

        draw_arrow(screen, world_to_screen(x, cam_x), y, angle_control, tri_color)

        if other["x"] is not None:
            draw_arrow(screen,
                       world_to_screen(other["x"], cam_x),
                       other["y"], other["angle"], other_color)

        # Balle (devant les joueurs)
        if ball is not None:
            draw_ball(screen, ball["x"], ball["y"], ball["z"], cam_x, HEIGHT)

        # ── HUD ──
        font_hud = pygame.font.SysFont("Arial", 22, bold=True)
        font_sm  = pygame.font.SysFont("Arial", 17)

        # Score
        score_txt = font_hud.render(
            f"{score_left}  —  {score_right}", True, (255, 255, 255))
        screen.blit(score_txt, (WIDTH // 2 - score_txt.get_width() // 2, 8))

        # Indication de service
        if my_serve and not serve_sent:
            serve_surf = font_hud.render("APPUIE SUR ESPACE POUR SERVIR",
                                         True, my_color)
            # Fond semi-transparent
            bg = pygame.Surface((serve_surf.get_width() + 20, serve_surf.get_height() + 8),
                                 pygame.SRCALPHA)
            bg.fill((0, 0, 0, 140))
            screen.blit(bg, (WIDTH // 2 - bg.get_width() // 2, HEIGHT // 2 - 24))
            screen.blit(serve_surf,
                        (WIDTH // 2 - serve_surf.get_width() // 2, HEIGHT // 2 - 20))

        # Légende vitesses
        my_speed    = math.hypot(vx, vy)
        other_speed = math.hypot(other["vx"], other["vy"])
        me_lbl  = font_sm.render(f"● Toi        {my_speed:5.0f} px/s", True, my_color)
        adv_lbl = font_sm.render(f"● Adversaire {other_speed:5.0f} px/s", True, other_color)
        screen.blit(me_lbl,  (10, HEIGHT - 46))
        screen.blit(adv_lbl, (10, HEIGHT - 26))

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
