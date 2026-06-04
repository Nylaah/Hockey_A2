import pygame
import math
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import Physics as physics
from .constants import (VWIDTH, HEIGHT, COLLISION_RADIUS,
                        COLOR_LEFT, COLOR_RIGHT)


class Player:
    """Triangle contrôlé localement."""

    def __init__(self, role: str):
        self.role  = role
        self.color = COLOR_LEFT if role == "LEFT" else COLOR_RIGHT
        self.x     = VWIDTH / 4         if role == "LEFT" else VWIDTH * 3 / 4
        self.y     = HEIGHT / 2
        self.vx    = 0.0
        self.vy    = 0.0
        self.angle = 0.0 if role == "LEFT" else math.pi

        self.hit_flash          = 0.0
        self.collision_cooldown = 0.0

    # ── Mise à jour ───────────────────────────────────────────────────────────

    def update(self, dt: float, keys):
        self.hit_flash          = max(0.0, self.hit_flash - dt)
        self.collision_cooldown = max(0.0, self.collision_cooldown - dt)

        if keys[pygame.K_LEFT]:
            self.angle -= physics.TURN_SPEED * dt
        if keys[pygame.K_RIGHT]:
            self.angle += physics.TURN_SPEED * dt

        self.x, self.y, self.vx, self.vy, _ = physics.update_physics(
            self.x, self.y, self.vx, self.vy,
            self.angle, bool(keys[pygame.K_UP]), dt
        )

        if keys[pygame.K_DOWN]:
            speed = math.hypot(self.vx, self.vy)
            if speed > 0:
                brake   = min(300 * dt, speed)
                self.vx -= (self.vx / speed) * brake
                self.vy -= (self.vy / speed) * brake

        # Rebonds sur les murs du monde virtuel
        if self.x < 0:          self.x = 0.0;           self.vx =  abs(self.vx)
        elif self.x > VWIDTH:   self.x = float(VWIDTH);  self.vx = -abs(self.vx)
        if self.y < 0:          self.y = 0.0;           self.vy =  abs(self.vy)
        elif self.y > HEIGHT:   self.y = float(HEIGHT);  self.vy = -abs(self.vy)

    def check_collision(self, other: "OtherPlayer", client):
        """Détecte la collision avec l'adversaire et envoie l'impulsion."""
        if other.x is None or self.collision_cooldown > 0:
            return
        dist = math.hypot(self.x - other.x, self.y - other.y)
        if dist < COLLISION_RADIUS and dist > 0:
            nx = (self.x - other.x) / dist
            ny = (self.y - other.y) / dist
            vrel_n = (self.vx - other.vx) * nx + (self.vy - other.vy) * ny
            if vrel_n < 0:
                j = -(1 + 1.5) / 2 * vrel_n   # e = 1.5 super-élastique
                self.vx += j * nx
                self.vy += j * ny
                client.send(f"IMPULSE {-j*nx:.4f} {-j*ny:.4f}")
                self.hit_flash          = 0.15
                self.collision_cooldown = 0.15
            # Séparation
            overlap = COLLISION_RADIUS - dist
            self.x += nx * overlap * 0.5
            self.y += ny * overlap * 0.5

    def apply_impulse(self, dvx: float, dvy: float):
        self.vx += dvx
        self.vy += dvy
        self.hit_flash          = 0.15
        self.collision_cooldown = 0.15

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, cam_x: float):
        sx    = self.x - cam_x
        color = (255, 255, 255) if self.hit_flash > 0 else self.color
        L, W  = 40, 20
        px = sx + L * math.cos(self.angle);     py = self.y + L * math.sin(self.angle)
        lx = sx + W * math.cos(self.angle+2.5); ly = self.y + W * math.sin(self.angle+2.5)
        rx = sx + W * math.cos(self.angle-2.5); ry = self.y + W * math.sin(self.angle-2.5)
        pygame.draw.polygon(surface, color, [(px,py),(lx,ly),(rx,ry)])

    # ── Propriétés ────────────────────────────────────────────────────────────

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    def pos_message(self) -> str:
        return (f"POS {self.x:.1f} {self.y:.1f} "
                f"{self.angle:.4f} {self.vx:.2f} {self.vy:.2f}")


class OtherPlayer:
    """Triangle de l'adversaire, reconstruit depuis les messages réseau."""

    def __init__(self, role: str):
        self.role  = role
        self.color = COLOR_LEFT if role == "LEFT" else COLOR_RIGHT
        self.x: float | None = None
        self.y     = 0.0
        self.angle = 0.0
        self.vx    = 0.0
        self.vy    = 0.0

    def update_from_pos(self, parts: list[str]):
        self.x     = float(parts[1])
        self.y     = float(parts[2])
        self.angle = float(parts[3])
        self.vx    = float(parts[4])
        self.vy    = float(parts[5])

    def draw(self, surface: pygame.Surface, cam_x: float):
        if self.x is None:
            return
        sx = self.x - cam_x
        L, W = 40, 20
        px = sx + L * math.cos(self.angle);     py = self.y + L * math.sin(self.angle)
        lx = sx + W * math.cos(self.angle+2.5); ly = self.y + W * math.sin(self.angle+2.5)
        rx = sx + W * math.cos(self.angle-2.5); ry = self.y + W * math.sin(self.angle-2.5)
        pygame.draw.polygon(surface, self.color, [(px,py),(lx,ly),(rx,ry)])

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)
