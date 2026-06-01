import math



def normalize_vector(vx: float, vy: float) -> tuple[float, float]:
    """Retourne le vecteur normalisé (norme 1) dans la même direction que (vx, vy)."""
    norm = math.hypot(vx, vy)
    if norm == 0:
        return 0.0, 0.0
    return vx / norm, vy / norm





def limite_speed(vx: float, vy: float, max_speed: float) -> tuple[float, float]:
    """Limite la norme du vecteur  vitesse à max_speed."""
    speed = math.hypot(vx, vy)

    if speed <= max_speed or speed == 0 :
        return vx, vy
    normalise = max_speed / speed
    return vx * normalise, vy * normalise





def angle_from_velocity(vx: float, vy: float) -> float:
    """Retourne l'angle correspondant au vecteur vitesse."""
    return math.atan2(vy, vx)




def lerp_angle(a: float, b: float, t: float) -> float:
    """Interpolation angulaire entre a et b par le plus court chemin."""
    delta_brut = b - a
    delta = (delta_brut + math.pi) %(2*math.pi)-math.pi
    return a + t*delta 


from Constantes import *

def update_physics(x: float, y:float,  # position (pixels)
                   vx: float, vy: float, # vistesse (pixels/s)
                   angle_control: float, # angle "commandé" (radians)
                   go_up: bool,   # l'objet accelère-t-il ?
                   dt: float  #pas de temps (s)
                   ) -> tuple[float, float, float, float, float]:
    """
    Met à jour le modèle cinématique sur un pas de temps DT (en secondes).
    Équations appliquées :
        v(t+dt) = v(t) + a * dt
        p(t+dt) = p(t) + v * dt
        v       = FRICTION * v
        theta_v = atan2(vy, vx)

    Paramètres
    ----------
    x, y : float
        Position (pixels).
    vx, vy : float
        Vitesse (pixels/seconde).
    angle_control : float
        Direction désirée (radians).
    go_up : bool
        True si l'objet accélère.
    dt: float
        Pas de temps (s)

    Constantes utilisées (globales)
    -------------------------------
    ACCEL : float
    FRICTION : float
    MAX_SPEED : float

    Retour
    ------
    (x, y, vx, vy, angle_velocity)
        x, y : nouvelle position
        vx, vy : nouvelle vitesse
        angle_velocity : direction réelle du mouvement
    """
    if go_up:
        ax = ACCEL * math.cos(angle_control)
        ay = ACCEL * math.sin(angle_control)
    else:
        ax = 0
        ay = 0
    
    vx = vx + ax * dt
    vy = vy + ay * dt
    vx, vy = limite_speed(vx, vy, MAX_SPEED)
    vx, vy = FRICTION * vx, FRICTION * vy

    x, y = x + vx *dt, y + vy * dt
    angle_velocity = angle_from_velocity(vx, vy)
    return (x, y, vx, vy, angle_velocity)
