RES = WIDTH, HEIGHT = 1600, 900

FPS = 60
TILE = 100  # Tamaño de cada celda del mapa en píxeles
PLAYER_POS = 1.5, 5
PLAYER_ANGLE = 0
PLAYER_SPEED = 0.004
PLAYER_ROT_SPEED = 0.002
PLAYER_CAN_SHOOT = False  # False = el jugador no dispara (Espacio, clic y X/RT del control no hacen nada)
MOUSE_SENSITIVITY = 0.0024

# Vista 3D con ray casting (ver render3d.py)
RAYCAST = {
    "fov_degrees": 60,     # Campo de visión
    "column_width": 4,     # Píxeles por rayo: 4 = 400 rayos a 1600 px (más bajo = más detalle, más lento)
    "ceiling_scale": 4,    # Resolución del techo con domos: 4 = se calcula a 1/4 y se escala (más bajo = más nítido, más lento)
}

# Portada y menú principal
GAME_TITLE = "ESTACIÓN MARTE"
GAME_SUBTITLE = "EL JUEGO "
# Música de fondo: la misma pista ambiental para el menú y todos los módulos
AMBIENT_MUSIC = "music/sonido_ambiente.mpeg"
MENU_MUSIC = AMBIENT_MUSIC
FOOTSTEP_SOUND = "music/sonido_pasos.mpeg"  # Pasos del jugador (se repite mientras camina)
# Fondo de la portada y el menú: None = negro. Acepta una imagen .png/.jpg (se escala a la pantalla).
MENU_BACKGROUND = None
MUSIC_VOLUME = 0.7   # Volumen inicial de la música (0.0 a 1.0)
SFX_VOLUME = 0.8     # Volumen inicial de los efectos (0.0 a 1.0)

TEXTURES = {
    "grass": "textures/grass.png",
    "player": "textures/player_skin.png",
    "tree": "textures/tree.png",
    "npc_1": "textures/astronauta_1.png",   # NPC (npc.py), en todos los módulos
    "npc_2": "textures/astronauta_2.png",   # SpecialNPC (special_npc.py), en todos los módulos
    "npc_3": "textures/astronauta_3.png",   # ExtraNPC (extra_npc.py), en todos los módulos
    "grass_2": "textures/grass_2.png",
    "tree_2": "textures/tree_2.png",
    "grass_3": "textures/grass_3.png",
    "tree_3": "textures/tree_3.png",
    "pause": "textures/pause_button.png",
    "restart": "textures/restart_button.png",
    "quit": "textures/quit_button.png",
    "settings": "textures/settings_button.png"
}

# Duración de la partida: un "sol" (día marciano, 24 h 39 min en la vida real) comprimido a unos minutos.
# Si llegas al final del sol con la tripulación a salvo, la misión se cumple.
SOL_DURATION = 240  # segundos

# Recursos de la base (0 a 100). Las tasas están en puntos por segundo.
RESOURCES = {
    "energy_start": 80,
    "oxygen_start": 80,
    "shield_start": 30,
    "energy_drain": 0.3,          # Consumo normal de la base
    "energy_reserve_drain": 0.6,  # Consumo extra mientras el tanque está en modo de reserva (alerta sin atender)
    "oxygen_gain": 0.2,           # El generador de oxígeno funciona si hay energía suficiente...
    "oxygen_loss": 0.8,           # ...si no, la tripulación consume el oxígeno guardado
    "oxygen_min_energy": 20,      # Por debajo de esta energía el generador de oxígeno se apaga
    "shield_decay": 0.15,         # El blindaje se descarga poco a poco
    "radiation_limit": 70,        # Radiación máxima que puede recibir la tripulación
}

# Misión 1: tanque de energía en el módulo "Energía"
ENERGY_MISSION = {
    "refill_energy": 24,       # Energía que se recupera al rellenar el tanque
    "station_cell": (33, 34),  # Celda del mapa donde está el tanque (módulo de Energía)
    "first_alert": 20,         # Segundos desde el inicio de la partida hasta la primera alerta
    "cooldown": 30,            # Segundos tras rellenar el tanque hasta la siguiente alerta
    "interact_range": 1.3,     # Distancia (en celdas) a la que se puede presionar E
    "press_gain": 3.5,         # % de la barra que sube cada tecla correcta
    "wrong_penalty": 4,        # % que baja al presionar una tecla equivocada
    "decay": 6,                # % por segundo que baja la barra si dejas de presionar
}

