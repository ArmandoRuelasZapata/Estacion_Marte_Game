import math
import pygame as pg
from settings import GAME_TITLE, GAME_SUBTITLE, MENU_BACKGROUND, MENU_MUSIC
from controls import CONTROLS

# Paleta de la portada y el menú
RED = (200, 30, 30)
BAR_RED = (130, 15, 15)
TEXT = (230, 230, 230)
TEXT_DIM = (125, 125, 125)
PANEL = (20, 6, 6)

FADE_MS = 300  # Duración del fundido al entrar a cada pantalla


def render_spaced(font, text, color, spacing):
    """ Renderiza texto con espacio extra entre letras (estilo títulos de consola) """
    text = text or " "
    glyphs = []
    for char in text:
        glyph = font.render(char, True, color)
        # La fuente por defecto coloca la línea base de las letras acentuadas (Ó, Ú) a otra altura
        # dentro de su superficie; calculamos dónde queda la línea base de cada letra para alinearlas.
        bounds = glyph.get_bounding_rect()
        metrics = font.metrics(char)[0]
        baseline = bounds.top + metrics[3] if bounds.height and metrics else font.get_ascent()
        glyphs.append((glyph, baseline))

    top = max(baseline for _, baseline in glyphs)
    bottom = max(glyph.get_height() - baseline for glyph, baseline in glyphs)
    width = sum(glyph.get_width() for glyph, _ in glyphs) + spacing * (len(glyphs) - 1)
    surface = pg.Surface((width, top + bottom), pg.SRCALPHA)
    x = 0
    for glyph, baseline in glyphs:
        surface.blit(glyph, (x, top - baseline))
        x += glyph.get_width() + spacing
    return surface


def wrap_text(font, text, max_width):
    """ Parte un texto en líneas que caben en max_width píxeles """
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


class MenuBackground:
    """ Fondo de la portada y el menú. Por ahora: negro, o una imagen fija si MENU_BACKGROUND la indica.
    Un video .mp4 en bucle requerirá una librería extra (pygame no reproduce video por sí solo). """

    def __init__(self, size, path=None):
        self.image = None
        if path and path.lower().endswith((".png", ".jpg", ".jpeg")):
            self.image = pg.transform.smoothscale(pg.image.load(path).convert(), size)

    def draw(self, screen):
        screen.fill((0, 0, 0))
        if self.image:
            screen.blit(self.image, (0, 0))


class Screen:
    """ Pantalla base del menú: maneja el fundido de entrada """

    def __init__(self, menu):
        self.menu = menu
        self.entered_at = 0

    def enter(self):
        self.entered_at = pg.time.get_ticks()

    def handle_event(self, event):
        pass

    def draw(self, screen):
        pass

    def draw_fade(self, screen):
        progress = (pg.time.get_ticks() - self.entered_at) / FADE_MS
        if progress < 1:
            overlay = pg.Surface(screen.get_size())
            overlay.fill((0, 0, 0))
            overlay.set_alpha(int(255 * (1 - progress)))
            screen.blit(overlay, (0, 0))


