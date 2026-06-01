import pygame
import math
import socket
import threading
import Physics as physics

SERVER_IP = "10.30.43.9"
PORT = 5000


def draw_arrow(surface: pygame.Surface, x: float, y: float, angle: float) -> None:
    L, W = 40, 20
    px = x + L * math.cos(angle); py = y + L * math.sin(angle)
    lx = x + W * math.cos(angle + 2.5); ly = y + W * math.sin(angle + 2.5)
    rx = x + W * math.cos(angle - 2.5); ry = y + W * math.sin(angle - 2.5)
    pygame.draw.polygon(surface, (255, 220, 0), [(px, py), (lx, ly), (rx, ry)])


def main():
    # --- CONNEXION RÉSEAU
    username = input("Pseudo : ").strip()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_IP, PORT))
    sock.sendall(username.encode("utf-8"))

    response = recv_line(sock)
    if response.startswith("USERNAME_REFUSED"):
        print("Connexion refusée :", response)
        return

    role_msg = recv_line(sock)   # "ROLE LEFT" ou "ROLE RIGHT"
    role = role_msg.split()[1]
    print(f"Connecté en tant que {username} — rôle : {role}")

    # --- FILE DES MESSAGES ENTRANTS (thread réseau → boucle principale)
    incoming = []
    incoming_lock = threading.Lock()

    def receive_loop():
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

    threading.Thread(target=receive_loop, daemon=True).start()

    # --- PYGAME
    pygame.init()
    WIDTH, HEIGHT = 900, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(f"Simulation — {role}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 36)

    # Le client LEFT démarre avec le triangle
    has_triangle = (role == "LEFT")
    x, y = WIDTH / 4, HEIGHT / 2
    vx, vy = 150.0, 0.0
    angle_control = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        # --- MESSAGES RÉSEAU
        with incoming_lock:
            msgs = incoming[:]
            incoming.clear()

        for msg in msgs:
            # Le serveur préfixe chaque message avec "username: "
            content = msg.split(": ", 1)[1] if ": " in msg else msg
            parts = content.split()
            if not parts:
                continue

            if parts[0] == "TRANSFER" and not has_triangle:
                # TRANSFER y vx vy angle_control
                _, ty, tvx, tvy, tangle = parts
                y             = float(ty)
                vx            = float(tvx)
                vy            = float(tvy)
                angle_control = float(tangle)
                x = 1.0 if role == "RIGHT" else WIDTH - 2.0
                has_triangle = True

        # --- ÉVÉNEMENTS
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # --- CONTRÔLE ET PHYSIQUE
        if has_triangle:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                angle_control -= physics.TURN_SPEED * dt
            if keys[pygame.K_RIGHT]:
                angle_control += physics.TURN_SPEED * dt

            x, y, vx, vy, _ = physics.update_physics(
                x, y, vx, vy, angle_control, bool(keys[pygame.K_UP]), dt
            )

            # Bords haut/bas : wrap local
            y = y % HEIGHT

            # Bord de passage inter-écrans
            if role == "LEFT" and x > WIDTH:
                sock.sendall(f"TRANSFER {y} {vx} {vy} {angle_control}\n".encode())
                has_triangle = False

            elif role == "RIGHT" and x < 0:
                sock.sendall(f"TRANSFER {y} {vx} {vy} {angle_control}\n".encode())
                has_triangle = False

            # Bord opposé : rebond (le triangle reste sur son écran)
            elif role == "LEFT" and x < 0:
                x = 0.0
                vx = abs(vx)
            elif role == "RIGHT" and x > WIDTH:
                x = float(WIDTH - 1)
                vx = -abs(vx)

        # --- RENDU
        screen.fill((30, 30, 30))
        if has_triangle:
            draw_arrow(screen, x, y, angle_control)
        else:
            label = font.render("En attente du triangle...", True, (150, 150, 150))
            screen.blit(label, (WIDTH // 2 - label.get_width() // 2, HEIGHT // 2))
        pygame.display.flip()

    pygame.quit()
    sock.close()


def recv_line(sock: socket.socket) -> str:
    """Lit une ligne complète (terminée par \\n) depuis le socket."""
    buf = ""
    while "\n" not in buf:
        chunk = sock.recv(1024).decode("utf-8")
        if not chunk:
            break
        buf += chunk
    return buf.split("\n")[0].strip()


if __name__ == "__main__":
    main()