# Misión 2: tormenta solar. La consola de blindaje está en el módulo central "Soporte Vital".
SOLAR_STORM = {
    "station_cell": (19, 25),        # Celda de la consola de blindaje (módulo de Soporte Vital)
    "first_warning": 50,             # Segundos hasta el primer aviso de tormenta
    "interval": (55, 75),            # Segundos entre una tormenta y el siguiente aviso (al azar)
    "warning_time": 25,              # Segundos de aviso antes del impacto
    "impact_time": 8,                # Segundos que dura el impacto de radiación
    "intensity_per_class": 5,        # Intensidad = magnitud de la llamarada × este valor (X9.3 → 46)
    "shield_energy_cost": 0.8,       # Energía que cuesta cada punto de blindaje
    "shield_absorb": 1.5,            # Blindaje que se gasta por segundo durante el impacto
    "interact_range": 1.3,
}

# Misión 3: cosecha en el invernadero. Las consolas están en el módulo "Cultivos".
# Cada cultivo tiene un nivel de luz de 0 (apagada) a 3 (alta): más luz = crece más rápido y da algo de
# oxígeno, pero gasta energía. Para cumplir la misión hay que juntar FOOD_GOAL raciones antes del fin del sol.
GREENHOUSE = {
    "interact_range": 1.3,
    "food_goal": 5,               # Raciones de comida necesarias al terminar el sol
    "start_light": 1,             # Nivel de luz inicial de cada cultivo
    "energy_per_light": 0.06,     # Energía por segundo que gasta cada nivel de luz encendido
    "oxygen_per_light": 0.03,     # Oxígeno por segundo que producen las plantas por cada nivel de luz
    # Cultivos: celda de su consola (las tres en fila), segundos para estar listo con luz alta (con luz media
    # tarda 1.5 veces más, con baja 3 veces) y raciones que da cada cosecha.
    # Los datos reales de cada planta están en nasa_data.py (PLANTS) y su apariencia en greenhouse.py (THEMES).
    "crops": [
        {"id": "lechuga", "cell": (17, 5), "grow_time": 40, "rations": 1},
        {"id": "mizuna", "cell": (19, 5), "grow_time": 50, "rations": 1},
        {"id": "chile", "cell": (21, 5), "grow_time": 80, "rations": 2},
    ],
}

# Misión 4: mensajes de la Tierra. La computadora está en el módulo "Comunicaciones con la Tierra".
COMMS = {
    "station_cell": (5, 35),
    "interact_range": 1.3,
    "first_message": 35,        # Segundos hasta el primer mensaje
    "interval": (45, 60),       # Segundos entre una respuesta (o un mensaje perdido) y el siguiente mensaje
    "reply_window": 45,         # Segundos para responder antes de que el mensaje se pierda
    "transmit_energy": 6,       # Energía que gasta enviar la respuesta
    "reward_points": 100,       # Puntos por cada mensaje respondido
    "pattern_length": (4, 7),   # Pasos del patrón: el primero tiene 4 y cada mensaje respondido suma uno, hasta 7
}

# Módulos de la estación (ver map.py). El mapa se genera con estos círculos y los tubos de STATION_TUBES.
# - center / radius: centro y radio del módulo, en celdas
# - music: música al entrar al módulo
# - skin: variante de sprites (1, 2 o 3) de los NPCs que aparecen ahí
# - start: posición inicial del jugador si la partida arranca en este módulo ("python main.py N")
# - color: color del módulo en el minimapa y de la franja de las paredes en 3D
# - floor_color: color del piso en 3D (soil=True le agrega textura de tierra)
SECTORS = [
    {
        "id": "soporte",
        "name": "Soporte Vital",
        "center": (19.5, 21.5),
        "radius": 7.2,
        "music": AMBIENT_MUSIC,
        "skin": 1,
        "start": (19.5, 21.5),
        "color": (70, 130, 180),
        "floor_color": (52, 66, 90),
    },
    {
        "id": "energia",
        "name": "Energía",
        "center": (32.5, 33.5),
        "radius": 4.6,
        "music": AMBIENT_MUSIC,
        "skin": 2,
        "start": (31.5, 32.5),
        "color": (200, 160, 40),
        "floor_color": (78, 68, 44),
    },
    {
        "id": "cultivos",
        "name": "Cultivos",
        "center": (19.5, 6.5),
        "radius": 4.6,
        "music": AMBIENT_MUSIC,
        "skin": 3,
        "start": (19.5, 8.5),
        "color": (60, 160, 90),
        "floor_color": (150, 58, 34),  # Suelo rojo de Marte
        "soil": True,
    },
    {
        "id": "comunicaciones",
        "name": "Comunicaciones con la Tierra",
        "center": (6.5, 33.5),
        "radius": 4.6,
        "music": AMBIENT_MUSIC,
        "skin": 1,
        "start": (7.5, 32.5),
        "color": (60, 190, 190),
        "floor_color": (40, 70, 78),
    },
]

# Tubos que conectan los módulos: pares de índices de SECTORS (el tubo pertenece al primer módulo del par)
STATION_TUBES = [(0, 2), (0, 3), (0, 1)]
TUBE_HALF_WIDTH = 1.4  # Medio ancho de los tubos, en celdas
