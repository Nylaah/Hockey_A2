import math

# ── Fenêtre ───────────────────────────────────────────────────────────────────
WIDTH  = 900
HEIGHT = 600

# ── Monde virtuel ─────────────────────────────────────────────────────────────
IMG_ORIGINAL_W = 740
TERRAIN_SCALE  = 2
VWIDTH         = IMG_ORIGINAL_W * TERRAIN_SCALE   # 1480 px

# ── Réseau ────────────────────────────────────────────────────────────────────
PORT = 5000

# ── Joueurs ───────────────────────────────────────────────────────────────────
COLLISION_RADIUS = 45
COLOR_LEFT       = (59,  130, 246)
COLOR_RIGHT      = (239,  68,  68)

# ── Balle (client) ────────────────────────────────────────────────────────────
BALL_Z_MAX     = 220.0
BALL_RADIUS    = 13
BALL_MIN_SCALE = 0.25

# ── Balle (serveur) ───────────────────────────────────────────────────────────
TOUCH_RADIUS = 75
BALL_TOUCH_Z = 55.0
MARGIN       = 110
