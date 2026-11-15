"""
Misión 3: cosecha en el invernadero.

Hay una consola por cultivo, en fila, dentro del sector "Invernadero y Laboratorio". Cada consola tiene
una interfaz holográfica propia (color y tipo de medidor distintos) y muestra un holograma de la planta
que va creciendo. Las plantas se dibujan con figuras de pygame (no usan imágenes).
"""
import math
import random
import pygame as pg
from settings import GREENHOUSE, TILE
from nasa_data import PLANTS, GREENHOUSE_SOURCES
from menu import render_spaced, wrap_text
from controls import CONTROLS

LIGHT_NAMES = ["APAGADA", "BAJA", "MEDIA", "ALTA"]
LIGHT_SPEED = [0, 1 / 3, 2 / 3, 1]  # Con luz baja tarda 3 veces más que con alta; con media, 1.5 veces

PLANT_GREEN = (70, 210, 90)
WARN_YELLOW = (255, 200, 0)
ALERT_RED = (235, 60, 60)
PANEL_BG = (6, 14, 28, 232)

# Cada consola tiene su propia apariencia: color del holograma y tipo de medidor de crecimiento
THEMES = {
    "lechuga": {"color": (90, 255, 170), "gauge": "ring", "code": "A"},
    "mizuna": {"color": (110, 200, 255), "gauge": "tube", "code": "B"},
    "chile": {"color": (255, 150, 80), "gauge": "hex", "code": "C"},
}


