"""
HUD de la partida, con el mismo estilo que los menús (negro con degradado, mayúsculas espaciadas y
acentos rojos):
  - arriba a la izquierda: sol, tiempo restante, sector y puntos
  - abajo a la izquierda: estado de la base (energía, oxígeno, blindaje, radiación y comida)
  - arriba a la derecha (debajo del minimapa): alertas como tarjetas de "objetivo" que entran deslizándose
  - centro: nombre del sector al cruzar una puerta
"""
import math
import pygame as pg
from settings import SECTORS
from menu import render_spaced, wrap_text
from controls import CONTROLS
from greenhouse import draw_projector, hologramize, render_hologram

RED = (200, 30, 30)
TEXT = (230, 230, 230)
TEXT_DIM = (150, 150, 150)
BAR_BG = (45, 45, 45)

ENERGY_COLOR = (255, 200, 0)
OXYGEN_COLOR = (80, 200, 255)
SHIELD_COLOR = (150, 120, 255)
RADIATION_COLOR = (235, 40, 40)
FOOD_COLOR = (70, 210, 90)
LOW_LEVEL = 20  # Debajo de este valor la barra parpadea

ALERT_WIDTH = 440
ALERT_SLIDE_MS = 320     # Duración de la animación de entrada de cada alerta
SECTOR_BANNER_MS = 3000  # Lo que dura en pantalla el nombre del sector


def gradient_panel(width, height, alpha=200, fade_from=0.45):
    """ Panel negro que se desvanece hacia la derecha (como la barra de selección de los menús) """
    panel = pg.Surface((width, height), pg.SRCALPHA)
    solid = int(width * fade_from)
    for x in range(width):
        a = alpha if x < solid else int(alpha * (1 - (x - solid) / (width - solid)) ** 1.4)
        pg.draw.line(panel, (0, 0, 0, a), (x, 0), (x, height))
    return panel


