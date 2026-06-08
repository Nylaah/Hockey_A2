# Arborescence du projet — Puck Master

```
Projet_A2/
│
├── main.py               ← Point d'entrée client : lance Game().run()
├── server.py             ← Point d'entrée serveur : lance GameServer().run() en standalone
│
├── Physics.py            ← Moteur physique du joueur (accélération, friction, plafond de vitesse)
├── Constantes.py         ← Constantes physiques partagées (ACCEL, MAX_SPEED, FRICTION…)
│
├── terrain.png           ← Image du terrain de hockey affichée en fond
│
└── src/
    ├── __init__.py       ← Marque le dossier comme package Python (vide)
    │
    ├── constants.py      ← Toutes les constantes du jeu (taille fenêtre, couleurs, réseau, balle…)
    │
    ├── game.py           ← Orchestrateur client : enchaîne Menu → Connexion → Attente → Jeu
    │
    ├── game_server.py    ← Serveur TCP : gère les connexions, le score et délègue la balle
    │
    ├── connection.py     ← Encapsule un socket client côté serveur avec envoi asynchrone (queue)
    │
    ├── network_client.py ← Connexion TCP côté client : handshake, réception en thread, envoi
    │
    ├── ball.py           ← Balle côté client : reçoit l'état du serveur, dessine et anime
    │
    ├── ball_manager.py   ← Physique de la balle côté serveur : trajectoire, rebond, détection de point
    │
    ├── player.py         ← Joueur local (Player) et fantôme adversaire (OtherPlayer) avec interpolation
    │
    ├── ai_client.py      ← Bot IA : client TCP autonome qui suit la balle et sert
    │
    ├── screen_menu.py    ← Écran de menu : pseudo, IP, mode 1v1/2v2, choix d'équipe
    ├── screen_wait.py    ← Écran d'attente : spinner, compteur de joueurs, bouton "Remplir avec IA"
    ├── screen_game.py    ← Boucle de jeu principale : rendu terrain/balle/HUD, envoi de position
    │
    └── widgets.py        ← Composants UI réutilisables : TextInput (saisie texte) et Button (bouton)
```

---

## Description détaillée fichier par fichier

### `main.py`
Point d'entrée pour lancer le **client**.  
Crée une instance de `Game` et appelle `run()`.

---

### `server.py`
Point d'entrée pour lancer le **serveur en mode standalone** (sans interface graphique).  
Crée un `GameServer` et appelle `run()` — utile pour héberger une partie en réseau local.

---

### `Physics.py`
Moteur physique des joueurs.  
Contient :
- `normalize_vector` — normalise un vecteur 2D
- `limite_speed` — plafonne la vitesse à `MAX_SPEED`
- `angle_from_velocity` — angle réel du déplacement
- `lerp_angle` — interpolation angulaire par le chemin le plus court
- `update_physics` — applique accélération, friction et déplacement sur un pas de temps

---

### `Constantes.py`
Constantes physiques importées par `Physics.py` :  
`FRICTION`, `MAX_SPEED`, `ANGLE_BLEND`, `TURN_SPEED`, `ACCEL`.

---

### `terrain.png`
Image du terrain de hockey affichée en fond de la scène de jeu.  
Elle est redimensionnée à `VWIDTH × HEIGHT` au chargement.

---

### `src/constants.py`
Centralise toutes les valeurs partagées entre client et serveur :
- Dimensions de la fenêtre et du monde virtuel (`WIDTH`, `HEIGHT`, `VWIDTH`)
- Port réseau (`PORT`)
- Rayon de collision, couleurs des équipes
- Paramètres de la balle (rayon, hauteur max, zone de contact)
- Identifiants des modes de jeu (`GAME_MODE_1V1`, `GAME_MODE_2V2`)

---

### `src/game.py`
Orchestrateur principal côté client.  
Classe `Game` — méthode `run()` :
1. Affiche le menu
2. Lance un serveur embarqué si mode solo
3. Connecte le client TCP
4. Demande un remplissage IA si nécessaire
5. Affiche l'écran d'attente
6. Lance la boucle de jeu

---