def blink(period_ms=500):
    return (pg.time.get_ticks() // period_ms) % 2 == 0


def growth_stage(crop):
    if crop["ready"]:
        return "LISTA PARA COSECHAR"
    if crop["growth"] < 35:
        return "BROTE"
    return "CRECIENDO"


# ====================================================================== hologramas de las plantas
# Las figuras se dibujan en blanco y luego se tiñen del color de la consola.
WHITE_FILL = (255, 255, 255, 70)
WHITE_LINE = (255, 255, 255, 255)
WHITE_SOFT = (255, 255, 255, 150)


def _leaf_surface(length, width):
    """ Hoja ovalada apuntando hacia arriba, con nervaduras """
    length, width = max(4, int(length)), max(3, int(width))
    surf = pg.Surface((width + 4, length + 4), pg.SRCALPHA)
    rect = pg.Rect(2, 2, width, length)
    pg.draw.ellipse(surf, WHITE_FILL, rect)
    pg.draw.ellipse(surf, WHITE_LINE, rect, 2)
    pg.draw.line(surf, WHITE_SOFT, (rect.centerx, rect.bottom - 2), (rect.centerx, rect.top + length * 0.15), 1)
    for f in (0.35, 0.55, 0.75):
        y = rect.top + length * f
        pg.draw.line(surf, WHITE_SOFT, (rect.centerx, y), (rect.centerx - width * 0.32, y - length * 0.08), 1)
        pg.draw.line(surf, WHITE_SOFT, (rect.centerx, y), (rect.centerx + width * 0.32, y - length * 0.08), 1)
    return surf


def _blit_leaf(target, leaf, base_point, angle_deg):
    """ Gira la hoja alrededor de su base y la coloca con la base en base_point """
    w, h = leaf.get_size()
    padded = pg.Surface((w, h * 2), pg.SRCALPHA)
    padded.blit(leaf, (0, 0))  # Así la base de la hoja queda en el centro de la superficie
    rotated = pg.transform.rotate(padded, angle_deg)
    target.blit(rotated, rotated.get_rect(center=base_point))


def draw_lettuce(surf, size, k):
    """ Lechuga: una roseta de hojas anchas """
    base = (size / 2, size * 0.84)
    for angles, length, width in (((-66, -44, -22, 22, 44, 66), 0.50, 0.21),
                                  ((-30, 0, 30), 0.44, 0.19),
                                  ((-10, 10), 0.34, 0.15)):
        leaf = _leaf_surface(size * length * k, size * width * k)
        for angle in angles:
            _blit_leaf(surf, leaf, base, angle)


def draw_mizuna(surf, size, k):
    """ Mizuna: tallos delgados con hojas dentadas, abiertos en abanico """
    bx, by = size / 2, size * 0.88
    for i, deg in enumerate((-58, -38, -18, 2, 22, 42, 60)):
        a = math.radians(deg)
        length = size * (0.55 + 0.1 * math.sin(i * 1.7)) * k
        dx, dy = math.sin(a), -math.cos(a)
        px, py = math.cos(a), math.sin(a)
        pg.draw.line(surf, WHITE_LINE, (bx, by), (bx + dx * length, by + dy * length), 2)
        left, right = [], []
        steps = 9
        for j in range(steps):
            t = 0.3 + 0.7 * j / (steps - 1)
            w = size * 0.075 * k * math.sin(math.pi * (t - 0.3) / 0.7) * (1.0 if j % 2 == 0 else 0.5)
            cx, cy = bx + dx * length * t, by + dy * length * t
            left.append((cx + px * w, cy + py * w))
            right.append((cx - px * w, cy - py * w))
        outline = left + right[::-1]
        if len(outline) >= 3:
            pg.draw.polygon(surf, WHITE_FILL, outline)
            pg.draw.polygon(surf, WHITE_LINE, outline, 1)


def _pepper(surf, x0, y0, size, k, side):
    """ Un chile curvo colgando desde (x0, y0) """
    spine = []
    for i in range(14):
        t = i / 13
        spine.append((x0 + side * math.sin(t * 1.3) * size * 0.14 * k, y0 + t * size * 0.55 * k))
    left, right = [], []
    for i, (x, y) in enumerate(spine):
        t = i / 13
        nx, ny = spine[min(i + 1, 13)][0] - spine[max(i - 1, 0)][0], spine[min(i + 1, 13)][1] - spine[max(i - 1, 0)][1]
        norm = math.hypot(nx, ny) or 1
        nx, ny = -ny / norm, nx / norm
        w = size * 0.085 * k * (1 - t ** 1.7) + 1
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    outline = left + right[::-1]
    pg.draw.polygon(surf, WHITE_FILL, outline)
    pg.draw.polygon(surf, WHITE_LINE, outline, 2)
    # Brillo y tallo
    pg.draw.lines(surf, WHITE_SOFT, False, [(x - side * 3, y) for x, y in spine[2:9]], 1)
    pg.draw.ellipse(surf, WHITE_LINE, (x0 - size * 0.06 * k, y0 - size * 0.03 * k, size * 0.12 * k, size * 0.06 * k), 2)
    pg.draw.line(surf, WHITE_LINE, (x0, y0 - size * 0.02 * k), (x0 - side * size * 0.05 * k, y0 - size * 0.12 * k), 2)


def draw_chile(surf, size, k):
    """ Chile: dos chiles colgando de una rama con hojas """
    top = size * 0.18
    pg.draw.line(surf, WHITE_LINE, (size * 0.2, top), (size * 0.8, top + size * 0.04), 2)
    leaf = _leaf_surface(size * 0.22 * k, size * 0.1 * k)
    for x, angle in ((0.3, 50), (0.5, -40), (0.7, 35)):
        _blit_leaf(surf, leaf, (size * x, top + size * 0.02), angle)
    _pepper(surf, size * 0.38, top + size * 0.06, size, k, -1)
    _pepper(surf, size * 0.62, top + size * 0.08, size, k, 1)


SHAPES = {"lechuga": draw_lettuce, "mizuna": draw_mizuna, "chile": draw_chile}
_shape_cache = {}
_scanline_cache = {}


def _scanlines(size):
    """ Máscara con líneas horizontales para el efecto de holograma """
    if size not in _scanline_cache:
        mask = pg.Surface((size, size), pg.SRCALPHA)
        mask.fill((255, 255, 255, 255))
        for y in range(0, size, 3):
            pg.draw.line(mask, (255, 255, 255, 80), (0, y), (size, y))
        _scanline_cache[size] = mask
    return _scanline_cache[size]


def render_hologram(kind, size, color, growth, t):
    """ Devuelve la imagen del holograma de la planta: crece con el cultivo, gira, parpadea y tiene líneas """
    k = 0.35 + 0.65 * growth / 100
    key = (kind, size, int(k * 20))
    if key not in _shape_cache:
        base = pg.Surface((size, size), pg.SRCALPHA)
        SHAPES[kind](base, size, int(k * 20) / 20)
        _shape_cache[key] = base
    base = _shape_cache[key]

    # Giro falso en 3D: se estrecha y se ensancha
    return hologramize(base, color, t, width_scale=max(0.25, abs(math.cos(t * 1.1))))


def hologramize(base, color, t, width_scale=1.0):
    """ Convierte un dibujo blanco en holograma: lo tiñe, le pone líneas horizontales,
    una franja brillante que lo recorre y un parpadeo. width_scale < 1 lo estrecha (efecto de giro). """
    w, h = base.get_size()
    width = max(2, int(w * width_scale))
    img = pg.transform.smoothscale(base, (width, h)) if width != w else base.copy()
    tint = pg.Surface(img.get_size(), pg.SRCALPHA)
    tint.fill((*color, 255))
    img.blit(tint, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
    img.blit(_scanlines(max(w, h)), (0, 0), area=pg.Rect(0, 0, width, h), special_flags=pg.BLEND_RGBA_MULT)
    band = int((t * 70) % h)
    pg.draw.line(img, (*color, 160), (0, band), (width, band), 2)
    flicker = 0.4 if random.random() < 0.03 else 0.82 + 0.18 * random.random()
    img.set_alpha(int(255 * flicker))
    return img


def draw_projector(surface, cx, base_y, width, height, color, t):
    """ Proyector del holograma: cono de luz, base brillante y anillos que suben """
    cone = [(cx - width * 0.12, base_y), (cx - width * 0.5, base_y - height),
            (cx + width * 0.5, base_y - height), (cx + width * 0.12, base_y)]
    pg.draw.polygon(surface, (*color, 28), cone)
    for i in range(3):
        phase = (t * 0.5 + i / 3) % 1
        ring_w = width * (0.25 + 0.6 * phase)
        y = base_y - phase * height * 0.85
        pg.draw.ellipse(surface, (*color, int(130 * (1 - phase))), (cx - ring_w / 2, y - ring_w * 0.08, ring_w, ring_w * 0.16), 1)
    emitter = pg.Rect(0, 0, width * 0.42, max(8, width * 0.08))
    emitter.center = (cx, base_y)
    pg.draw.ellipse(surface, (*color, 70), emitter)
    pg.draw.ellipse(surface, (*color, 230), emitter, 2)


def draw_sun(surface, center, radius, lit, color):
    """ Icono de luz: un sol encendido (amarillo) o apagado (contorno) """
    cx, cy = center
    sun_color = WARN_YELLOW if lit else color
    for i in range(8):
        a = i * math.pi / 4
        start = (cx + math.cos(a) * radius * 1.35, cy + math.sin(a) * radius * 1.35)
        end = (cx + math.cos(a) * radius * 1.8, cy + math.sin(a) * radius * 1.8)
        pg.draw.line(surface, (*sun_color, 255 if lit else 90), start, end, 2)
    pg.draw.circle(surface, (*sun_color, 255 if lit else 40), center, radius, 0)
    pg.draw.circle(surface, (*sun_color, 255 if lit else 120), center, radius, 2)


# ====================================================================== misión
class GreenhouseMission:
    """ Cada cultivo tiene su consola y un nivel de luz (0 a 3):
      - más luz: crece más rápido y las plantas dan un poco de oxígeno
      - pero cada nivel de luz encendido gasta energía todo el tiempo
    Cuando un cultivo está listo hay que ir a su consola a cosecharlo (deja de crecer hasta entonces).
    Para cumplir la misión hay que juntar food_goal raciones antes de que termine el sol.
    """

    def __init__(self, game):
        self.game = game
        self.cfg = GREENHOUSE
        self.food = 0
        self.food_goal = self.cfg["food_goal"]
        self.crops = []
        for crop_cfg in self.cfg["crops"]:
            crop = {
                **crop_cfg,
                "name": PLANTS[crop_cfg["id"]]["name"],
                "fact": PLANTS[crop_cfg["id"]]["fact"],
                "light": self.cfg["start_light"],
                "growth": 0.0,
                "ready": False,
                "x": crop_cfg["cell"][0] + 0.5,
                "y": crop_cfg["cell"][1] + 0.5,
            }
            crop["console"] = HoloConsole(game, self, crop)
            self.crops.append(crop)
        self.label_font = pg.font.Font(None, 26)
        self.prompt_font = pg.font.Font(None, 34)

    @property
    def total_light(self):
        return sum(crop["light"] for crop in self.crops)

    def energy_drain(self):
        """ Energía por segundo que gastan todas las luces encendidas """
        return self.total_light * self.cfg["energy_per_light"]

    def oxygen_bonus(self):
        """ Oxígeno por segundo que producen las plantas (solo si hay energía para las luces) """
        if self.game.resources.energy <= 0:
            return 0.0
        return self.total_light * self.cfg["oxygen_per_light"]

    def seconds_to_ready(self, crop):
        speed = LIGHT_SPEED[crop["light"]]
        if crop["ready"] or speed == 0:
            return None
        return (100 - crop["growth"]) / (100 / crop["grow_time"] * speed)

    def update(self, dt_ms):
        dt = dt_ms / 1000
        resources = self.game.resources
        lights_on = resources.energy > 0  # Sin energía las luces se apagan solas
        resources.oxygen = resources.clamp(resources.oxygen + self.oxygen_bonus() * dt)
        resources.energy = resources.clamp(resources.energy - self.energy_drain() * dt)
        if not lights_on:
            return
        for crop in self.crops:
            if crop["ready"]:
                continue
            crop["growth"] += 100 / crop["grow_time"] * LIGHT_SPEED[crop["light"]] * dt
            if crop["growth"] >= 100:
                crop["growth"] = 100.0
                crop["ready"] = True

    def harvest(self, crop):
        if not crop["ready"]:
            return 0
        crop["ready"] = False
        crop["growth"] = 0.0
        self.food += crop["rations"]
        return crop["rations"]

    def any_ready(self):
        return any(crop["ready"] for crop in self.crops)

    def nearest_crop_in_range(self):
        """ El cultivo cuya consola está más cerca del jugador, si está a distancia de interactuar """
        player = self.game.player
        best, best_dist = None, self.cfg["interact_range"]
        for crop in self.crops:
            dist = math.hypot(player.x - crop["x"], player.y - crop["y"])
            if dist <= best_dist:
                best, best_dist = crop, dist
        return best

    def try_interact(self):
        crop = self.nearest_crop_in_range()
        return crop["console"] if crop else None

    def prompt(self):
        """ Aviso de interacción para la vista 3D """
        crop = self.nearest_crop_in_range()
        if not crop:
            return None
        name = crop["name"].split()[0].upper()
        return f"COSECHAR {name}" if crop["ready"] else f"CONSOLA: {name}"

    def billboards(self):
        """ Sprites 3D: un pedestal por cultivo con el holograma de su planta flotando encima """
        t = pg.time.get_ticks() / 1000
        sprites = []
        for crop in self.crops:
            color = THEMES[crop["id"]]["color"]
            surf = pg.Surface((160, 260), pg.SRCALPHA)
            draw_projector(surf, 80, 196, 120, 170, color, t)
            holo = render_hologram(crop["id"], 140, color, crop["growth"], t + crop["cell"][0])
            surf.blit(holo, holo.get_rect(center=(80, 112 + math.sin(t * 2 + crop["cell"][0]) * 5)))
            pedestal = pg.Rect(36, 198, 88, 60)
            pg.draw.rect(surf, (22, 30, 44), pedestal, border_radius=8)
            pg.draw.rect(surf, color, pedestal, 3, border_radius=8)
            bar = pg.Rect(48, 236, 64, 8)
            pg.draw.rect(surf, (10, 15, 20), bar)
            pg.draw.rect(surf, WARN_YELLOW if crop["ready"] else color,
                         (bar.x, bar.y, int(bar.width * crop["growth"] / 100), bar.height))
            sprites.append((crop["x"], crop["y"], surf, 0.85, 0.0, False))
        return sprites

    def failure_reason(self):
        """ Se revisa al terminar el sol """
        if self.food >= self.food_goal:
            return None
        return (f"Terminó el sol, pero solo cosecharon {self.food} de {self.food_goal} raciones de comida. "
                "Las plantas necesitan luz para crecer, y la luz gasta energía: busca el equilibrio.")

    # ------------------------------------------------------------------ dibujo en el mapa
    def draw_world(self):
        screen = self.game.screen
        nearest = self.nearest_crop_in_range()
        t = pg.time.get_ticks() / 1000
        for crop in self.crops:
            sx, sy = self.game.camera.to_screen(*crop["cell"])
            if sx < -TILE or sx > screen.get_width():
                continue
            color = THEMES[crop["id"]]["color"]

            # Pedestal con proyector y holograma pequeño flotando
            overlay = pg.Surface((TILE, TILE), pg.SRCALPHA)
            draw_projector(overlay, TILE // 2, 66, 56, 50, color, t)
            pg.draw.rect(overlay, (18, 26, 40, 255), (22, 68, 56, 24), border_radius=6)
            pg.draw.rect(overlay, (*color, 255), (22, 68, 56, 24), 2, border_radius=6)
            screen.blit(overlay, (sx, sy))
            holo = render_hologram(crop["id"], 58, color, crop["growth"], t + crop["cell"][0])
            bob = math.sin(t * 2 + crop["cell"][0]) * 3
            screen.blit(holo, holo.get_rect(center=(sx + TILE // 2, sy + 34 + bob)))

            # Barra de crecimiento debajo del pedestal
            bar = pg.Rect(sx + 18, sy + 95, TILE - 36, 6)
            pg.draw.rect(screen, (20, 25, 30), bar)
            pg.draw.rect(screen, WARN_YELLOW if crop["ready"] else color,
                         (bar.x, bar.y, int(bar.width * crop["growth"] / 100), bar.height))

            label_color = WARN_YELLOW if crop["ready"] and blink(300) else color
            label = self.label_font.render(crop["name"].split()[0].upper(), True, label_color)
            screen.blit(label, (sx + TILE // 2 - label.get_width() // 2, sy - 8))

            if crop is nearest:
                key = CONTROLS.label("interact")
                text = f"[{key}] COSECHAR" if crop["ready"] else f"[{key}] {crop['name'].split()[0].upper()}"
                prompt = self.prompt_font.render(text, True, WARN_YELLOW)
                box = prompt.get_rect(center=(sx + TILE // 2, sy + TILE + 24)).inflate(16, 8)
                pg.draw.rect(screen, (0, 0, 0), box, border_radius=6)
                screen.blit(prompt, prompt.get_rect(center=box.center))

    def get_alert(self):
        ready = [crop["name"].split()[0].lower() for crop in self.crops if crop["ready"]]
        if not ready:
            return None
        return {
            "id": "harvest",
            "tag": "INVERNADERO",
            "title": "¡Cosecha lista!",
            "hint": f"Lista: {', '.join(ready)}. Cosecha en su consola del módulo de Cultivos "
                    f"({CONTROLS.label('interact')}); si no, deja de crecer.",
            "color": PLANT_GREEN,
        }

    def draw_minimap_marker(self, x0, y0, cell):
        for crop in self.crops:
            if crop["ready"] and not blink(300):
                continue
            color = WARN_YELLOW if crop["ready"] else THEMES[crop["id"]]["color"]
            pg.draw.rect(self.game.screen, color, (x0 + crop["cell"][0] * cell, y0 + crop["cell"][1] * cell, cell, cell))

# ====================================================================== consola holográfica
class HoloConsole:
    """ Consola holográfica de un cultivo: holograma de la planta a la izquierda y controles a la derecha.
    Cada cultivo usa un color y un medidor distinto (anillo, tubo o hexágonos) según THEMES. """

    WIDTH, HEIGHT = 980, 620
    OPEN_MS = 260
    HARVEST_MS = 900

    def __init__(self, game, mission, crop):
        self.game = game
        self.mission = mission
        self.crop = crop
        self.theme = THEMES[crop["id"]]
        self.color = self.theme["color"]
        self.title = render_spaced(pg.font.Font(None, 46), crop["name"].upper(), self.color, 5)
        self.code_font = pg.font.Font(None, 26)
        self.label_font = pg.font.Font(None, 32)
        self.small_font = pg.font.Font(None, 25)
        self.big_font = pg.font.Font(None, 54)
        self.ring_font = pg.font.Font(None, 44)
        self.opened_at = 0
        self.harvest_at = None
        self.harvest_amount = 0
        self.grid = self.build_grid()

    def build_grid(self):
        grid = pg.Surface((self.WIDTH, self.HEIGHT), pg.SRCALPHA)
        for x in range(0, self.WIDTH, 28):
            pg.draw.line(grid, (*self.color, 14), (x, 0), (x, self.HEIGHT))
        for y in range(0, self.HEIGHT, 28):
            pg.draw.line(grid, (*self.color, 14), (0, y), (self.WIDTH, y))
        return grid

    def start(self):
        self.opened_at = pg.time.get_ticks()
        self.harvest_at = None

    def update(self, dt_ms):
        pass

    def handle_event(self, event):
        if event.type != pg.KEYDOWN:
            return
        crop = self.crop
        if event.key in (pg.K_RIGHT, pg.K_d, pg.K_UP, pg.K_w):
            crop["light"] = min(3, crop["light"] + 1)
        elif event.key in (pg.K_LEFT, pg.K_a, pg.K_DOWN, pg.K_s):
            crop["light"] = max(0, crop["light"] - 1)
        elif event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
            rations = self.mission.harvest(crop)
            if rations:
                CONTROLS.rumble(0.3, 0.3, 150)
                self.harvest_at = pg.time.get_ticks()
                self.harvest_amount = rations
        elif event.key == pg.K_ESCAPE:
            self.game.close_terminal()

    # ------------------------------------------------------------------ dibujo
    def draw(self, screen):
        panel = self.render_panel()
        progress = min(1.0, (pg.time.get_ticks() - self.opened_at) / self.OPEN_MS)
        if progress < 1:
            # Se abre desde una línea horizontal, parpadeando como un holograma que se enciende
            ease = 1 - (1 - progress) ** 3
            panel = pg.transform.smoothscale(panel, (self.WIDTH, max(6, int(self.HEIGHT * ease))))
            panel.set_alpha(random.randint(120, 255))
        screen.blit(panel, panel.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2)))

    def render_panel(self):
        W, H, color = self.WIDTH, self.HEIGHT, self.color
        background = pg.Surface((W, H), pg.SRCALPHA)
        pg.draw.rect(background, PANEL_BG, background.get_rect(), border_radius=16)
        background.blit(self.grid, (0, 0))
        # Todo el contenido se dibuja en una capa transparente aparte y luego se mezcla con el fondo:
        # en pygame, dibujar figuras semitransparentes directo sobre el fondo reemplazaría su opacidad.
        panel = pg.Surface((W, H), pg.SRCALPHA)
        pg.draw.rect(panel, (*color, 170), panel.get_rect(), 2, border_radius=16)
        for cx, cy, dx, dy in ((0, 0, 1, 1), (W - 1, 0, -1, 1), (0, H - 1, 1, -1), (W - 1, H - 1, -1, -1)):
            pg.draw.line(panel, (*color, 255), (cx + dx * 8, cy + dy * 8), (cx + dx * 50, cy + dy * 8), 4)
            pg.draw.line(panel, (*color, 255), (cx + dx * 8, cy + dy * 8), (cx + dx * 8, cy + dy * 50), 4)

        # Encabezado
        chip = pg.Rect(30, 26, 120, 30)
        pg.draw.rect(panel, (*color, 60), chip, border_radius=6)
        pg.draw.rect(panel, (*color, 255), chip, 2, border_radius=6)
        code = self.code_font.render(f"CULTIVO {self.theme['code']}", True, color)
        panel.blit(code, code.get_rect(center=chip.center))
        panel.blit(self.title, (170, 24))
        panel.blit(self.small_font.render("MÓDULO HOLOGRÁFICO DE CRECIMIENTO  //  MÓDULO DE CULTIVOS",
                                          True, (*color, 160)), (170, 64))
        pg.draw.line(panel, (*color, 120), (30, 96), (W - 30, 96), 1)

        self.draw_hologram_area(panel)
        self.draw_controls(panel, 450)

        labels = CONTROLS.labels()
        footer = self.small_font.render(f"[{labels['adjust']}] Luz      [{labels['confirm']}] Cosechar      "
                                        f"[{labels['back']}] Salir", True, (200, 210, 220))
        panel.blit(footer, footer.get_rect(center=(W // 2, H - 26)))
        background.blit(panel, (0, 0))
        return background

    def draw_hologram_area(self, panel):
        crop, color = self.crop, self.color
        t = pg.time.get_ticks() / 1000
        area = pg.Rect(30, 112, 390, 400)
        pg.draw.rect(panel, (*color, 40), area, 1, border_radius=10)
        cx, base_y = area.centerx, area.bottom - 60
        draw_projector(panel, cx, base_y, 300, 300, color, t)

        size = 250
        harvest_age = None if self.harvest_at is None else pg.time.get_ticks() - self.harvest_at
        if harvest_age is not None and harvest_age < self.HARVEST_MS:
            # Al cosechar: destello y la planta desaparece hacia arriba
            size = int(250 * (1 + harvest_age / self.HARVEST_MS * 0.4))
        holo = render_hologram(crop["id"], size, color, 100 if harvest_age is not None and harvest_age < self.HARVEST_MS
                               else crop["growth"], t)
        if harvest_age is not None and harvest_age < self.HARVEST_MS:
            holo.set_alpha(int(255 * (1 - harvest_age / self.HARVEST_MS)))
        bob = math.sin(t * 2) * 6
        panel.blit(holo, holo.get_rect(center=(cx, base_y - 150 + bob)))

        if harvest_age is not None and harvest_age < self.HARVEST_MS * 1.6:
            rise = harvest_age / 20
            plus = self.big_font.render(f"+{self.harvest_amount} COMIDA", True, WARN_YELLOW)
            panel.blit(plus, plus.get_rect(center=(cx, area.top + 70 - rise)))

        stage = growth_stage(crop)
        stage_color = WARN_YELLOW if crop["ready"] else color
        text = self.small_font.render(f"ETAPA: {stage}", True, stage_color)
        panel.blit(text, text.get_rect(center=(cx, area.bottom - 28)))

        y = area.bottom + 10
        for line in wrap_text(self.small_font, GREENHOUSE_SOURCES, area.width):
            panel.blit(self.small_font.render(line, True, (150, 165, 180)), (area.x, y))
            y += self.small_font.get_linesize()

    def draw_controls(self, panel, x0):
        crop, color, mission = self.crop, self.color, self.mission
        width = self.WIDTH - x0 - 30

        # Luz
        panel.blit(self.label_font.render("LUZ", True, color), (x0, 122))
        for level in range(3):
            draw_sun(panel, (x0 + 95 + level * 58, 133), 11, level < crop["light"], color)
        panel.blit(self.label_font.render(LIGHT_NAMES[crop["light"]], True, color), (x0 + 270, 122))

        # Medidor de crecimiento (distinto en cada consola)
        gauge = pg.Rect(x0, 170, width, 150)
        getattr(self, f"draw_gauge_{self.theme['gauge']}")(panel, gauge)

        # Botón de cosecha
        button = pg.Rect(x0, 334, width, 56)
        if crop["ready"]:
            pulse = 0.6 + 0.4 * (math.sin(pg.time.get_ticks() / 150) + 1) / 2
            pg.draw.rect(panel, (*color, int(255 * pulse)), button, border_radius=10)
            label = self.label_font.render(f"[{CONTROLS.label('confirm')}] COSECHAR   +{crop['rations']} COMIDA",
                                           True, (5, 15, 25))
        else:
            pg.draw.rect(panel, (*color, 70), button, 2, border_radius=10)
            label = self.label_font.render("COSECHAR  (todavía no está lista)", True, (*color, 120))
        panel.blit(label, label.get_rect(center=button.center))

        # Costo de la luz de este cultivo
        energy = crop["light"] * GREENHOUSE["energy_per_light"] * 60
        oxygen = crop["light"] * GREENHOUSE["oxygen_per_light"] * 60
        y = 402
        for line in wrap_text(self.small_font, f"Esta luz gasta {energy:.1f} de energía por minuto "
                                               f"y las plantas dan +{oxygen:.1f} de oxígeno por minuto.", width):
            panel.blit(self.small_font.render(line, True, (220, 225, 230)), (x0, y))
            y += self.small_font.get_linesize()
        panel.blit(self.small_font.render(
            f"Comida de la base: {mission.food} de {mission.food_goal} raciones", True, WARN_YELLOW), (x0, y + 4))

        y += 36
        fact_color = tuple(min(255, c // 2 + 110) for c in color)
        for line in wrap_text(self.small_font, crop["fact"], width):
            panel.blit(self.small_font.render(line, True, fact_color), (x0, y))
            y += self.small_font.get_linesize()

    def status_text(self):
        crop = self.crop
        if crop["ready"]:
            return "¡LISTA PARA COSECHAR!", WARN_YELLOW if blink(400) else self.color
        if crop["light"] == 0:
            return "SIN LUZ: NO CRECE", ALERT_RED
        return f"Lista en {math.ceil(self.mission.seconds_to_ready(crop))} s", self.color

    def draw_status(self, panel, x, y):
        text, color = self.status_text()
        panel.blit(self.label_font.render(text, True, color), (x, y))
        rations = f"{self.crop['rations']} ración por cosecha" if self.crop["rations"] == 1 \
            else f"{self.crop['rations']} raciones por cosecha"
        panel.blit(self.small_font.render(rations, True, (180, 190, 200)), (x, y + 34))

    def draw_gauge_ring(self, panel, area):
        """ Lechuga: anillo circular de crecimiento """
        crop, color = self.crop, self.color
        center, radius = (area.x + 75, area.centery), 64
        rect = pg.Rect(0, 0, radius * 2, radius * 2)
        rect.center = center
        pg.draw.circle(panel, (*color, 40), center, radius, 12)
        progress = crop["growth"] / 100
        if progress > 0:
            pg.draw.arc(panel, (*(WARN_YELLOW if crop["ready"] else color), 255), rect,
                        math.pi / 2 - 2 * math.pi * progress, math.pi / 2, 12)
        percent = self.ring_font.render(f"{int(crop['growth'])}%", True, color)
        panel.blit(percent, percent.get_rect(center=center))
        self.draw_status(panel, area.x + 170, area.centery - 30)

    def draw_gauge_tube(self, panel, area):
        """ Mizuna: tubo de cultivo que se llena, con burbujas """
        crop, color = self.crop, self.color
        tube = pg.Rect(area.x + 40, area.y + 6, 66, area.height - 12)
        pg.draw.rect(panel, (*color, 30), tube, border_radius=24)
        fill_h = int((tube.height - 8) * crop["growth"] / 100)
        fill = pg.Rect(tube.x + 4, tube.bottom - 4 - fill_h, tube.width - 8, fill_h)
        if fill_h > 0:
            pg.draw.rect(panel, (*(WARN_YELLOW if crop["ready"] else color), 170), fill, border_radius=20)
            t = pg.time.get_ticks() / 1000
            for i in range(5):
                phase = (t * 0.4 + i / 5) % 1
                by = fill.bottom - phase * fill.height
                bx = fill.x + 10 + (i * 13) % (fill.width - 16)
                if fill.top < by < fill.bottom:
                    pg.draw.circle(panel, (255, 255, 255, 120), (bx, by), 4, 1)
        pg.draw.rect(panel, (*color, 255), tube, 2, border_radius=24)
        percent = self.big_font.render(f"{int(crop['growth'])}%", True, color)
        panel.blit(percent, (area.x + 130, area.y + 20))
        self.draw_status(panel, area.x + 130, area.y + 78)

    def draw_gauge_hex(self, panel, area):
        """ Chile: fila de hexágonos que se encienden """
        crop, color = self.crop, self.color
        lit = int(crop["growth"] / 10)
        for i in range(10):
            cx, cy, r = area.x + 24 + i * 47, area.y + 34, 21
            points = [(cx + r * math.cos(math.pi / 6 + j * math.pi / 3), cy + r * math.sin(math.pi / 6 + j * math.pi / 3))
                      for j in range(6)]
            on = i < lit
            pg.draw.polygon(panel, (*(WARN_YELLOW if crop["ready"] else color), 200 if on else 25), points)
            pg.draw.polygon(panel, (*color, 255), points, 2)
        percent = self.big_font.render(f"{int(crop['growth'])}%", True, color)
        panel.blit(percent, (area.x, area.y + 74))
        self.draw_status(panel, area.x + 130, area.y + 76)