class TitleScreen(Screen):
    """ Portada: título centrado y "presiona cualquier tecla" parpadeando """

    def __init__(self, menu):
        super().__init__(menu)
        self.title = render_spaced(pg.font.Font(None, 170), GAME_TITLE, TEXT, 14)
        self.subtitle = render_spaced(pg.font.Font(None, 52), GAME_SUBTITLE, RED, 10)
        self.prompt = render_spaced(pg.font.Font(None, 34), "PRESIONA CUALQUIER TECLA O BOTÓN", TEXT, 6)
        self.footer = pg.font.Font(None, 26).render("Prototipo - NASA Space Apps Challenge 2026", True, TEXT_DIM)

    def handle_event(self, event):
        if event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
            self.menu.go("main")

    def draw(self, screen):
        w, h = screen.get_size()
        title_y = h // 2 - self.title.get_height()
        screen.blit(self.title, (w // 2 - self.title.get_width() // 2, title_y))
        line_y = title_y + self.title.get_height() + 12
        pg.draw.line(screen, RED, (w // 2 - 320, line_y), (w // 2 + 320, line_y), 3)
        screen.blit(self.subtitle, (w // 2 - self.subtitle.get_width() // 2, line_y + 20))

        # Parpadeo suave del mensaje
        pulse = (math.sin(pg.time.get_ticks() / 400) + 1) / 2
        prompt = self.prompt.copy()
        prompt.set_alpha(int(80 + 175 * pulse))
        screen.blit(prompt, (w // 2 - prompt.get_width() // 2, h - 190))
        screen.blit(self.footer, (w // 2 - self.footer.get_width() // 2, h - 60))


class ListScreen(Screen):
    """ Menú vertical alineado a la izquierda con barra de selección y panel de descripción.
    Cada opción es un dict con: label, description, action (opcional), adjust (opcional, recibe +1/-1),
    value (opcional, función que devuelve el texto del valor) y separator (línea antes de la opción).
    description puede ser un texto o una función que lo devuelva (para mostrar datos que cambian).
    backdrop=True oscurece el lado izquierdo para que el menú se lea sobre una imagen (pausa). """

    X = 130           # Margen izquierdo de las opciones
    Y = 330           # Altura de la primera opción
    ROW = 50          # Separación entre opciones
    BAR_WIDTH = 600   # Ancho de la barra de selección

    def __init__(self, menu, items, on_back=None, heading=None, backdrop=False):
        super().__init__(menu)
        self.backdrop = self.build_backdrop() if backdrop else None
        self.items = items
        self.on_back = on_back
        self.selected = 0
        self.font = pg.font.Font(None, 42)
        self.desc_font = pg.font.Font(None, 32)
        self.hint_font = pg.font.Font(None, 28)
        self.heading = render_spaced(pg.font.Font(None, 60), heading or GAME_TITLE, TEXT, 8)
        self.bar = self.build_bar()
        self.item_rects = []

    def build_backdrop(self):
        """ Degradado negro de izquierda a derecha detrás del menú """
        width, height = pg.display.get_surface().get_size()
        surface = pg.Surface((width, height), pg.SRCALPHA)
        fade_end = int(width * 0.75)
        for x in range(fade_end):
            alpha = int(200 * (1 - x / fade_end) ** 1.2)
            pg.draw.line(surface, (0, 0, 0, alpha), (x, 0), (x, height))
        return surface

    def reset(self):
        """ Vuelve a seleccionar la primera opción """
        self.selected = 0

    def build_bar(self):
        """ Barra roja que se desvanece hacia la derecha """
        bar = pg.Surface((self.BAR_WIDTH, self.ROW - 6), pg.SRCALPHA)
        for x in range(self.BAR_WIDTH):
            alpha = int(220 * (1 - x / self.BAR_WIDTH) ** 1.5)
            pg.draw.line(bar, (*BAR_RED, alpha), (x, 0), (x, bar.get_height()))
        return bar

    def item_y(self, index):
        separators = sum(1 for item in self.items[:index + 1] if item.get("separator"))
        return self.Y + index * self.ROW + separators * 24

    def activate(self):
        item = self.items[self.selected]
        if item.get("action"):
            item["action"]()
        elif item.get("adjust"):
            item["adjust"](1)

    def handle_event(self, event):
        if event.type == pg.KEYDOWN:
            if event.key in (pg.K_UP, pg.K_w):
                self.selected = (self.selected - 1) % len(self.items)
            elif event.key in (pg.K_DOWN, pg.K_s):
                self.selected = (self.selected + 1) % len(self.items)
            elif event.key in (pg.K_LEFT, pg.K_a, pg.K_RIGHT, pg.K_d):
                adjust = self.items[self.selected].get("adjust")
                if adjust:
                    adjust(1 if event.key in (pg.K_RIGHT, pg.K_d) else -1)
            elif event.key in (pg.K_RETURN, pg.K_KP_ENTER, pg.K_SPACE):
                self.activate()
            elif event.key == pg.K_ESCAPE and self.on_back:
                self.on_back()
        elif event.type == pg.MOUSEMOTION:
            for index, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos):
                    self.selected = index
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for index, rect in enumerate(self.item_rects):
                if rect.collidepoint(event.pos):
                    self.selected = index
                    self.activate()

    def draw(self, screen):
        if self.backdrop:
            screen.blit(self.backdrop, (0, 0))
        screen.blit(self.heading, (self.X, self.Y - 130))
        pg.draw.line(screen, RED, (self.X, self.Y - 65), (self.X + 360, self.Y - 65), 3)

        self.item_rects = []
        for index, item in enumerate(self.items):
            y = self.item_y(index)
            selected = index == self.selected
            if item.get("separator"):
                sep_y = y - 18
                pg.draw.line(screen, (70, 70, 70), (self.X - 40, sep_y), (self.X + self.BAR_WIDTH - 140, sep_y), 1)

            row_rect = pg.Rect(self.X - 50, y - 10, self.BAR_WIDTH, self.ROW - 6)
            self.item_rects.append(row_rect)
            if selected:
                screen.blit(self.bar, row_rect.topleft)
                # Indicador: círculo rojo con una flecha
                cx, cy = self.X - 25, row_rect.centery
                pg.draw.circle(screen, RED, (cx, cy), 12)
                pg.draw.polygon(screen, TEXT, [(cx - 4, cy - 6), (cx - 4, cy + 6), (cx + 6, cy)])

            label = render_spaced(self.font, item["label"], TEXT if selected else TEXT_DIM, 4)
            screen.blit(label, (self.X, row_rect.centery - label.get_height() // 2))

            if item.get("value"):
                value_text = item["value"]()
                if selected and item.get("adjust"):
                    value_text = f"<  {value_text}  >"
                value = self.font.render(value_text, True, TEXT if selected else TEXT_DIM)
                screen.blit(value, (self.X + self.BAR_WIDTH - 110 - value.get_width(), row_rect.centery - value.get_height() // 2))

        self.draw_description(screen)
        self.draw_hints(screen)

    def draw_description(self, screen):
        text = self.items[self.selected].get("description")
        if callable(text):
            text = text()
        if not text:
            return
        row = self.item_rects[self.selected]
        width = 520
        lines = wrap_text(self.desc_font, text, width - 50)
        line_h = self.desc_font.get_linesize()
        panel = pg.Rect(row.right + 20, row.top, width, max(row.height, len(lines) * line_h + 24))
        surface = pg.Surface(panel.size)
        surface.fill(PANEL)
        surface.set_alpha(220)
        screen.blit(surface, panel.topleft)
        # Flecha roja apuntando a la opción
        ax, ay = panel.left + 18, panel.top + 22
        pg.draw.polygon(screen, RED, [(ax + 8, ay - 9), (ax + 8, ay + 9), (ax - 4, ay)])
        for i, line in enumerate(lines):
            screen.blit(self.desc_font.render(line, True, TEXT), (panel.left + 38, panel.top + 12 + i * line_h))

    def draw_hints(self, screen):
        """ Ayudas de controles abajo a la izquierda """
        labels = CONTROLS.labels()
        hints = [(labels["navigate"], "Navegar"), (labels["confirm"], "Seleccionar")]
        if any(item.get("adjust") for item in self.items):
            hints.append((labels["adjust"], "Ajustar"))
        if self.on_back:
            hints.append((labels["back"], "Volver"))
        x, y = self.X, screen.get_height() - 80
        for key, label in hints:
            key_surface = self.hint_font.render(key, True, TEXT)
            chip = pg.Rect(x, y, key_surface.get_width() + 16, key_surface.get_height() + 8)
            pg.draw.rect(screen, TEXT_DIM, chip, 2, border_radius=6)
            screen.blit(key_surface, (chip.x + 8, chip.y + 4))
            label_surface = self.hint_font.render(label, True, TEXT)
            screen.blit(label_surface, (chip.right + 10, chip.y + 4))
            x = chip.right + 10 + label_surface.get_width() + 40


class Menu:
    """ Controla la portada y las pantallas del menú antes de entrar al juego """

    def __init__(self, game):
        self.game = game
        self.background = MenuBackground(game.screen.get_size(), MENU_BACKGROUND)
        self.screens = {
            "title": TitleScreen(self),
            "main": ListScreen(self, [
                {"label": "INICIAR MISIÓN",
                 "description": "Entra a la estación marciana y recorre sus cuatro módulos.",
                 "action": game.start_mission_with_cinematic},
                {"label": "CONFIGURACIÓN",
                 "description": "Ajusta el volumen de la música y de los efectos de sonido.",
                 "action": lambda: self.go("settings")},
                {"label": "SALIR",
                 "description": "Cierra el juego.",
                 "action": game.quit_game,
                 "separator": True},
            ], on_back=lambda: self.go("title")),
            "settings": ListScreen(self, [
                {"label": "MÚSICA",
                 "description": "Volumen de la música. Usa izquierda/derecha para cambiarlo.",
                 "value": lambda: f"{round(game.music_volume * 100)}%",
                 "adjust": lambda step: game.set_music_volume(game.music_volume + 0.1 * step)},
                {"label": "EFECTOS",
                 "description": "Volumen de los disparos y golpes. Usa izquierda/derecha para cambiarlo.",
                 "value": lambda: f"{round(game.sfx_volume * 100)}%",
                 "adjust": lambda step: game.set_sfx_volume(game.sfx_volume + 0.1 * step)},
                {"label": "VOLVER",
                 "description": "Regresa al menú principal.",
                 "action": lambda: self.go("main"),
                 "separator": True},
            ], on_back=lambda: self.go("main"), heading="CONFIGURACIÓN"),
        }
        self.current = None

    def open(self, screen="title"):
        """ Arranca la música del menú y muestra la portada (o la pantalla indicada) """
        pg.mixer.music.load(MENU_MUSIC)
        pg.mixer.music.set_volume(self.game.music_volume)
        pg.mixer.music.play(-1, 0.0, fade_ms=1500)
        self.go(screen)

    def go(self, name):
        self.current = self.screens[name]
        self.current.enter()

    def run_frame(self):
        """ Un frame del menú: eventos, dibujo y flip """
        for event in CONTROLS.events("menu"):
            if event.type == pg.QUIT:
                self.game.quit_game()
            self.current.handle_event(event)
            if self.game.state != "menu":
                return
        screen = self.game.screen
        self.background.draw(screen)
        self.current.draw(screen)
        self.current.draw_fade(screen)
        pg.display.flip()