### `src/game_server.py`
Serveur de jeu multijoueur.  
Classe `GameServer` :
- Accepte jusqu'à 2 (1v1) ou 4 (2v2) connexions TCP
- Attribue les rôles (`LEFT`, `RIGHT`, `LEFT_1`…)
- Lance la partie dès que tous les slots sont remplis
- Dispatche les messages (`POS`, `SERVE`, `IMPULSE`, `FILL_AI`)
- Gère le score et la remise en jeu via `BallManager`
- Peut remplir les slots vides avec des bots (`_fill_with_ai`)

---

### `src/connection.py`
Wrapper autour d'un socket client **côté serveur**.  
Classe `ClientConnection` :
- Thread d'envoi dédié (file `queue`) → `send()` non-bloquant
- `TCP_NODELAY` activé pour minimiser la latence
- `recv()` pour la lecture bloquante

---

### `src/network_client.py`
Connexion TCP **côté client**.  
Classe `NetworkClient` :
- `connect()` : handshake username/rôle avec le serveur
- Thread de réception qui accumule les lignes dans `_incoming`
- `get_messages()` / `put_back()` pour consommer les messages par les écrans
- `send()` pour envoyer des commandes

---

### `src/ball.py`
Représentation de la balle **côté client**.  
Classe `Ball` :
- Reçoit son état complet depuis le serveur (`update_from_msg`)
- Dessine la balle avec ombre, rétrécissement en hauteur et effet flash au rebond (`draw`)
- Dessine les cercles de prédiction (rebond bleu, cible jaune) (`draw_landing_circle`)

---

### `src/ball_manager.py`
Physique de la balle **côté serveur** (~30 fps dans un thread dédié).  
- `_BallFlight` : trajectoire en 3 phases (arc aller → sol → arc retour)
- `BallManager` :
  - `serve()` : démarre un vol depuis la position du serveur
  - `_tick()` : avance la simulation, détecte les touches et les points
  - Broadcasts `BALL`, `BOUNCE`, `SERVE_TURN`, `SCORE` vers tous les clients
  - `_new_flight()` : génère une trajectoire aléatoire vers le camp adverse

---

### `src/player.py`
Joueurs dans la scène de jeu.  
- `Player` (joueur local) :
  - Mouvement avec flèches + physique via `Physics.py`
  - `check_collision()` : rebond super-élastique contre les adversaires + envoi `IMPULSE`
  - `draw()` : triangle coloré (blanc pendant le flash de collision)
- `OtherPlayer` (adversaire/coéquipier distant) :
  - Interpolation lissée vers la dernière position reçue (`tick`)
  - Pas de physique locale — juste affichage

---

### `src/ai_client.py`
Bot IA qui se connecte au serveur comme un vrai client TCP.  
Classe `AIClient` :
- Thread réception (`_recv_loop`) + thread jeu (`_game_loop`) à ~30 fps
- `_choose_target()` : va sur le cercle de chute si la balle est pour lui, sinon rentre à la maison
- `_move_toward()` : physique simple (accélération/friction, même modèle que le joueur humain)
- Sert automatiquement après un délai aléatoire

---

### `src/screen_menu.py`
Écran de menu principal.  
Classe `MenuScreen` — méthode `run()` :
- Champs texte pour le pseudo et l'IP du serveur
- Boutons de sélection du mode (1v1 / 2v2) et de l'équipe (LEFT / RIGHT)
- Bouton **PLAY** (multijoueur) et **SOLO** (contre IA)
- Retourne `(username, team, server_ip, mode)` ou `None` si fermé

---

### `src/screen_wait.py`
Écran d'attente entre la connexion et le début de la partie.  
Classe `WaitScreen` — méthode `run()` :
- Affiche le nombre de joueurs connectés et un spinner animé
- Écoute `GAME_START` pour passer à la partie
- Bouton « Remplir avec IA » visible en mode multijoueur

---

### `src/screen_game.py`
Boucle de jeu graphique principale.  
Classe `GameScreen` — méthode `run()` :
- Traite les messages réseau (`_process`) : positions adversaires, balle, score, service
- Gère la physique du joueur local et l'interpolation des adversaires
- Envoie la position à ~30 fps
- Dessine le terrain scrollable (caméra centrée sur le joueur), la balle, les joueurs et le HUD
- HUD : score, invite de service, vitesses, indicateur réseau 4 barres

---

### `src/widgets.py`
Composants d'interface graphique réutilisables.  
- `TextInput` : champ texte avec curseur clignotant, placeholder et bordure active
- `Button` : bouton avec état `selected`/`hovered` et rendu par défaut