def blink(period_ms=400):
    return (pg.time.get_ticks() // period_ms) % 2 == 0


class Hud:
    def __init__(self, game):
        self.game = game
        self.title_font = pg.font.Font(None, 42)
        self.value_font = pg.font.Font(None, 30)
        self.label_font = pg.font.Font(None, 22)
        self.small_font = pg.font.Font(None, 24)
        self.alert_title_font = pg.font.Font(None, 30)
        self.alert_text_font = pg.font.Font(None, 22)
        self.top_panel = gradient_panel(560, 124)
        self.base_panel = gradient_panel(560, 238)
        self.sol_title = render_spaced(self.title_font, "SOL 1", TEXT, 6)
        self.base_title = render_spaced(self.label_font, "ESTADO DE LA BASE", TEXT, 4)
        self.alert_seen = {}  # id de alerta -> momento en que apareció (para la animación de entrada)
        self.sector_cache = {}

    # ------------------------------------------------------------------ principal
    def draw(self):
        screen = self.game.screen
        self.draw_top_left(screen)
        self.draw_base_status(screen)
        self.draw_alerts(screen)
        self.draw_sector_banner(screen)

    def spaced(self, font, text, color, spacing):
        """ render_spaced con caché (los textos del HUD casi no cambian) """
        key = (id(font), text, color, spacing)
        if key not in self.sector_cache:
            if len(self.sector_cache) > 300:
                self.sector_cache.clear()
            self.sector_cache[key] = render_spaced(font, text, color, spacing)
        return self.sector_cache[key]

    # ------------------------------------------------------------------ arriba a la izquierda
    def draw_top_left(self, screen):
        game = self.game
        screen.blit(self.top_panel, (0, 0))
        x, y = 26, 18
        screen.blit(self.sol_title, (x, y))
        pg.draw.line(screen, RED, (x, y + 42), (x + 300, y + 42), 3)

        seconds = math.ceil(game.time_left)
        urgent = seconds <= 30
        color = RED if urgent and blink(500) else TEXT
        label = self.spaced(self.label_font, "FIN DEL SOL", TEXT_DIM, 3)
        lx = x + self.sol_title.get_width() + 28
        screen.blit(label, (lx, y + 2))
        screen.blit(self.value_font.render(f"{seconds // 60}:{seconds % 60:02d}", True, color), (lx, y + 18))

        if game.current_sector is not None:
            sector = SECTORS[game.current_sector]
            pg.draw.rect(screen, sector["color"], (x, y + 58, 12, 12))
            screen.blit(self.spaced(self.label_font, sector["name"].upper(), TEXT, 3), (x + 22, y + 57))
        screen.blit(self.spaced(self.label_font, "PUNTOS", TEXT_DIM, 3), (x, y + 82))
        screen.blit(self.small_font.render(str(game.score), True, TEXT), (x + 92, y + 80))

    # ------------------------------------------------------------------ abajo a la izquierda
    def draw_base_status(self, screen):
        game = self.game
        r = game.resources
        top = screen.get_height() - self.base_panel.get_height()
        screen.blit(self.base_panel, (0, top))
        x, y = 26, top + 16
        screen.blit(self.base_title, (x, y))
        pg.draw.line(screen, RED, (x, y + 22), (x + 300, y + 22), 2)
        y += 36

        rows = [
            ("ENERGÍA", r.energy, 100, ENERGY_COLOR, f"{int(r.energy)}%", r.energy < LOW_LEVEL),
            ("OXÍGENO", r.oxygen, 100, OXYGEN_COLOR, f"{int(r.oxygen)}%", r.oxygen < LOW_LEVEL),
            ("BLINDAJE", r.shield, 100, SHIELD_COLOR, f"{int(r.shield)}%", False),
            ("RADIACIÓN", r.radiation, r.radiation_limit, RADIATION_COLOR,
             f"{int(r.radiation)}/{r.radiation_limit}", r.radiation > r.radiation_limit * 0.75),
        ]
        for label, value, maximum, color, text, warn in rows:
            self.draw_bar_row(screen, x, y, label, value / maximum, color, text, warn)
            y += 30

        # Comida: una casilla por ración de la meta
        greenhouse = game.greenhouse_mission
        screen.blit(self.spaced(self.label_font, "COMIDA", TEXT, 3), (x, y + 2))
        size, gap = 18, 6
        for i in range(greenhouse.food_goal):
            box = pg.Rect(x + 130 + i * (size + gap), y, size, size)
            pg.draw.rect(screen, FOOD_COLOR if i < greenhouse.food else BAR_BG, box)
            pg.draw.rect(screen, (90, 90, 90), box, 1)
        done = greenhouse.food >= greenhouse.food_goal
        text = f"{greenhouse.food}/{greenhouse.food_goal}" + ("  META" if done else "")
        screen.blit(self.small_font.render(text, True, FOOD_COLOR if done else TEXT),
                    (x + 130 + greenhouse.food_goal * (size + gap) + 8, y))

    def draw_bar_row(self, screen, x, y, label, fraction, color, text, warn):
        label_color = RED if warn and blink(300) else TEXT
        screen.blit(self.spaced(self.label_font, label, label_color, 3), (x, y + 2))
        bar = pg.Rect(x + 130, y + 5, 240, 10)
        pg.draw.rect(screen, BAR_BG, bar)
        if not warn or blink(300):
            pg.draw.rect(screen, color, (bar.x, bar.y, int(bar.width * max(0.0, min(1.0, fraction))), bar.height))
        for i in range(1, 4):  # Marcas cada 25%
            tick_x = bar.x + bar.width * i // 4
            pg.draw.line(screen, (0, 0, 0), (tick_x, bar.y), (tick_x, bar.bottom - 1), 1)
        screen.blit(self.small_font.render(text, True, label_color), (bar.right + 12, y))

    # ------------------------------------------------------------------ alertas (arriba a la derecha)
    def collect_alerts(self):
        game = self.game
        candidates = [mission.get_alert() for mission in game.missions[:2]]
        candidates.append(game.resources.get_alert())
        candidates.extend(mission.get_alert() for mission in game.missions[2:])
        return [a for a in candidates if a][:3]  # Como máximo 3 a la vez

    def draw_alerts(self, screen):
        alerts = self.collect_alerts()
        now = pg.time.get_ticks()
        ids = [alert.get("id", alert["title"]) for alert in alerts]
        self.alert_seen = {key: self.alert_seen.get(key, now) for key in ids}

        right = screen.get_width() - 20
        y = 20 + self.game.minimap_base.get_height() + 18
        for alert, key in zip(alerts, ids):
            card = self.render_alert(alert)
            progress = min(1.0, (now - self.alert_seen[key]) / ALERT_SLIDE_MS)
            ease = 1 - (1 - progress) ** 3
            x = right - card.get_width() + int((1 - ease) * (card.get_width() + 40))
            screen.blit(card, (x, y))
            y += card.get_height() + 10

    def render_alert(self, alert):
        """ Tarjeta de alerta: holograma de lo que representa a la izquierda, título y texto corto a la derecha """
        kind, color = alert_icon(alert)
        width = ALERT_WIDTH
        icon_w = 104
        inner_x, inner_w = icon_w + 8, width - icon_w - 22
        title_lines = wrap_text(self.alert_title_font, alert["title"].upper(), inner_w)
        hint_lines = wrap_text(self.alert_text_font, alert["hint"], inner_w)[:3]
        title_h = self.alert_title_font.get_linesize()
        hint_h = self.alert_text_font.get_linesize()
        height = max(110, 14 + len(title_lines) * title_h + 6 + len(hint_lines) * hint_h + 12)

        card = pg.Surface((width, height), pg.SRCALPHA)
        card.fill((0, 0, 0, 190))

        # Holograma flotando sobre un mini proyector (en una capa aparte para que la transparencia se mezcle bien)
        t = pg.time.get_ticks() / 1000
        icon_layer = pg.Surface((icon_w, height), pg.SRCALPHA)
        base_y = height // 2 + 36
        draw_projector(icon_layer, icon_w // 2, base_y, 70, 76, color, t)
        holo = alert_hologram(kind, 84, color, t)
        icon_layer.blit(holo, holo.get_rect(center=(icon_w // 2, height // 2 - 4 + math.sin(t * 2.4) * 3)))
        card.blit(icon_layer, (0, 0))

        y = 14
        for line in title_lines:
            card.blit(self.alert_title_font.render(line, True, TEXT), (inner_x, y))
            y += title_h
        y += 6
        for line in hint_lines:
            card.blit(self.alert_text_font.render(line, True, (195, 195, 195)), (inner_x, y))
            y += hint_h
        return card

    # ------------------------------------------------------------------ nombre del sector
    def draw_sector_banner(self, screen):
        game = self.game
        remaining = game.sector_message_timer - pg.time.get_ticks()
        if not game.sector_message or remaining <= 0:
            return
        elapsed = SECTOR_BANNER_MS - remaining
        alpha = min(1.0, elapsed / 400, remaining / 600)

        label = self.spaced(self.label_font, "SECTOR", RED, 6)
        name = self.spaced(self.title_font, game.sector_message.upper(), TEXT, 8)
        width = max(label.get_width(), name.get_width()) + 80
        banner = pg.Surface((width, 96), pg.SRCALPHA)
        for x in range(width):
            # Fondo que se desvanece hacia ambos lados
            a = int(170 * (1 - abs(x - width / 2) / (width / 2)) ** 0.8)
            pg.draw.line(banner, (0, 0, 0, a), (x, 0), (x, 96))
        banner.blit(label, label.get_rect(midtop=(width // 2, 10)))
        banner.blit(name, name.get_rect(midtop=(width // 2, 34)))
        pg.draw.line(banner, RED, (width // 2 - name.get_width() // 2, 78), (width // 2 + name.get_width() // 2, 78), 3)
        banner.set_alpha(int(255 * alpha))
        screen.blit(banner, banner.get_rect(midtop=(screen.get_width() // 2, 130)))


# ====================================================================== hologramas de las alertas
# Cada alerta se representa con el holograma de lo que trata. Se elige por el "id" de la alerta
# (o por "icon" si la alerta lo trae), así las misiones no necesitan saber nada del dibujo.
ALERT_ICONS = {
    "energy": ("energy", (255, 210, 60)),           # Tanque de energía en reserva: rayo amarillo
    "energy_critical": ("oxygen", (235, 70, 70)),    # Energía crítica: el oxígeno está en peligro
    "storm_warning": ("dome", (255, 140, 0)),        # Tormenta en camino: cúpula del escudo
    "storm_impact": ("dome", (255, 191, 0)),         # Impacto de radiación
    "harvest": ("food", (90, 255, 140)),             # Cosecha lista: lechuga verde
    "comms": ("letter", (90, 180, 255)),             # Mensaje de la Tierra: carta
}
_icon_cache = {}


def alert_icon(alert):
    """ (tipo de holograma, color) para una alerta """
    if "icon" in alert:
        return alert["icon"], alert["color"]
    return ALERT_ICONS.get(alert.get("id"), ("energy", alert["color"]))


def _icon_drawing(kind, size):
    """ Dibujo en blanco del icono (luego se tiñe y se convierte en holograma). Se guarda en caché. """
    key = (kind, size)
    if key in _icon_cache:
        return _icon_cache[key]
    S = size
    surf = pg.Surface((S, S), pg.SRCALPHA)
    fill, line = (255, 255, 255, 90), (255, 255, 255, 255)
    if kind == "energy":
        bolt = [(0.60, 0.04), (0.20, 0.56), (0.46, 0.56), (0.34, 0.96), (0.82, 0.40), (0.55, 0.40), (0.70, 0.04)]
        points = [(x * S, y * S) for x, y in bolt]
        pg.draw.polygon(surf, fill, points)
        pg.draw.polygon(surf, line, points, 3)
    elif kind == "dome":
        cx, base, r = S / 2, S * 0.80, S * 0.42
        pg.draw.ellipse(surf, fill, (cx - r - 3, base - 6, 2 * r + 6, 12))
        pg.draw.circle(surf, (255, 255, 255, 50), (cx, base), r, draw_top_left=True, draw_top_right=True)
        pg.draw.arc(surf, line, (cx - r, base - r, 2 * r, 2 * r), 0, math.pi, 3)
        for k in (0.35, 0.7):
            w = r * k
            pg.draw.arc(surf, (255, 255, 255, 170), (cx - w, base - r, 2 * w, 2 * r), 0, math.pi, 1)
        for h in (0.35, 0.7):
            half = math.sqrt(1 - h * h) * r
            pg.draw.line(surf, (255, 255, 255, 150), (cx - half, base - h * r), (cx + half, base - h * r), 1)
        pg.draw.rect(surf, line, (cx - 4, base - r * 0.55, 8, r * 0.45), 2)           # Estación dentro del domo
        pg.draw.line(surf, line, (cx - 14, base - r * 0.4), (cx + 14, base - r * 0.4), 2)
    elif kind == "letter":
        env = pg.Rect(S * 0.10, S * 0.26, S * 0.80, S * 0.50)
        pg.draw.rect(surf, fill, env, border_radius=4)
        pg.draw.rect(surf, line, env, 3, border_radius=4)
        pg.draw.lines(surf, line, False, [env.topleft, (env.centerx, env.top + env.height * 0.55), env.topright], 3)
        earth = (int(env.right - 4), int(env.bottom - 2))                              # Sello con la Tierra
        pg.draw.circle(surf, (255, 255, 255, 160), earth, int(S * 0.13))
        pg.draw.circle(surf, line, earth, int(S * 0.13), 2)
        pg.draw.ellipse(surf, line, (earth[0] - S * 0.07, earth[1] - S * 0.06, S * 0.08, S * 0.06))
    elif kind == "oxygen":
        for (x, y, r) in ((0.42, 0.55, 0.30), (0.78, 0.30, 0.13), (0.80, 0.70, 0.09), (0.20, 0.18, 0.08)):
            pg.draw.circle(surf, fill, (x * S, y * S), r * S)
            pg.draw.circle(surf, line, (x * S, y * S), r * S, 2)
        label = pg.font.Font(None, int(S * 0.36)).render("O2", True, line)
        surf.blit(label, label.get_rect(center=(0.42 * S, 0.56 * S)))
    _icon_cache[key] = surf
    return surf


def alert_hologram(kind, size, color, t):
    """ Holograma del icono de una alerta: tinte del color, líneas, parpadeo y un leve giro """
    if kind == "food":
        return render_hologram("lechuga", size, color, 100, t)
    return hologramize(_icon_drawing(kind, size), color, t, width_scale=0.82 + 0.18 * abs(math.cos(t * 1.4)))
