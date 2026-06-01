import math
from Physics import *
import Physics as physics

assert limite_speed(100, 0, 50) == (50.0, 0.0)
assert limite_speed(0, 0, 50) == (0.0, 0.0)
assert limite_speed(30, 40, 50) == (30.0, 40.0)  # norme = 50, rien ne change



assert angle_from_velocity(1, 0) == 0
assert math.isclose(angle_from_velocity(0, 1), math.pi/2)
assert math.isclose(angle_from_velocity(-1, 0), math.pi)
assert angle_from_velocity(0, 0) == 0.0

# État initial
x, y = 0.0, 0.0
vx, vy = 0.0, 0.0

# "Haut-gauche" maintenu (UP+LEFT) = -135° = -3π/4
angle_control = -3 * math.pi / 4

# Une itération de mise à jour : nouvelles position et vitesse
x, y, vx, vy, ang_v = physics.update_physics(
    x, y, vx, vy, angle_control, True, 0.02
)