"""
Misión 4: mensajes de la Tierra.

Cada cierto tiempo llega un mensaje de Control de Misión a la computadora de Comunicaciones.
Para responder hay que "codificar" la respuesta siguiendo un patrón de direcciones con los dos sticks:
  - flechas azules = stick izquierdo (WASD en el teclado)
  - flechas rosas  = stick derecho (flechas del teclado)
Enviar la respuesta gasta energía (la antena es muy potente), pero cada mensaje trae una ayuda y puntos.
Si nadie responde a tiempo, el mensaje se pierde.

Lo que enseña: un mensaje entre la Tierra y Marte tarda minutos en llegar (según la distancia entre
los planetas), así que los astronautas no pueden recibir ayuda al instante.
"""
import math
import random
import pygame as pg
from settings import COMMS, TILE
from nasa_data import (EARTH_MARS_MIN_KM, EARTH_MARS_MAX_KM, LIGHT_SPEED_KM_S, COMMS_FACTS, COMMS_SOURCES)
from menu import render_spaced, wrap_text
from greenhouse import draw_projector, hologramize
from missions import draw_station, blink, WARN_YELLOW, ALERT_RED
from controls import CONTROLS

EARTH_BLUE = (90, 180, 255)
LEFT_COLOR = (80, 210, 255)    # Stick izquierdo / WASD
RIGHT_COLOR = (255, 95, 200)   # Stick derecho / flechas
OK_GREEN = (70, 220, 120)

DIRECTION_ANGLE = {"up": 0, "right": 90, "down": 180, "left": 270}
# Tecla que corresponde a cada paso del patrón (el mando se traduce a estas teclas en controls.py)
STEP_KEYS = {
    ("L", "up"): pg.K_w, ("L", "down"): pg.K_s, ("L", "left"): pg.K_a, ("L", "right"): pg.K_d,
    ("R", "up"): pg.K_UP, ("R", "down"): pg.K_DOWN, ("R", "left"): pg.K_LEFT, ("R", "right"): pg.K_RIGHT,
}
KEY_STEPS = {key: step for step, key in STEP_KEYS.items()}

# Mensajes de Control de Misión y la ayuda que da cada uno al responderlo
MESSAGES = [
    {"subject": "Pronóstico del clima espacial",
     "body": "Nuestros satélites vigilan el Sol todo el tiempo. Respondan y les mandaremos el pronóstico "
             "para avisarles antes de la próxima tormenta solar.",
     "effect": "storm_warning",
     "reward": "La próxima tormenta solar se avisará 10 segundos antes."},
    {"subject": "Diagnóstico del soporte vital",
     "body": "Los ingenieros revisaron los datos del reciclador de aire y encontraron un ajuste. "
             "Respondan para recibirlo.",
     "effect": "oxygen",
     "reward": "+10 de oxígeno: el reciclador de aire funciona mejor."},
    {"subject": "Plan de energía",
     "body": "Calculamos un horario para que los equipos usen menos energía. "
             "Respondan para activarlo en la estación.",
     "effect": "energy_delay",
     "reward": "El tanque de energía tardará 15 segundos más en entrar en reserva."},
    {"subject": "Saludos de sus familias",
     "body": "Sus familias les mandan muchos saludos desde la Tierra. "
             "¡Respondan para que sepan que la tripulación está bien!",
     "effect": "morale",
     "reward": "+100 puntos extra: ¡la tripulación está muy contenta!"},
]

# Continentes aproximados como manchas (longitud, latitud, tamaño en grados) para el holograma de la Tierra
CONTINENTS = [
    (-100, 48, 20), (-112, 35, 12), (-88, 18, 9), (-62, -8, 16), (-64, -32, 10),       # América
    (12, 50, 11), (25, 58, 9), (18, 8, 18), (28, -18, 13), (42, 10, 8),                 # Europa y África
    (85, 52, 24), (110, 45, 16), (78, 22, 11), (105, 25, 12), (60, 38, 12),             # Asia
    (135, -25, 12), (-40, 72, 9),                                                       # Australia y Groenlandia
]


