import math
import random
import pygame as pg
from settings import ENERGY_MISSION, SOLAR_STORM, TILE
from nasa_data import SOLAR_FLARES, MARS_RADIATION_FACTS, DATA_SOURCES, flare_magnitude
from menu import wrap_text
from greenhouse import draw_projector, hologramize
from controls import CONTROLS

ALERT_RED = (235, 30, 30)
STORM_ORANGE = (255, 140, 0)
CRT_GREEN = (90, 255, 130)
CRT_DIM = (40, 120, 60)
CRT_BG = (4, 18, 8)
BEZEL = (48, 50, 56)
WARN_YELLOW = (255, 200, 0)
SHIELD_PURPLE = (150, 120, 255)

# Teclas posibles en el evento de pulsación rápida
QTE_KEYS = {pg.K_f: "F", pg.K_g: "G", pg.K_h: "H", pg.K_j: "J"}

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]


def blink(period_ms=500):
    """ True/False alternando cada period_ms (para alarmas que parpadean) """
    return (pg.time.get_ticks() // period_ms) % 2 == 0


def spanish_date(iso_date):
    """ "2017-09-06" → "6 de septiembre de 2017" """
    year, month, day = (int(part) for part in iso_date.split("-"))
    return f"{day} de {MONTHS[month - 1]} de {year}"


def draw_station(game, cell, base_color, border_color, label, prompt=None):
    """ Dibuja una consola o tanque en el mapa, con su nombre arriba y un aviso [E] abajo """
    screen = game.screen
    font = pg.font.Font(None, 26)
    sx, sy = game.camera.to_screen(cell[0], cell[1])
    base = pg.Rect(sx + 12, sy + 12, TILE - 24, TILE - 24)
    pg.draw.rect(screen, base_color, base, border_radius=8)
    pg.draw.rect(screen, border_color, base, 4, border_radius=8)
    text = font.render(label, True, (255, 255, 255))
    screen.blit(text, (sx + TILE // 2 - text.get_width() // 2, sy - 4))
    if prompt:
        prompt_font = pg.font.Font(None, 36)
        surface = prompt_font.render(prompt, True, WARN_YELLOW)
        box = surface.get_rect(center=(sx + TILE // 2, sy + TILE + 22)).inflate(16, 8)
        pg.draw.rect(screen, (0, 0, 0), box, border_radius=6)
        screen.blit(surface, surface.get_rect(center=box.center))
    return base


# ====================================================================== ventanas tipo computadora
class CrtWindow:
    """ Ventana con marco de computadora y pantalla verde (estilo monitor CRT).
    Las subclases definen title, footer, draw_screen_content(crt) y, si quieren, handle_event/update. """

    WIDTH, HEIGHT = 920, 560
    OPEN_MS = 220  # Animación de encendido de la pantalla
    title = ""
    footer = ""

    def __init__(self, game):
        self.game = game
        self.title_font = pg.font.Font(None, 34)
        self.big_font = pg.font.Font(None, 60)
        self.text_font = pg.font.Font(None, 32)
        self.small_font = pg.font.Font(None, 26)
        self.opened_at = 0
        self.scanlines = self.build_scanlines()

    def build_scanlines(self):
        surface = pg.Surface((self.WIDTH - 60, self.HEIGHT - 110), pg.SRCALPHA)
        for y in range(0, surface.get_height(), 3):
            pg.draw.line(surface, (0, 0, 0, 70), (0, y), (surface.get_width(), y))
        return surface

    def start(self):
        self.opened_at = pg.time.get_ticks()

    def handle_event(self, event):
        pass

    def update(self, dt_ms):
        pass

    def led_color(self):
        return ALERT_RED if blink(400) else (90, 20, 20)

    def draw_screen_content(self, crt):
        pass

    def draw(self, screen):
        window = self.render_window()
        t = min(1.0, (pg.time.get_ticks() - self.opened_at) / self.OPEN_MS)
        if t < 1:
            window = pg.transform.smoothscale(window, (window.get_width(), max(4, int(window.get_height() * t))))
        screen.blit(window, window.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2)))

    def render_window(self):
        window = pg.Surface((self.WIDTH, self.HEIGHT), pg.SRCALPHA)
        pg.draw.rect(window, BEZEL, window.get_rect(), border_radius=18)
        pg.draw.rect(window, (90, 92, 100), window.get_rect(), 3, border_radius=18)
        window.blit(self.title_font.render(self.title, True, (220, 220, 220)), (30, 20))
        pg.draw.circle(window, self.led_color(), (self.WIDTH - 40, 33), 9)

        screen_rect = pg.Rect(30, 60, self.WIDTH - 60, self.HEIGHT - 110)
        crt = pg.Surface(screen_rect.size)
        crt.fill(CRT_BG)
        self.draw_screen_content(crt)
        crt.blit(self.scanlines, (0, 0))
        window.blit(crt, screen_rect.topleft)
        pg.draw.rect(window, (20, 20, 22), screen_rect, 4)
        footer = self.footer.format(**CONTROLS.labels())  # {confirm}, {back}... según teclado o mando
        window.blit(self.text_font.render(footer, True, (170, 170, 170)), (30, self.HEIGHT - 40))
        return window

    @staticmethod
    def center_text(crt, font, text, color, y):
        surface = font.render(text, True, color)
        crt.blit(surface, (crt.get_width() // 2 - surface.get_width() // 2, y))

    def wrapped(self, crt, font, text, color, x, y, width):
        """ Escribe un párrafo con saltos de línea automáticos; devuelve la y siguiente """
        for line in wrap_text(font, text, width):
            crt.blit(font.render(line, True, color), (x, y))
            y += font.get_linesize()
        return y


# ====================================================================== misión 1: tanque de energía
class EnergyMission:
    """ Misión 1: cada cierto tiempo el tanque de energía entra en modo de reserva y la base gasta
    energía más rápido. El jugador debe ir al tanque, presionar E y completar la terminal de recarga.

    Estados:
      "stable"    → energía bien; cuenta atrás hasta la siguiente alerta
      "alert"     → energía en reserva; alarma en pantalla hasta que el jugador lo resuelva
      "repairing" → la terminal está abierta
    """

    def __init__(self, game):
        self.game = game
        self.config = ENERGY_MISSION
        self.cell = self.config["station_cell"]
        self.x, self.y = self.cell[0] + 0.5, self.cell[1] + 0.5
        self.state = "stable"
        self.cooldown_total = self.config["first_alert"]
        self.time_to_alert = self.cooldown_total
        self.completed = 0
        self.bonus_delay = 0  # Segundos extra antes de la próxima alerta (ayuda de un mensaje de la Tierra)
        self.terminal = EnergyTerminal(game, self)

    @property
    def in_reserve(self):
        """ True mientras la base gasta energía de más porque nadie ha rellenado el tanque """
        return self.state != "stable"

    def update(self, dt_ms):
        if self.state == "stable":
            self.time_to_alert -= dt_ms / 1000
            if self.time_to_alert <= 0:
                self.state = "alert"

    def player_in_range(self):
        player = self.game.player
        return math.hypot(player.x - self.x, player.y - self.y) <= self.config["interact_range"]

    def try_interact(self):
        """ Al presionar E: devuelve la ventana a abrir, o None """
        if self.state == "alert" and self.player_in_range():
            self.state = "repairing"
            return self.terminal
        return None

    def on_terminal_closed(self, success):
        if success:
            self.completed += 1
            self.game.resources.add_energy(self.config["refill_energy"])
            self.state = "stable"
            self.cooldown_total = self.config["cooldown"] + self.bonus_delay
            self.bonus_delay = 0
            self.time_to_alert = self.cooldown_total
        else:
            self.state = "alert"

    def prompt(self):
        """ Aviso de interacción para la vista 3D """
        if self.state == "alert" and self.player_in_range():
            return "RELLENAR TANQUE DE ENERGÍA"
        return None

    def billboards(self):
        """ Sprites para la vista 3D: (x, y, imagen, escala, elevación, sombrear) """
        return [(self.x, self.y, self.tank_image(), 0.85, 0.0, True)]

    def tank_image(self):
        """ Tanque cilíndrico con ventana de nivel y baliza (roja parpadeante si está en reserva) """
        alert = self.state != "stable"
        surf = pg.Surface((120, 200), pg.SRCALPHA)
        pg.draw.rect(surf, (40, 42, 50), (6, 178, 108, 20), border_radius=4)
        body = pg.Rect(14, 30, 92, 150)
        pg.draw.rect(surf, (88, 92, 104), body, border_radius=18)
        pg.draw.rect(surf, (128, 132, 146), (body.x + 14, body.y + 8, 14, body.height - 16), border_radius=6)
        pg.draw.rect(surf, (58, 60, 70), (body.right - 18, body.y + 8, 10, body.height - 16), border_radius=5)
        for y in (body.y + 18, body.bottom - 18):
            pg.draw.rect(surf, (52, 54, 63), (body.x, y - 4, body.width, 8))
        window = pg.Rect(body.centerx - 18, body.y + 34, 36, 90)
        pg.draw.rect(surf, (14, 17, 22), window, border_radius=6)
        level = self.energy_level()
        fill_h = int((window.height - 8) * level)
        color = ALERT_RED if alert else (60, 220, 90) if level > 0.4 else WARN_YELLOW
        pg.draw.rect(surf, color, (window.x + 4, window.bottom - 4 - fill_h, window.width - 8, fill_h), border_radius=4)
        pg.draw.rect(surf, (170, 175, 190), window, 2, border_radius=6)
        pg.draw.ellipse(surf, (112, 116, 130), (body.x, body.y - 10, body.width, 22))
        beacon = (ALERT_RED if blink(300) else (90, 20, 20)) if alert else (60, 220, 90)
        pg.draw.rect(surf, (50, 52, 60), (52, 10, 16, 14))
        pg.draw.circle(surf, beacon, (60, 9), 8)
        return surf

    def energy_level(self):
        """ Nivel visual del tanque (0 a 1): se vacía poco a poco hasta la alerta """
        if self.state == "stable":
            return max(0.15, self.time_to_alert / self.cooldown_total)
        return 0.1

    def draw_world(self):
        alert = self.state != "stable"
        border = ALERT_RED if alert and blink(300) else WARN_YELLOW
        prompt = f"[{CONTROLS.label('interact')}] RELLENAR" if self.state == "alert" and self.player_in_range() else None
        base = draw_station(self.game, self.cell, (35, 38, 50), border, "TANQUE DE ENERGÍA", prompt)

        # Indicador de nivel dentro del tanque
        inner = base.inflate(-24, -24)
        level = self.energy_level()
        fill_h = int(inner.height * level)
        color = ALERT_RED if alert else (60, 220, 90) if level > 0.4 else WARN_YELLOW
        pg.draw.rect(self.game.screen, (15, 15, 20), inner)
        pg.draw.rect(self.game.screen, color, (inner.x, inner.bottom - fill_h, inner.width, fill_h))
        pg.draw.rect(self.game.screen, (200, 200, 200), inner, 1)

    def get_alert(self):
        if self.state != "alert":
            return None
        return {
            "id": "energy",
            "tag": "ALERTA DE ENERGÍA",
            "title": "¡Rellena el tanque de energía!",
            "hint": f"Ve al módulo de Energía y presiona {CONTROLS.label('interact')} en el tanque. "
                    "Mientras tanto, la base gasta más energía.",
            "color": ALERT_RED,
        }

    def draw_minimap_marker(self, x0, y0, cell):
        if self.state == "stable":
            color = WARN_YELLOW
        elif blink(300):
            color = ALERT_RED
        else:
            return
        pg.draw.rect(self.game.screen, color, (x0 + self.cell[0] * cell, y0 + self.cell[1] * cell, cell, cell))


class EnergyTerminal(CrtWindow):
    """ Evento de pulsación rápida: presiona las teclas indicadas, en orden y una y otra vez,
    hasta llenar la barra. La barra baja sola si dejas de presionar y cada 25% cambia la combinación.

    Pantalla en tres columnas:
      - izquierda: holograma de la batería de reserva llenándose
      - centro: las teclas a presionar y la barra de progreso
      - derecha: gráfica de la energía de la estación, que sube mientras recargas
    """

    WIDTH, HEIGHT = 1100, 600
    SUCCESS_MS = 1600
    SAMPLE_MS = 100      # Cada cuánto se agrega un punto a la gráfica
    MAX_SAMPLES = 120    # Puntos visibles en la gráfica (12 segundos)
    HOLO_COLOR = (100, 220, 255)
    input_context = "qte"  # Con mando, A/B/X/Y son las teclas del evento (ver controls.py)
    title = "TERMINAL DE ENERGÍA  //  MÓDULO DE ENERGÍA"
    footer = "[{qte_exit}] Salir sin terminar"

    def __init__(self, game, mission):
        super().__init__(game)
        self.mission = mission
        cfg = ENERGY_MISSION
        self.gain = cfg["press_gain"]
        self.penalty = cfg["wrong_penalty"]
        self.decay = cfg["decay"]
        self.refill = cfg["refill_energy"]
        self.key_font = pg.font.Font(None, 90)
        self.tiny_font = pg.font.Font(None, 22)
        self.progress = 0.0
        self.done_at = None
        self.history = []
        self.base_energy = 0.0

    def start(self):
        super().start()
        self.progress = 0.0
        self.stage = 0
        self.done_at = None
        self.feedback = None  # ("ok" | "bad", momento) para el destello de color
        self.base_energy = self.game.resources.energy
        self.history = [self.projected_energy()]
        self.sample_timer = 0
        self.new_combo(first=True)

    def projected_energy(self):
        """ Energía que tendrá la estación si se completa la recarga hasta el progreso actual """
        return min(100.0, self.base_energy + self.refill * self.progress / 100)

    def new_combo(self, first=False):
        """ La primera combinación es una sola tecla; después, una o dos teclas al azar """
        self.combo = [pg.K_f] if first else random.sample(list(QTE_KEYS), random.choice((1, 2, 2)))
        self.combo_index = 0

    def close(self, success):
        self.mission.on_terminal_closed(success)
        self.game.close_terminal()

    def led_color(self):
        return (60, 220, 90) if self.done_at is not None else super().led_color()

    def handle_event(self, event):
        if event.type != pg.KEYDOWN:
            return
        if event.key == pg.K_ESCAPE and self.done_at is None:
            self.close(success=False)
            return
        if self.done_at is not None or event.key not in QTE_KEYS:
            return

        now = pg.time.get_ticks()
        if event.key == self.combo[self.combo_index]:
            self.progress = min(100.0, self.progress + self.gain)
            self.combo_index = (self.combo_index + 1) % len(self.combo)
            self.feedback = ("ok", now)
        else:
            self.progress = max(0.0, self.progress - self.penalty)
            self.feedback = ("bad", now)
            CONTROLS.rumble(0.8, 0.2, 120)

        if self.progress >= 100:
            self.done_at = now
            CONTROLS.rumble(0.4, 0.6, 300)
        elif int(self.progress // 25) > self.stage:
            self.stage = int(self.progress // 25)
            self.new_combo()

    def update(self, dt_ms):
        if self.done_at is None:
            self.progress = max(0.0, self.progress - self.decay * dt_ms / 1000)
        elif pg.time.get_ticks() - self.done_at >= self.SUCCESS_MS:
            self.close(success=True)
            return
        self.sample_timer += dt_ms
        while self.sample_timer >= self.SAMPLE_MS:
            self.sample_timer -= self.SAMPLE_MS
            self.history.append(self.projected_energy())
            self.history = self.history[-self.MAX_SAMPLES:]

    # ------------------------------------------------------------------ dibujo
    def draw_screen_content(self, crt):
        done = self.done_at is not None
        if done:
            self.center_text(crt, self.big_font, "TANQUE DE ENERGÍA RELLENADO", CRT_GREEN, 14)
        elif blink(500):
            self.center_text(crt, self.big_font, "ENERGÍA EN MODO DE RESERVA", ALERT_RED, 14)
        pg.draw.line(crt, CRT_DIM, (20, 66), (crt.get_width() - 20, 66), 1)

        self.draw_battery(crt, pg.Rect(10, 74, 320, 400))
        self.draw_keys(crt, pg.Rect(350, 74, 340, 400))
        self.draw_graph(crt, pg.Rect(710, 74, 320, 400))

    def draw_battery(self, crt, area):
        """ Holograma de la batería de reserva sobre su proyector """
        t = pg.time.get_ticks() / 1000
        color = (60, 230, 120) if self.done_at is not None else self.HOLO_COLOR
        crt.blit(self.small_font.render("BATERÍA DE RESERVA", True, CRT_GREEN), (area.x + 60, area.y + 4))

        overlay = pg.Surface(area.size, pg.SRCALPHA)
        draw_projector(overlay, area.width // 2, area.height - 40, 230, 300, color, t)
        crt.blit(overlay, area.topleft)

        holo = hologramize(self.battery_drawing(), color, t, width_scale=0.9 + 0.1 * math.cos(t * 1.5))
        bob = math.sin(t * 2) * 5
        crt.blit(holo, holo.get_rect(center=(area.centerx, area.y + 190 + bob)))

        label = self.text_font.render(f"CARGA: {int(self.progress)}%", True, color)
        crt.blit(label, label.get_rect(center=(area.centerx, area.bottom - 12)))

    def battery_drawing(self):
        """ Batería en blanco (luego se tiñe): cuerpo, borne, 8 celdas que se encienden y un rayo """
        surf = pg.Surface((170, 260), pg.SRCALPHA)
        body = pg.Rect(20, 34, 130, 216)
        pg.draw.rect(surf, (255, 255, 255, 45), body, border_radius=16)
        pg.draw.rect(surf, (255, 255, 255, 255), body, 3, border_radius=16)
        pg.draw.rect(surf, (255, 255, 255, 230), (62, 14, 46, 22), border_radius=5)

        cells = 8
        inner = body.inflate(-24, -24)
        cell_h = (inner.height - (cells - 1) * 6) / cells
        lit = self.progress / 100 * cells
        for i in range(cells):
            cell = pg.Rect(inner.x, inner.bottom - (i + 1) * cell_h - i * 6, inner.width, cell_h)
            if i < int(lit):
                pg.draw.rect(surf, (255, 255, 255, 210), cell, border_radius=4)
            elif i < lit:
                # Celda que se está llenando: parpadea
                pg.draw.rect(surf, (255, 255, 255, 210 if blink(150) else 90), cell, border_radius=4)
            else:
                pg.draw.rect(surf, (255, 255, 255, 90), cell, 1, border_radius=4)

        if self.done_at is None:
            cx, cy = body.centerx, body.centery
            bolt = [(cx + 8, cy - 46), (cx - 18, cy + 6), (cx - 2, cy + 6),
                    (cx - 10, cy + 46), (cx + 18, cy - 8), (cx + 2, cy - 8)]
            pg.draw.polygon(surf, (255, 255, 255, 255), bolt, 3)
        return surf

    def draw_keys(self, crt, area):
        """ Teclas a presionar (la siguiente se resalta) y barra de progreso """
        if self.done_at is not None:
            y = area.y + 60
            for line in wrap_text(self.text_font, f"La base recupera +{self.refill} de energía. ¡Buen trabajo!", area.width):
                surface = self.text_font.render(line, True, CRT_GREEN)
                crt.blit(surface, surface.get_rect(midtop=(area.centerx, y)))
                y += self.text_font.get_linesize()
            self.draw_bar(crt, pg.Rect(area.x, area.y + 250, area.width, 42), 100)
            return

        y = area.y + 6
        for line in wrap_text(self.small_font, "¡Presiona rápido estas teclas, en orden, una y otra vez!", area.width):
            surface = self.small_font.render(line, True, CRT_GREEN)
            crt.blit(surface, surface.get_rect(midtop=(area.centerx, y)))
            y += self.small_font.get_linesize()

        cap_w, gap = 110, 26
        total = len(self.combo) * cap_w + (len(self.combo) - 1) * gap
        x = area.centerx - total // 2
        for i, key in enumerate(self.combo):
            cap = pg.Rect(x, area.y + 80, cap_w, cap_w)
            active = i == self.combo_index
            # Con mando se muestra el botón (A/B/X/Y) con su color de Xbox; con teclado, la letra
            name, pad_color = CONTROLS.qte_label(key, QTE_KEYS[key])
            idle = pad_color or CRT_DIM
            color = (pad_color or CRT_GREEN) if active else idle
            if active and self.feedback and pg.time.get_ticks() - self.feedback[1] < 120:
                color = (255, 255, 255) if self.feedback[0] == "ok" else ALERT_RED
            if pad_color:
                pg.draw.circle(crt, color, cap.center, cap_w // 2, 0 if active else 5)
            else:
                pg.draw.rect(crt, color, cap, 0 if active else 4, border_radius=12)
            label = self.key_font.render(name, True, CRT_BG if active else idle)
            crt.blit(label, label.get_rect(center=cap.center))
            x += cap_w + gap

        self.draw_bar(crt, pg.Rect(area.x, area.y + 250, area.width, 42), self.progress)
        y = area.y + 336
        for line in wrap_text(self.tiny_font, "Si dejas de presionar, la barra baja. Una tecla equivocada resta.", area.width):
            hint = self.tiny_font.render(line, True, CRT_DIM)
            crt.blit(hint, hint.get_rect(midtop=(area.centerx, y)))
            y += self.tiny_font.get_linesize()

    def draw_bar(self, crt, bar, progress):
        pg.draw.rect(crt, CRT_DIM, bar, 3)
        fill = bar.inflate(-10, -10)
        fill.width = int(fill.width * progress / 100)
        bad = self.feedback and self.feedback[0] == "bad" and pg.time.get_ticks() - self.feedback[1] < 150
        pg.draw.rect(crt, ALERT_RED if bad else CRT_GREEN, fill)
        crt.blit(self.small_font.render(f"LLENANDO TANQUE: {int(progress)}%", True, CRT_GREEN), (bar.x, bar.bottom + 10))

    def draw_graph(self, crt, area):
        """ Gráfica de la energía de la estación durante la recarga, con la meta marcada """
        crt.blit(self.small_font.render("ENERGÍA DE LA ESTACIÓN", True, CRT_GREEN), (area.x, area.y + 4))
        graph = pg.Rect(area.x + 34, area.y + 40, area.width - 44, 250)

        def to_y(value):
            return graph.bottom - graph.height * value / 100

        # Cuadrícula y escala
        for value in (0, 25, 50, 75, 100):
            y = to_y(value)
            pg.draw.line(crt, (15, 45, 25), (graph.x, y), (graph.right, y), 1)
            label = self.tiny_font.render(str(value), True, CRT_DIM)
            crt.blit(label, (graph.x - label.get_width() - 6, y - 7))
        pg.draw.rect(crt, CRT_DIM, graph, 2)

        # Línea de la meta (energía al completar la recarga)
        target = min(100.0, self.base_energy + self.refill)
        ty = to_y(target)
        for x in range(graph.x, graph.right, 12):
            pg.draw.line(crt, WARN_YELLOW, (x, ty), (min(x + 6, graph.right), ty), 2)
        crt.blit(self.tiny_font.render("META", True, WARN_YELLOW), (graph.right - 40, ty - 18))

        # Curva de energía
        if len(self.history) >= 2:
            # Al principio la curva ocupa al menos un tercio del ancho; luego se va comprimiendo hasta MAX_SAMPLES
            step = graph.width / (max(len(self.history), self.MAX_SAMPLES // 3) - 1)
            points = [(graph.x + i * step, to_y(v)) for i, v in enumerate(self.history)]
            fill = pg.Surface(graph.size, pg.SRCALPHA)
            local = [(px - graph.x, py - graph.y) for px, py in points]
            pg.draw.polygon(fill, (*CRT_GREEN, 45), [(local[0][0], graph.height)] + local + [(local[-1][0], graph.height)])
            crt.blit(fill, graph.topleft)
            pg.draw.lines(crt, CRT_GREEN, False, points, 3)
            pg.draw.circle(crt, (255, 255, 255), points[-1], 5)

        now = self.history[-1] if self.history else self.base_energy
        crt.blit(self.text_font.render(f"Ahora: {int(now)}%", True, CRT_GREEN), (area.x, graph.bottom + 14))
        crt.blit(self.text_font.render(f"Meta: {int(target)}%", True, WARN_YELLOW), (area.x + 170, graph.bottom + 14))
        crt.blit(self.tiny_font.render(f"Rellenar el tanque suma +{self.refill} de energía", True, CRT_DIM),
                 (area.x, graph.bottom + 48))


# ====================================================================== misión 2: tormenta solar
class SolarStormMission:
    """ Misión 2: tormentas solares basadas en llamaradas reales registradas por NASA DONKI.

    Estados:
      "calm"    → sin tormenta; cuenta atrás hasta el siguiente aviso
      "warning" → se detectó una llamarada: el jugador tiene unos segundos para subir el blindaje
      "impact"  → llega la radiación; el blindaje bloquea una parte y se va gastando
    La intensidad sale de la clase real de la llamarada (X9.3 es más fuerte que X5.8).
    El blindaje se sube en la consola del Hábitat y cuesta energía: esa es la decisión.
    """

    def __init__(self, game):
        self.game = game
        self.cfg = SOLAR_STORM
        self.cell = self.cfg["station_cell"]
        self.x, self.y = self.cell[0] + 0.5, self.cell[1] + 0.5
        self.state = "calm"
        self.timer = self.cfg["first_warning"]
        self.deck = random.sample(SOLAR_FLARES, len(SOLAR_FLARES))  # Orden distinto en cada partida
        self.flare = None
        self.intensity = 0
        self.dose = 0.0
        self.dose_unshielded = 0.0
        self.storms_survived = 0
        self.total_blocked = 0.0
        self.pending_report = False
        self.extra_warning = 0  # Segundos extra de aviso para la próxima tormenta (pronóstico de la Tierra)
        self.console = ShieldConsole(game, self)
        self.report = StormReport(game, self)

    def next_flare(self):
        if not self.deck:
            self.deck = random.sample(SOLAR_FLARES, len(SOLAR_FLARES))
        return self.deck.pop()

    def update(self, dt_ms):
        dt = dt_ms / 1000
        self.timer -= dt
        if self.state == "calm" and self.timer <= 0:
            self.state = "warning"
            self.flare = self.next_flare()
            self.intensity = round(flare_magnitude(self.flare["class"]) * self.cfg["intensity_per_class"])
            self.timer = self.cfg["warning_time"] + self.extra_warning
            self.extra_warning = 0
        elif self.state == "warning" and self.timer <= 0:
            CONTROLS.rumble(0.7, 1.0, 700)
            self.state = "impact"
            self.timer = self.cfg["impact_time"]
            self.dose = 0.0
            self.dose_unshielded = 0.0
        elif self.state == "impact":
            resources = self.game.resources
            rate = self.intensity / self.cfg["impact_time"]
            received = rate * dt * (1 - resources.shield / 100)
            resources.add_radiation(received)
            self.dose += received
            self.dose_unshielded += rate * dt
            resources.shield = resources.clamp(resources.shield - self.cfg["shield_absorb"] * dt)
            if self.timer <= 0:
                self.storms_survived += 1
                self.total_blocked += self.dose_unshielded - self.dose
                self.state = "calm"
                self.timer = random.uniform(*self.cfg["interval"])
                self.pending_report = True  # El juego abre el informe al terminar este frame

    def player_in_range(self):
        player = self.game.player
        return math.hypot(player.x - self.x, player.y - self.y) <= self.cfg["interact_range"]

    def try_interact(self):
        """ La consola de blindaje se puede usar en cualquier momento, no solo con tormenta """
        return self.console if self.player_in_range() else None

    def prompt(self):
        return "CONSOLA DE BLINDAJE" if self.player_in_range() else None

    def billboards(self):
        """ Sprite 3D: escritorio de la consola con el holograma del domo encima (cambia de color con la tormenta) """
        t = pg.time.get_ticks() / 1000
        color = self.console.HOLO_COLORS[self.state]
        surf = pg.Surface((200, 300), pg.SRCALPHA)
        draw_projector(surf, 100, 214, 150, 160, color, t)
        drawing = self.console.station_drawing(self.game.resources.shield / 100, t)
        holo = hologramize(drawing, color, t, width_scale=0.94 + 0.06 * math.cos(t * 1.3))
        holo = pg.transform.smoothscale(holo, (190, 160))
        surf.blit(holo, (5, 40 + math.sin(t * 2) * 4))
        desk = [(26, 300), (174, 300), (162, 214), (38, 214)]
        pg.draw.polygon(surf, (44, 40, 70), desk)
        pg.draw.polygon(surf, (110, 100, 170), desk, 3)
        pg.draw.rect(surf, tuple(c // 2 for c in color), (56, 226, 88, 30), border_radius=4)
        pg.draw.rect(surf, color, (56, 226, 88, 30), 2, border_radius=4)
        return [(self.x, self.y, surf, 1.0, 0.0, False)]

    def estimated_dose(self, shield):
        """ Radiación aproximada que recibiría la tripulación con ese blindaje (sin contar su desgaste) """
        return self.intensity * (1 - shield / 100)

    def draw_world(self):
        danger = self.state in ("warning", "impact")
        border = STORM_ORANGE if danger and blink(300) else SHIELD_PURPLE
        prompt = f"[{CONTROLS.label('interact')}] BLINDAJE" if self.player_in_range() else None
        base = draw_station(self.game, self.cell, (30, 25, 55), border, "CONSOLA DE BLINDAJE", prompt)
        # Escudo dibujado dentro de la consola, lleno según el blindaje actual
        inner = base.inflate(-28, -28)
        level = self.game.resources.shield / 100
        pg.draw.rect(self.game.screen, (15, 15, 25), inner)
        fill_h = int(inner.height * level)
        pg.draw.rect(self.game.screen, SHIELD_PURPLE, (inner.x, inner.bottom - fill_h, inner.width, fill_h))
        pg.draw.rect(self.game.screen, (200, 200, 200), inner, 1)

    def draw_effects(self, screen):
        """ Durante el impacto, la pantalla se tiñe de naranja """
        if self.state != "impact":
            return
        pulse = (math.sin(pg.time.get_ticks() / 120) + 1) / 2
        tint = pg.Surface(screen.get_size())
        tint.fill(STORM_ORANGE)
        tint.set_alpha(int(25 + 35 * pulse))
        screen.blit(tint, (0, 0))

    def get_alert(self):
        if self.state == "warning":
            return {
                "id": "storm_warning",
                "tag": "TORMENTA SOLAR EN CAMINO",
                "title": f"¡Sube el blindaje! Impacto en {math.ceil(self.timer)} s",
                "hint": f"Consola de Soporte Vital ({CONTROLS.label('interact')}). Llamarada real "
                        f"{self.flare['class']} del {spanish_date(self.flare['date'])}.",
                "color": STORM_ORANGE,
            }
        if self.state == "impact":
            return {
                "id": "storm_impact",
                "tag": "TORMENTA SOLAR",
                "title": "¡Impacto de radiación!",
                "hint": f"El blindaje ({int(self.game.resources.shield)}%) bloquea parte de la radiación.",
                "color": STORM_ORANGE,
            }
        return None

    def draw_minimap_marker(self, x0, y0, cell):
        danger = self.state in ("warning", "impact")
        if danger and not blink(300):
            return
        color = STORM_ORANGE if danger else SHIELD_PURPLE
        pg.draw.rect(self.game.screen, color, (x0 + self.cell[0] * cell, y0 + self.cell[1] * cell, cell, cell))


class ShieldConsole(CrtWindow):
    """ Consola de blindaje: el jugador elige a qué nivel subir el blindaje y ve cuánto cuesta en energía
    y cuánta radiación evitaría. Es una decisión, no un juego de reflejos.

    A la izquierda hay un holograma de la estación dentro de su domo de blindaje:
      - el color indica la situación: morado sin tormenta, naranja con tormenta en camino, ámbar durante el impacto
      - el domo se ve más denso cuanto más blindaje eliges
      - durante el impacto, partículas de radiación chocan contra el domo
    """

    WIDTH, HEIGHT = 1100, 600
    STEP = 10
    HOLO_COLORS = {"calm": SHIELD_PURPLE, "warning": STORM_ORANGE, "impact": (255, 191, 0)}
    STATE_LABELS = {"calm": "SIN TORMENTA", "warning": "TORMENTA EN CAMINO", "impact": "IMPACTO DE RADIACIÓN"}
    title = "CONSOLA DE BLINDAJE  //  SOPORTE VITAL"
    footer = "[{adjust}] Ajustar    [{confirm}] Confirmar    [{back}] Salir sin cambios"

    def __init__(self, game, mission):
        super().__init__(game)
        self.mission = mission
        self.cost_per_point = SOLAR_STORM["shield_energy_cost"]
        self.target = 0
        self.holo_color = list(SHIELD_PURPLE)
        self.tiny_font = pg.font.Font(None, 22)

    def led_color(self):
        return STORM_ORANGE if self.mission.state != "calm" and blink(400) else SHIELD_PURPLE

    def start(self):
        super().start()
        self.target = int(self.game.resources.shield)
        self.holo_color = list(self.HOLO_COLORS[self.mission.state])

    def max_affordable(self):
        resources = self.game.resources
        return int(min(100, resources.shield + resources.energy / self.cost_per_point))

    def cost(self):
        return max(0.0, (self.target - self.game.resources.shield) * self.cost_per_point)

    def handle_event(self, event):
        if event.type != pg.KEYDOWN:
            return
        current = int(self.game.resources.shield)
        if event.key in (pg.K_RIGHT, pg.K_d):
            self.target = min(self.max_affordable(), (self.target // self.STEP + 1) * self.STEP)
        elif event.key in (pg.K_LEFT, pg.K_a):
            self.target = max(current, (self.target - 1) // self.STEP * self.STEP)
        elif event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
            resources = self.game.resources
            resources.energy = resources.clamp(resources.energy - self.cost())
            resources.shield = max(resources.shield, float(self.target))
            self.game.close_terminal()
        elif event.key == pg.K_ESCAPE:
            self.game.close_terminal()

    # ------------------------------------------------------------------ holograma de la estación
    def current_holo_color(self):
        """ El color se acerca poco a poco al de la situación actual (transición suave) """
        target = self.HOLO_COLORS[self.mission.state]
        self.holo_color = [c + (t - c) * 0.08 for c, t in zip(self.holo_color, target)]
        return tuple(int(c) for c in self.holo_color)

    def station_drawing(self, shield, t):
        """ Estación espacial dentro de un domo, en blanco (luego se tiñe). shield va de 0 a 1. """
        W, H = 320, 270
        surf = pg.Surface((W, H), pg.SRCALPHA)
        cx, base_y = W // 2, H - 24
        R = 146  # Radio del domo

        # Plataforma
        pg.draw.ellipse(surf, (255, 255, 255, 60), (cx - R - 6, base_y - 16, 2 * R + 12, 32))
        pg.draw.ellipse(surf, (255, 255, 255, 220), (cx - R - 6, base_y - 16, 2 * R + 12, 32), 2)

        # Estación (cabe completa dentro del domo): anillo que gira, módulo central, paneles solares y antena
        sy = base_y - 72
        ring = pg.Rect(cx - 62, sy - 20, 124, 40)
        pg.draw.ellipse(surf, (255, 255, 255, 230), ring, 3)
        spin = t * 1.4
        for i in range(4):
            a = spin + i * math.pi / 2
            pg.draw.line(surf, (255, 255, 255, 170), (cx, sy), (cx + math.cos(a) * 62, sy + math.sin(a) * 20), 2)
        hub = pg.Rect(cx - 14, sy - 36, 28, 72)
        pg.draw.rect(surf, (255, 255, 255, 70), hub, border_radius=9)
        pg.draw.rect(surf, (255, 255, 255, 240), hub, 2, border_radius=9)
        for dy in (-18, 0, 18):
            pg.draw.line(surf, (255, 255, 255, 150), (hub.x, sy + dy), (hub.right, sy + dy), 1)
        for side in (-1, 1):
            arm_x = cx + side * 14
            pg.draw.line(surf, (255, 255, 255, 220), (arm_x, sy - 22), (arm_x + side * 26, sy - 22), 2)
            panel = pg.Rect(0, 0, 40, 20)
            panel.center = (arm_x + side * 46, sy - 22)
            pg.draw.rect(surf, (255, 255, 255, 80), panel)
            pg.draw.rect(surf, (255, 255, 255, 240), panel, 2)
            for gx in range(panel.x + 10, panel.right, 10):
                pg.draw.line(surf, (255, 255, 255, 140), (gx, panel.y), (gx, panel.bottom), 1)
        pg.draw.line(surf, (255, 255, 255, 230), (cx, hub.top), (cx, hub.top - 22), 2)
        pg.draw.circle(surf, (255, 255, 255, 255), (cx, hub.top - 24), 4)
        pg.draw.line(surf, (255, 255, 255, 200), (cx, hub.bottom), (cx, base_y - 6), 2)

        # Domo: más líneas y más opaco cuanto más blindaje
        strength = 0.25 + 0.75 * shield
        dome = pg.Rect(cx - R, base_y - R, 2 * R, 2 * R)
        fill = pg.Surface((W, H), pg.SRCALPHA)
        pg.draw.circle(fill, (255, 255, 255, int(18 + 45 * shield)), (cx, base_y), R)
        pg.draw.rect(fill, (0, 0, 0, 0), (0, base_y, W, H - base_y))
        surf.blit(fill, (0, 0))
        line_alpha = int(60 + 190 * strength)
        pg.draw.arc(surf, (255, 255, 255, line_alpha), dome, 0, math.pi, 3)
        lines = 2 + int(shield * 4)
        for i in range(1, lines + 1):
            # Paralelos (líneas horizontales del domo)
            h = R * i / (lines + 1)
            half = math.sqrt(R * R - h * h)
            y = base_y - h
            pg.draw.ellipse(surf, (255, 255, 255, int(line_alpha * 0.7)), (cx - half, y - half * 0.12, 2 * half, half * 0.24), 1)
        for i in range(1, lines + 1):
            # Meridianos (líneas verticales del domo)
            w = R * i / (lines + 1)
            pg.draw.arc(surf, (255, 255, 255, int(line_alpha * 0.6)), (cx - w, base_y - R, 2 * w, 2 * R), 0, math.pi, 1)
        return surf

    def draw_hologram(self, crt, area):
        mission = self.mission
        t = pg.time.get_ticks() / 1000
        color = self.current_holo_color()
        crt.blit(self.small_font.render("DOMO DE BLINDAJE", True, color), (area.x + 70, area.y + 4))

        overlay = pg.Surface(area.size, pg.SRCALPHA)
        draw_projector(overlay, area.width // 2, area.height - 66, 260, 300, color, t)

        holo = hologramize(self.station_drawing(self.target / 100, t), color, t,
                           width_scale=0.94 + 0.06 * math.cos(t * 1.3))
        bob = math.sin(t * 2) * 4
        holo_rect = holo.get_rect(midbottom=(area.width // 2, area.height - 74 + bob))
        overlay.blit(holo, holo_rect)

        if mission.state == "impact":
            # Partículas de radiación que llegan desde arriba y chocan contra el domo
            dome_center = (holo_rect.centerx, holo_rect.bottom - 24)
            for i in range(14):
                phase = (t * 1.6 + i * 0.37) % 1
                angle = math.radians(200 + (i * 47) % 140)
                start_r, end_r = 240, 150
                r = start_r - (start_r - end_r) * phase
                x = dome_center[0] + math.cos(angle) * r
                y = dome_center[1] + math.sin(angle) * r
                tail = 18
                tx = dome_center[0] + math.cos(angle) * (r + tail)
                ty = dome_center[1] + math.sin(angle) * (r + tail)
                pg.draw.line(overlay, (255, 240, 180, 220), (tx, ty), (x, y), 2)
                if phase > 0.9:
                    pg.draw.circle(overlay, (255, 255, 255, 255), (x, y), 4)
        crt.blit(overlay, area.topleft)

        state = self.STATE_LABELS[mission.state]
        label = self.small_font.render(f"ESTADO: {state}", True, color)
        crt.blit(label, label.get_rect(center=(area.centerx, area.bottom - 34)))
        level = self.text_font.render(f"DOMO AL {self.target}%", True, color)
        crt.blit(level, level.get_rect(center=(area.centerx, area.bottom - 8)))

    # ------------------------------------------------------------------ pantalla
    def draw_screen_content(self, crt):
        resources = self.game.resources
        mission = self.mission

        if mission.state in ("warning", "impact"):
            when = f"impacto en {math.ceil(mission.timer)} s" if mission.state == "warning" else "¡impactando ahora!"
            self.center_text(crt, self.big_font, f"TORMENTA SOLAR: {when}", STORM_ORANGE, 14)
        else:
            self.center_text(crt, self.big_font, "SIN TORMENTAS DETECTADAS", CRT_GREEN, 14)
        pg.draw.line(crt, CRT_DIM, (20, 66), (crt.get_width() - 20, 66), 1)

        self.draw_hologram(crt, pg.Rect(10, 74, 320, 410))

        x, width = 350, crt.get_width() - 370
        if mission.state in ("warning", "impact"):
            flare = mission.flare
            y = self.wrapped(crt, self.small_font,
                             f"Llamarada real clase {flare['class']} del {spanish_date(flare['date'])}, "
                             f"región activa {flare['region']} del Sol (NASA DONKI). Intensidad: {mission.intensity}.",
                             CRT_GREEN, x, 84, width)
        else:
            y = self.wrapped(crt, self.small_font,
                             "Puedes subir el blindaje por adelantado, pero se descarga poco a poco.", CRT_GREEN, x, 84, width)

        # Barra de blindaje: actual (morado) y lo que vas a agregar (verde)
        bar = pg.Rect(x, max(y + 14, 140), width, 46)
        pg.draw.rect(crt, CRT_DIM, bar, 3)
        inner = bar.inflate(-10, -10)
        current_w = int(inner.width * resources.shield / 100)
        target_w = int(inner.width * self.target / 100)
        pg.draw.rect(crt, CRT_GREEN, (inner.x, inner.y, target_w, inner.height))
        pg.draw.rect(crt, SHIELD_PURPLE, (inner.x, inner.y, current_w, inner.height))
        crt.blit(self.text_font.render(f"BLINDAJE: de {int(resources.shield)}% a {self.target}%", True, CRT_GREEN),
                 (bar.x, bar.bottom + 10))

        cost = self.cost()
        left = resources.energy - cost
        energy_color = ALERT_RED if left < resources.cfg["oxygen_min_energy"] else CRT_GREEN
        y = bar.bottom + 64
        crt.blit(self.text_font.render(f"Costo: {int(cost)} de energía  (te quedará {int(left)}%)", True, energy_color), (x, y))
        if left < resources.cfg["oxygen_min_energy"]:
            y += 34
            crt.blit(self.small_font.render(
                "¡Cuidado! Con tan poca energía se apaga el generador de oxígeno.", True, ALERT_RED), (x, y))
        y += 48
        if mission.state in ("warning", "impact"):
            estimate = mission.estimated_dose(self.target)
            crt.blit(self.text_font.render(
                f"Radiación estimada: {mission.intensity} × {100 - self.target}% sin bloquear = unos {round(estimate)}",
                True, CRT_GREEN), (x, y))
            y += 34
            crt.blit(self.small_font.render(
                "Aproximado: el blindaje se gasta mientras bloquea la radiación.", True, CRT_DIM), (x, y))
        else:
            self.wrapped(crt, self.small_font, MARS_RADIATION_FACTS[0], CRT_DIM, x, y, width)

        legend = "Color del domo: morado = calma  ·  naranja = tormenta en camino  ·  ámbar = impacto"
        crt.blit(self.tiny_font.render(legend, True, CRT_DIM), (x, crt.get_height() - 26))


class StormReport(CrtWindow):
    """ Informe que aparece al terminar cada tormenta: qué pasó, qué tan bien funcionó el blindaje
    y el dato real de la NASA en el que se basó la tormenta """

    title = "INFORME DE TORMENTA SOLAR"
    footer = "[{confirm}] Continuar"

    def __init__(self, game, mission):
        super().__init__(game)
        self.mission = mission
        self.radiation_fact = MARS_RADIATION_FACTS[0]

    def start(self):
        super().start()
        self.radiation_fact = random.choice(MARS_RADIATION_FACTS)

    def led_color(self):
        return (60, 220, 90)

    def handle_event(self, event):
        if event.type == pg.KEYDOWN and event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE, pg.K_ESCAPE):
            self.game.close_terminal()

    def draw_screen_content(self, crt):
        mission = self.mission
        x, width = 40, crt.get_width() - 80
        unshielded = mission.dose_unshielded
        blocked = 0 if unshielded <= 0 else round(100 * (1 - mission.dose / unshielded))

        self.center_text(crt, self.big_font, "LA TORMENTA PASÓ", CRT_GREEN, 16)
        y = 76
        crt.blit(self.text_font.render(
            f"Tu blindaje bloqueó el {blocked}% de la radiación.", True, CRT_GREEN), (x, y))
        y += 34
        crt.blit(self.text_font.render(
            f"La tripulación recibió {round(mission.dose)} de radiación (sin blindaje: {round(unshielded)}).",
            True, CRT_GREEN), (x, y))
        y += 50

        flare = mission.flare
        crt.blit(self.text_font.render("EVENTO REAL", True, WARN_YELLOW), (x, y))
        y += 32
        y = self.wrapped(crt, self.small_font,
                         f"Llamarada solar clase {flare['class']} del {spanish_date(flare['date'])}, "
                         f"región activa {flare['region']} del Sol. {flare['fact']}", CRT_GREEN, x, y, width)
        y += 14
        y = self.wrapped(crt, self.small_font, self.radiation_fact, CRT_DIM, x, y, width)
        self.wrapped(crt, self.small_font, DATA_SOURCES, CRT_DIM, x, crt.get_height() - 34, width)