# ====================================================================== holograma de la Tierra
def draw_earth(size, t):
    """ La Tierra en blanco (luego se tiñe): globo con paralelos, meridianos que giran, continentes,
    una órbita inclinada y un satélite """
    surf = pg.Surface((size, size), pg.SRCALPHA)
    cx, cy = size / 2, size / 2
    R = size * 0.36
    rotation = t * 0.5

    pg.draw.circle(surf, (255, 255, 255, 38), (cx, cy), R)
    for lat in (-60, -30, 0, 30, 60):
        la = math.radians(lat)
        half = R * math.cos(la)
        y = cy - R * math.sin(la)
        pg.draw.ellipse(surf, (255, 255, 255, 90), (cx - half, y - half * 0.09, 2 * half, half * 0.18), 1)
    for k in range(6):
        lon = rotation + k * math.pi / 6
        w = abs(R * math.sin(lon))
        if w > 2:
            pg.draw.ellipse(surf, (255, 255, 255, 60), (cx - w, cy - R, 2 * w, 2 * R), 1)

    for lon, lat, deg in CONTINENTS:
        rel = math.radians(lon) + rotation
        la = math.radians(lat)
        depth = math.cos(la) * math.cos(rel)
        if depth <= 0.08:
            continue  # Está del otro lado del planeta
        x = cx + R * math.cos(la) * math.sin(rel)
        y = cy - R * math.sin(la)
        h = R * math.radians(deg) * 1.1
        w = h * max(0.25, math.cos(rel)) * 1.25
        blob = pg.Rect(0, 0, max(2, w), max(2, h))
        blob.center = (x, y)
        pg.draw.ellipse(surf, (255, 255, 255, int(110 + 100 * depth)), blob)
        pg.draw.ellipse(surf, (255, 255, 255, 255), blob, 1)

    pg.draw.circle(surf, (255, 255, 255, 255), (cx, cy), R, 3)
    orbit = pg.Rect(cx - R * 1.35, cy - R * 0.28, R * 2.7, R * 0.56)
    pg.draw.ellipse(surf, (255, 255, 255, 120), orbit, 1)
    a = t * 1.3
    sat = (cx + math.cos(a) * R * 1.35, cy + math.sin(a) * R * 0.28)
    if math.sin(a) > -0.2 or math.hypot(sat[0] - cx, sat[1] - cy) > R:  # Se esconde detrás del planeta
        pg.draw.rect(surf, (255, 255, 255, 255), (sat[0] - 4, sat[1] - 3, 8, 6))
        pg.draw.line(surf, (255, 255, 255, 220), (sat[0] - 12, sat[1]), (sat[0] + 12, sat[1]), 2)
    return surf


def draw_signal_waves(surface, origin, t, color, outward=True, spread=170, count=4):
    """ Arcos de señal: salen de la Tierra (enviando) o llegan hacia ella (recibiendo) """
    for i in range(count):
        phase = (t * 0.8 + i / count) % 1
        if not outward:
            phase = 1 - phase
        r = 40 + phase * spread
        alpha = int(220 * (1 - phase))
        rect = pg.Rect(0, 0, r * 2, r * 2)
        rect.center = origin
        pg.draw.arc(surface, (*color, alpha), rect, -0.6, 0.6, 3)


def draw_arrow(surface, center, direction, size, color):
    """ Flecha que apunta hacia direction ("up", "down", "left", "right") """
    angle = math.radians(DIRECTION_ANGLE[direction])
    points = [(0, -size), (size * 0.62, -size * 0.05), (size * 0.24, -size * 0.05), (size * 0.24, size * 0.72),
              (-size * 0.24, size * 0.72), (-size * 0.24, -size * 0.05), (-size * 0.62, -size * 0.05)]
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    pg.draw.polygon(surface, color, [(center[0] + x * cos_a - y * sin_a, center[1] + x * sin_a + y * cos_a)
                                     for x, y in points])


# ====================================================================== misión
class CommsMission:
    """ Estados:
      "idle"      → sin mensajes; cuenta atrás hasta el siguiente
      "incoming"  → llegó un mensaje: hay reply_window segundos para responderlo
      "answering" → la computadora está abierta
    """

    def __init__(self, game):
        self.game = game
        self.cfg = COMMS
        self.cell = self.cfg["station_cell"]
        self.x, self.y = self.cell[0] + 0.5, self.cell[1] + 0.5
        self.state = "idle"
        self.timer = self.cfg["first_message"]
        self.message = None
        self.answered = 0
        self.lost = 0
        self.deck = []
        self.computer = CommsComputer(game, self)

    # ------------------------------------------------------------------ lógica
    def new_message(self):
        if not self.deck:
            self.deck = random.sample(MESSAGES, len(MESSAGES))
        message = dict(self.deck.pop())
        distance_km = random.uniform(EARTH_MARS_MIN_KM, EARTH_MARS_MAX_KM)
        message["distance_mkm"] = distance_km / 1e6
        message["delay_min"] = distance_km / LIGHT_SPEED_KM_S / 60
        message["pattern"] = self.make_pattern()
        return message

    def make_pattern(self):
        """ El primer mensaje usa solo el stick izquierdo; los siguientes son más largos y mezclan los dos """
        low, high = self.cfg["pattern_length"]
        length = min(high, low + self.answered)
        directions = list(DIRECTION_ANGLE)
        pattern = []
        for _ in range(length):
            stick = "L" if self.answered == 0 or random.random() < 0.55 else "R"
            pattern.append((stick, random.choice(directions)))
        return pattern

    def update(self, dt_ms):
        dt = dt_ms / 1000
        if self.state == "idle":
            self.timer -= dt
            if self.timer <= 0:
                self.message = self.new_message()
                self.state = "incoming"
                self.timer = self.cfg["reply_window"]
                CONTROLS.rumble(0.3, 0.3, 200)
        elif self.state == "incoming":
            self.timer -= dt
            if self.timer <= 0:
                self.lost += 1
                self.message = None
                self.state = "idle"
                self.timer = random.uniform(*self.cfg["interval"])

    def player_in_range(self):
        player = self.game.player
        return math.hypot(player.x - self.x, player.y - self.y) <= self.cfg["interact_range"]

    def try_interact(self):
        """ La computadora se puede abrir siempre; si hay mensaje, se responde """
        if not self.player_in_range():
            return None
        if self.state == "incoming":
            self.state = "answering"
        return self.computer

    def on_computer_closed(self, sent):
        if sent:
            self.apply_effect(self.message["effect"])
            self.answered += 1
            self.game.score += self.cfg["reward_points"]
            self.game.resources.energy = self.game.resources.clamp(
                self.game.resources.energy - self.cfg["transmit_energy"])
            self.message = None
            self.state = "idle"
            self.timer = random.uniform(*self.cfg["interval"])
        elif self.state == "answering":
            self.state = "incoming"  # Salió sin responder: el mensaje sigue esperando

    def apply_effect(self, effect):
        game = self.game
        if effect == "storm_warning":
            storm = game.storm_mission
            if storm.state == "warning":
                storm.timer += 10
            else:
                storm.extra_warning += 10
        elif effect == "oxygen":
            game.resources.oxygen = game.resources.clamp(game.resources.oxygen + 10)
        elif effect == "energy_delay":
            energy = game.energy_mission
            if energy.state == "stable":
                energy.time_to_alert += 15
                energy.cooldown_total += 15
            else:
                energy.bonus_delay += 15
        elif effect == "morale":
            game.score += 100

    # ------------------------------------------------------------------ dibujo y avisos
    def prompt(self):
        if not self.player_in_range():
            return None
        return "RESPONDER MENSAJE DE LA TIERRA" if self.state == "incoming" else "COMPUTADORA DE COMUNICACIONES"

    def get_alert(self):
        if self.state != "incoming":
            return None
        return {
            "id": "comms",
            "tag": "MENSAJE DE LA TIERRA",
            "title": f"{self.message['subject']}",
            "hint": f"Responde en la computadora de Comunicaciones ({CONTROLS.label('interact')}). "
                    f"Se pierde en {math.ceil(self.timer)} s.",
            "color": EARTH_BLUE,
        }

    def draw_world(self):
        """ Vista 2D: la computadora en el mapa con una Tierra pequeña encima """
        incoming = self.state == "incoming"
        border = EARTH_BLUE if not incoming or blink(300) else WARN_YELLOW
        prompt = f"[{CONTROLS.label('interact')}] COMUNICACIONES" if self.player_in_range() else None
        base = draw_station(self.game, self.cell, (16, 28, 52), border, "COMUNICACIONES", prompt)
        screen_rect = base.inflate(-24, -34)
        pg.draw.rect(self.game.screen, (20, 60, 110), screen_rect)
        if incoming and blink(400):
            env = screen_rect.inflate(-14, -12)
            pg.draw.rect(self.game.screen, (240, 240, 240), env, 2)
            pg.draw.lines(self.game.screen, (240, 240, 240), False, [env.topleft, env.center, env.topright], 2)

    def billboards(self):
        """ Vista 3D: escritorio con la computadora y la Tierra en holograma flotando encima """
        t = pg.time.get_ticks() / 1000
        surf = pg.Surface((220, 320), pg.SRCALPHA)
        draw_projector(surf, 110, 150, 130, 120, EARTH_BLUE, t)
        earth = hologramize(draw_earth(140, t), EARTH_BLUE, t)
        surf.blit(earth, earth.get_rect(center=(110, 78 + math.sin(t * 2) * 4)))
        # Escritorio
        pg.draw.rect(surf, (52, 50, 58), (10, 262, 200, 18), border_radius=4)
        pg.draw.rect(surf, (36, 35, 42), (22, 280, 16, 40))
        pg.draw.rect(surf, (36, 35, 42), (182, 280, 16, 40))
        # Monitor
        monitor = pg.Rect(40, 160, 140, 92)
        pg.draw.rect(surf, (60, 62, 70), monitor, border_radius=8)
        screen_rect = monitor.inflate(-16, -16)
        pg.draw.rect(surf, (18, 55, 105), screen_rect)
        if self.state == "incoming" and blink(400):
            env = screen_rect.inflate(-50, -34)
            pg.draw.rect(surf, (245, 245, 245), env, 3)
            pg.draw.lines(surf, (245, 245, 245), False, [env.topleft, env.center, env.topright], 3)
        else:
            for i in range(4):
                pg.draw.line(surf, (90, 160, 230), (screen_rect.x + 8, screen_rect.y + 12 + i * 13),
                             (screen_rect.right - 8 - i * 14, screen_rect.y + 12 + i * 13), 3)
        pg.draw.rect(surf, (60, 62, 70), (100, 252, 20, 12))
        pg.draw.rect(surf, (75, 77, 86), (64, 266, 92, 8), border_radius=3)  # Teclado
        return [(self.x, self.y, surf, 1.0, 0.0, False)]

    def draw_minimap_marker(self, x0, y0, cell):
        incoming = self.state == "incoming"
        if incoming and not blink(300):
            return
        color = WARN_YELLOW if incoming else EARTH_BLUE
        pg.draw.rect(self.game.screen, color, (x0 + self.cell[0] * cell, y0 + self.cell[1] * cell, cell, cell))


# ====================================================================== computadora
class CommsComputer:
    """ Ventana con el holograma de la Tierra a la izquierda y un monitor de computadora a la derecha.
    Fases: "empty" (sin mensajes) → "read" (leer el mensaje) → "pattern" (codificar la respuesta) → "sent" """

    WIDTH, HEIGHT = 1240, 640
    OPEN_MS = 260
    SENT_MS = 2800
    input_context = "pattern"  # Stick izq. → WASD, stick der. → flechas (ver controls.py)

    def __init__(self, game, mission):
        self.game = game
        self.mission = mission
        self.title_font = pg.font.Font(None, 30)
        self.big_font = pg.font.Font(None, 46)
        self.text_font = pg.font.Font(None, 28)
        self.small_font = pg.font.Font(None, 23)
        self.step_font = pg.font.Font(None, 20)
        self.phase = "empty"
        self.step = 0
        self.flash = None
        self.opened_at = 0
        self.sent_at = None
        self.fact = COMMS_FACTS[0]

    def start(self):
        self.opened_at = pg.time.get_ticks()
        self.phase = "read" if self.mission.message else "empty"
        self.step = 0
        self.flash = None
        self.sent_at = None
        self.fact = random.choice(COMMS_FACTS)

    def close(self, sent):
        self.mission.on_computer_closed(sent)
        self.game.close_terminal()

    def handle_event(self, event):
        if event.type != pg.KEYDOWN or self.phase == "sent":
            return
        if event.key == pg.K_ESCAPE:
            self.close(sent=False)
        elif self.phase == "empty" and event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
            self.close(sent=False)
        elif self.phase == "read" and event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
            self.phase = "pattern"
        elif self.phase == "pattern" and event.key in KEY_STEPS:
            pattern = self.mission.message["pattern"]
            now = pg.time.get_ticks()
            if KEY_STEPS[event.key] == pattern[self.step]:
                self.step += 1
                self.flash = ("ok", now)
                if self.step >= len(pattern):
                    self.phase = "sent"
                    self.sent_at = now
                    CONTROLS.rumble(0.4, 0.6, 350)
            else:
                self.step = 0  # Un error reinicia el patrón (sigue a la vista)
                self.flash = ("bad", now)
                CONTROLS.rumble(0.8, 0.2, 150)

    def update(self, dt_ms):
        if self.phase == "sent" and pg.time.get_ticks() - self.sent_at >= self.SENT_MS:
            self.close(sent=True)

    # ------------------------------------------------------------------ dibujo
    def draw(self, screen):
        window = self.render()
        progress = min(1.0, (pg.time.get_ticks() - self.opened_at) / self.OPEN_MS)
        if progress < 1:
            ease = 1 - (1 - progress) ** 3
            window = pg.transform.smoothscale(window, (self.WIDTH, max(6, int(self.HEIGHT * ease))))
        screen.blit(window, window.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2)))

    def render(self):
        window = pg.Surface((self.WIDTH, self.HEIGHT), pg.SRCALPHA)
        self.draw_earth_area(window, pg.Rect(0, 30, 330, 560))
        self.draw_monitor(window, pg.Rect(330, 10, 900, 580))
        return window

    def draw_earth_area(self, window, area):
        t = pg.time.get_ticks() / 1000
        overlay = pg.Surface(area.size, pg.SRCALPHA)
        center = (area.width // 2, 230)
        draw_projector(overlay, center[0], 430, 260, 330, EARTH_BLUE, t)
        if self.phase == "sent":
            draw_signal_waves(overlay, center, t * 1.6, EARTH_BLUE, outward=True)
        elif self.phase in ("read", "pattern"):
            draw_signal_waves(overlay, center, t, EARTH_BLUE, outward=False)
        earth = hologramize(draw_earth(260, t), EARTH_BLUE, t)
        overlay.blit(earth, earth.get_rect(center=(center[0], center[1] + math.sin(t * 2) * 5)))
        window.blit(overlay, area.topleft)

        label = render_spaced(self.title_font, "TIERRA", EARTH_BLUE, 6)
        window.blit(label, label.get_rect(midtop=(area.centerx, area.y + 452)))
        message = self.mission.message
        if message:
            info = f"a {message['distance_mkm']:.0f} millones de km"
            text = self.small_font.render(info, True, (190, 215, 240))
            window.blit(text, text.get_rect(midtop=(area.centerx, area.y + 482)))

    def draw_monitor(self, window, rect):
        """ Monitor de computadora: marco, pantalla, base y luz de encendido """
        pg.draw.rect(window, (58, 60, 68), rect.inflate(0, -40).move(0, -20), border_radius=24)
        bezel = rect.inflate(0, -40).move(0, -20)
        pg.draw.rect(window, (88, 90, 100), bezel, 3, border_radius=24)
        stand = [(rect.centerx - 60, bezel.bottom), (rect.centerx + 60, bezel.bottom),
                 (rect.centerx + 90, rect.bottom), (rect.centerx - 90, rect.bottom)]
        pg.draw.polygon(window, (48, 50, 58), stand)
        pg.draw.rect(window, (70, 72, 82), (rect.centerx - 140, rect.bottom - 6, 280, 12), border_radius=5)
        brand = self.small_font.render("ESTACIÓN MARTE  ·  COMPUTADORA DE COMUNICACIONES", True, (150, 152, 162))
        window.blit(brand, (bezel.x + 30, bezel.bottom - 30))
        pg.draw.circle(window, OK_GREEN if blink(900) or self.phase != "read" else (30, 90, 50),
                       (bezel.right - 36, bezel.bottom - 20), 6)

        screen_rect = pg.Rect(bezel.x + 26, bezel.y + 24, bezel.width - 52, bezel.height - 72)
        screen = pg.Surface(screen_rect.size)
        self.draw_desktop(screen)
        window.blit(screen, screen_rect.topleft)
        pg.draw.rect(window, (20, 20, 24), screen_rect, 3)

    def draw_desktop(self, s):
        """ Pantalla tipo escritorio de computadora: barra superior, ventana del mensaje y panel de respuesta """
        w, h = s.get_size()
        for y in range(h):  # Fondo azul con degradado
            c = 18 + int(30 * y / h)
            pg.draw.line(s, (10, c, 40 + c), (0, y), (w, y))
        pg.draw.rect(s, (8, 18, 34), (0, 0, w, 30))
        s.blit(self.small_font.render("CENTRO DE COMUNICACIONES", True, (200, 220, 245)), (12, 7))
        bars = 4 if self.phase != "sent" else (pg.time.get_ticks() // 200) % 5
        for i in range(4):
            color = OK_GREEN if i < bars else (50, 60, 80)
            pg.draw.rect(s, color, (w - 70 + i * 12, 22 - (i + 1) * 4, 8, (i + 1) * 4))
        s.blit(self.small_font.render("SEÑAL", True, (200, 220, 245)), (w - 132, 7))

        if self.phase == "empty":
            self.draw_empty(s)
            return
        self.draw_message_window(s, pg.Rect(14, 42, w - 28, 196))
        panel = pg.Rect(14, 250, w - 28, h - 264)
        if self.phase == "read":
            self.draw_read_panel(s, panel)
        elif self.phase == "pattern":
            self.draw_pattern_panel(s, panel)
        else:
            self.draw_sent_panel(s, panel)

    def draw_empty(self, s):
        w, h = s.get_size()
        win = pg.Rect(60, 70, w - 120, h - 140)
        pg.draw.rect(s, (232, 236, 244), win, border_radius=6)
        pg.draw.rect(s, (40, 90, 170), (win.x, win.y, win.width, 32), border_top_left_radius=6, border_top_right_radius=6)
        s.blit(self.small_font.render("BANDEJA DE ENTRADA", True, (255, 255, 255)), (win.x + 12, win.y + 8))
        title = self.big_font.render("No hay mensajes nuevos", True, (30, 40, 60))
        s.blit(title, title.get_rect(midtop=(win.centerx, win.y + 60)))
        y = win.y + 120
        for line in wrap_text(self.text_font, self.fact, win.width - 60):
            s.blit(self.text_font.render(line, True, (50, 60, 80)), (win.x + 30, y))
            y += self.text_font.get_linesize()
        s.blit(self.small_font.render(COMMS_SOURCES, True, (110, 120, 140)), (win.x + 30, win.bottom - 60))
        hint = self.small_font.render(f"[{CONTROLS.label('confirm')}] Cerrar", True, (40, 90, 170))
        s.blit(hint, (win.x + 30, win.bottom - 32))

    def draw_message_window(self, s, win):
        message = self.mission.message
        pg.draw.rect(s, (232, 236, 244), win, border_radius=6)
        pg.draw.rect(s, (40, 90, 170), (win.x, win.y, win.width, 30), border_top_left_radius=6, border_top_right_radius=6)
        s.blit(self.small_font.render("BANDEJA DE ENTRADA  —  1 mensaje nuevo", True, (255, 255, 255)), (win.x + 12, win.y + 7))
        x, y = win.x + 16, win.y + 40
        s.blit(self.small_font.render("De: Control de Misión (Tierra)", True, (80, 90, 110)), (x, y))
        s.blit(self.text_font.render(f"Asunto: {message['subject']}", True, (20, 30, 50)), (x, y + 20))
        y += 50
        for line in wrap_text(self.small_font, message["body"], win.width - 32)[:3]:
            s.blit(self.small_font.render(line, True, (40, 50, 70)), (x, y))
            y += self.small_font.get_linesize()
        delay = (f"Este mensaje viajó {message['distance_mkm']:.0f} millones de km y tardó "
                 f"{message['delay_min']:.1f} minutos en llegar, aunque va a la velocidad de la luz.")
        y = win.bottom - 8 - 2 * self.small_font.get_linesize()
        for line in wrap_text(self.small_font, delay, win.width - 32)[:2]:
            s.blit(self.small_font.render(line, True, (30, 90, 170)), (x, y))
            y += self.small_font.get_linesize()

    def panel_frame(self, s, panel, title):
        pg.draw.rect(s, (10, 26, 48), panel, border_radius=6)
        pg.draw.rect(s, EARTH_BLUE, panel, 2, border_radius=6)
        s.blit(render_spaced(self.small_font, title, EARTH_BLUE, 3), (panel.x + 16, panel.y + 10))

    def draw_read_panel(self, s, panel):
        self.panel_frame(s, panel, "RESPONDER")
        message = self.mission.message
        button = pg.Rect(0, 0, 420, 56)
        button.center = (panel.centerx, panel.y + 72)
        pulse = 0.6 + 0.4 * (math.sin(pg.time.get_ticks() / 160) + 1) / 2
        pg.draw.rect(s, tuple(int(c * pulse) for c in EARTH_BLUE), button, border_radius=10)
        label = self.text_font.render(f"[{CONTROLS.label('confirm')}]  CODIFICAR RESPUESTA", True, (5, 15, 30))
        s.blit(label, label.get_rect(center=button.center))
        lines = [
            f"Ayuda al responder: {message['reward']}",
            f"Enviar usa {COMMS['transmit_energy']} de energía: la antena necesita mucha potencia.",
            f"[{CONTROLS.label('back')}] Salir sin responder  ·  el mensaje se pierde si tardas demasiado.",
        ]
        y = button.bottom + 16
        for i, line in enumerate(lines):
            color = (255, 220, 120) if i == 0 else (190, 205, 225)
            s.blit(self.small_font.render(line, True, color), (panel.x + 20, y))
            y += 26

    def draw_pattern_panel(self, s, panel):
        self.panel_frame(s, panel, "CODIFICA TU RESPUESTA: SIGUE EL PATRÓN")
        labels = CONTROLS.labels()
        left_name = "STICK IZQUIERDO" if CONTROLS.last_device == "gamepad" else "WASD"
        right_name = "STICK DERECHO" if CONTROLS.last_device == "gamepad" else "FLECHAS"
        legend_x = panel.x + 16
        for color, text in ((LEFT_COLOR, f"Azul = {left_name}"), (RIGHT_COLOR, f"Rosa = {right_name}")):
            pg.draw.circle(s, color, (legend_x + 7, panel.y + 44), 7)
            surface = self.small_font.render(text, True, (220, 230, 245))
            s.blit(surface, (legend_x + 20, panel.y + 36))
            legend_x += surface.get_width() + 50

        pattern = self.mission.message["pattern"]
        now = pg.time.get_ticks()
        flash_bad = self.flash and self.flash[0] == "bad" and now - self.flash[1] < 300
        spacing = 92
        start_x = panel.centerx - (len(pattern) - 1) * spacing / 2
        cy = panel.y + 112
        for i, (stick, direction) in enumerate(pattern):
            cx = start_x + i * spacing
            color = LEFT_COLOR if stick == "L" else RIGHT_COLOR
            if i < self.step:
                pg.draw.circle(s, OK_GREEN, (cx, cy), 34)
                pg.draw.lines(s, (10, 30, 20), False, [(cx - 14, cy), (cx - 3, cy + 12), (cx + 16, cy - 12)], 5)
            elif i == self.step:
                ring = ALERT_RED if flash_bad else color
                radius = 34 + 4 * (math.sin(now / 120) + 1) / 2
                pg.draw.circle(s, tuple(c // 4 for c in color), (cx, cy), 34)
                pg.draw.circle(s, ring, (cx, cy), radius, 4)
                draw_arrow(s, (cx, cy), direction, 22, color)
            else:
                pg.draw.circle(s, (20, 36, 60), (cx, cy), 34)
                pg.draw.circle(s, tuple(c // 2 for c in color), (cx, cy), 34, 2)
                draw_arrow(s, (cx, cy), direction, 20, tuple(c // 2 for c in color))
            tag = self.step_font.render("IZQ" if stick == "L" else "DER", True, color)
            s.blit(tag, tag.get_rect(midtop=(cx, cy + 40)))

        bar = pg.Rect(panel.x + 20, panel.bottom - 34, panel.width - 40, 14)
        pg.draw.rect(s, (30, 45, 70), bar, border_radius=7)
        fill = int(bar.width * self.step / len(pattern))
        if fill:
            pg.draw.rect(s, OK_GREEN, (bar.x, bar.y, fill, bar.height), border_radius=7)
        hint = "¡Te equivocaste! Empieza de nuevo el patrón." if flash_bad else \
            f"Paso {self.step + 1} de {len(pattern)}   ·   [{labels['back']}] Salir"
        s.blit(self.small_font.render(hint, True, ALERT_RED if flash_bad else (190, 205, 225)), (bar.x, bar.y - 24))

    def draw_sent_panel(self, s, panel):
        self.panel_frame(s, panel, "TRANSMISIÓN")
        message = self.mission.message
        title = self.big_font.render("RESPUESTA ENVIADA", True, OK_GREEN)
        s.blit(title, title.get_rect(midtop=(panel.centerx, panel.y + 40)))
        lines = [
            (f"Llegará a la Tierra en {message['delay_min']:.1f} minutos.", (220, 230, 245)),
            (message["reward"], (255, 220, 120)),
            (f"+{COMMS['reward_points']} puntos   ·   -{COMMS['transmit_energy']} de energía por la transmisión", (190, 205, 225)),
        ]
        y = panel.y + 96
        for text, color in lines:
            surface = self.text_font.render(text, True, color)
            s.blit(surface, surface.get_rect(midtop=(panel.centerx, y)))
            y += 32
