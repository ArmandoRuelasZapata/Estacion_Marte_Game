"""
Soporte para mando (Xbox Series X/S y otros compatibles con XInput / SDL GameController).

Idea principal: el resto del juego solo entiende teclado. Este módulo traduce los botones del mando a
eventos de teclado (KEYDOWN) según el contexto en el que esté el jugador, así los menús y las consolas
funcionan con el mando sin cambiarlos. El movimiento con los sticks se lee aparte (move_axes).

Contextos y botones:
  "menu"     menú principal, configuración y misión cumplida/fallida
  "pause"    menú de pausa (MENÚ también reanuda)
  "playing"  partida: stick izq. = moverse, stick der. = girar, A = interactuar, X o RT = disparar, MENÚ = pausa
  "terminal" consolas de blindaje e invernadero e informes: D-pad/stick = ajustar, A = confirmar, B = salir
  "qte"      terminal de energía: A/B/X/Y son las teclas del evento rápido, VISTA = salir
  "pattern"  computadora de comunicaciones: stick izq./D-pad = WASD, stick der. = flechas, A = confirmar, B = salir

También guarda cuál fue el último dispositivo usado ("keyboard" o "gamepad") para que los textos de ayuda
muestren las teclas o los botones correctos (label()).
"""
import pygame as pg

try:
    from pygame._sdl2 import controller as sdl_controller  # API GameController de SDL (mapeo estándar)
except ImportError:  # Si no existe (por ejemplo en otra versión de pygame), se usa la API de joystick
    sdl_controller = None

DEADZONE = 0.25       # Zona muerta de los sticks (evita que el personaje se mueva solo)
STICK_PRESS = 0.6     # Cuánto hay que inclinar el stick para que cuente como "flecha" en los menús
TRIGGER_PRESS = 0.5   # Cuánto hay que apretar el gatillo para disparar

K = pg.KEYDOWN
CONTEXT_KEYS = {
    "menu": {"up": pg.K_UP, "down": pg.K_DOWN, "left": pg.K_LEFT, "right": pg.K_RIGHT,
             "a": pg.K_RETURN, "b": pg.K_ESCAPE, "start": pg.K_RETURN},
    "pause": {"up": pg.K_UP, "down": pg.K_DOWN, "left": pg.K_LEFT, "right": pg.K_RIGHT,
              "a": pg.K_RETURN, "b": pg.K_ESCAPE, "start": pg.K_ESCAPE},
    "playing": {"a": pg.K_e, "x": pg.K_SPACE, "rt": pg.K_SPACE, "start": pg.K_ESCAPE},
    "terminal": {"up": pg.K_UP, "down": pg.K_DOWN, "left": pg.K_LEFT, "right": pg.K_RIGHT,
                 "a": pg.K_RETURN, "b": pg.K_ESCAPE, "start": pg.K_ESCAPE},
    "qte": {"a": pg.K_f, "b": pg.K_g, "x": pg.K_h, "y": pg.K_j, "back": pg.K_ESCAPE, "start": pg.K_ESCAPE},
    # Computadora de comunicaciones: stick izquierdo/D-pad = WASD, stick derecho = flechas
    "pattern": {"up": pg.K_w, "down": pg.K_s, "left": pg.K_a, "right": pg.K_d,
                "r_up": pg.K_UP, "r_down": pg.K_DOWN, "r_left": pg.K_LEFT, "r_right": pg.K_RIGHT,
                "a": pg.K_RETURN, "b": pg.K_ESCAPE, "back": pg.K_ESCAPE, "start": pg.K_ESCAPE},
}
# Contextos donde el stick izquierdo funciona como flechas (en "playing" mueve al personaje)
STICK_AS_ARROWS = {"menu", "pause", "terminal", "pattern"}
# Contextos donde el stick derecho también cuenta como flechas, y donde solo vale la dirección dominante
RIGHT_STICK_EDGES = {"pattern"}
DOMINANT_AXIS = {"pattern"}

LABELS = {
    "keyboard": {"interact": "E", "confirm": "ENTER", "back": "ESC", "adjust": "IZQ/DER",
                 "navigate": "ARRIBA/ABAJO", "pause": "ESC", "qte_exit": "ESC", "shoot": "ESPACIO"},
    "gamepad": {"interact": "A", "confirm": "A", "back": "B", "adjust": "D-PAD",
                "navigate": "D-PAD", "pause": "MENÚ", "qte_exit": "VISTA", "shoot": "RT"},
}

# Teclas del evento rápido de energía y su botón equivalente en el mando (con los colores de Xbox)
QTE_GAMEPAD = {pg.K_f: ("A", (96, 190, 40)), pg.K_g: ("B", (230, 50, 50)),
               pg.K_h: ("X", (40, 120, 235)), pg.K_j: ("Y", (245, 190, 0))}

if sdl_controller:
    SDL_BUTTONS = {
        pg.CONTROLLER_BUTTON_A: "a", pg.CONTROLLER_BUTTON_B: "b",
        pg.CONTROLLER_BUTTON_X: "x", pg.CONTROLLER_BUTTON_Y: "y",
        pg.CONTROLLER_BUTTON_BACK: "back", pg.CONTROLLER_BUTTON_START: "start",
        pg.CONTROLLER_BUTTON_LEFTSHOULDER: "lb", pg.CONTROLLER_BUTTON_RIGHTSHOULDER: "rb",
        pg.CONTROLLER_BUTTON_DPAD_UP: "up", pg.CONTROLLER_BUTTON_DPAD_DOWN: "down",
        pg.CONTROLLER_BUTTON_DPAD_LEFT: "left", pg.CONTROLLER_BUTTON_DPAD_RIGHT: "right",
    }
# Respaldo con la API de joystick: orden de botones de XInput en Windows
JOY_BUTTONS = {0: "a", 1: "b", 2: "x", 3: "y", 4: "lb", 5: "rb", 6: "back", 7: "start"}


class GamepadDevice:
    """ Envuelve un mando (GameController o joystick) y normaliza sus ejes a -1..1 (gatillos a 0..1) """

    def __init__(self, device, is_controller):
        self.device = device
        self.is_controller = is_controller

    def axes(self):
        """ Devuelve (stick_izq_x, stick_izq_y, stick_der_x, stick_der_y, gatillo_der) """
        d = self.device
        try:
            if self.is_controller:
                get = lambda axis: d.get_axis(axis) / 32767
                return (get(pg.CONTROLLER_AXIS_LEFTX), get(pg.CONTROLLER_AXIS_LEFTY),
                        get(pg.CONTROLLER_AXIS_RIGHTX), get(pg.CONTROLLER_AXIS_RIGHTY),
                        max(0.0, get(pg.CONTROLLER_AXIS_TRIGGERRIGHT)))
            count = d.get_numaxes()
            get = lambda i: d.get_axis(i) if i < count else 0.0
            trigger = (get(5) + 1) / 2 if count > 5 else 0.0
            return get(0), get(1), get(2), get(3), trigger
        except pg.error:
            return 0.0, 0.0, 0.0, 0.0, 0.0

    def rumble(self, low, high, duration_ms):
        try:
            self.device.rumble(low, high, duration_ms)
        except (pg.error, AttributeError):
            pass


def apply_deadzone(x, y):
    """ Zona muerta circular: debajo de DEADZONE vale 0 y luego escala suave hasta 1 """
    magnitude = (x * x + y * y) ** 0.5
    if magnitude < DEADZONE:
        return 0.0, 0.0
    scale = min(1.0, (magnitude - DEADZONE) / (1 - DEADZONE)) / magnitude
    return x * scale, y * scale


class Controls:
    def __init__(self):
        self.pads = {}                 # id de instancia -> GamepadDevice
        self.last_device = "keyboard"
        self.stick_state = (0, 0)      # Dirección del stick en los menús, para detectar cuándo cambia
        self.rstick_state = (0, 0)     # Igual para el stick derecho (computadora de comunicaciones)
        self.trigger_down = False

    def init(self):
        """ Llamar después de pg.init(). Los mandos ya conectados llegan como eventos *DEVICEADDED. """
        if sdl_controller:
            sdl_controller.init()

    # ------------------------------------------------------------------ conexión de mandos
    def _handle_device_event(self, event):
        """ Devuelve True si el evento era de conexión/desconexión (y ya se procesó) """
        if sdl_controller:
            if event.type == pg.CONTROLLERDEVICEADDED:
                try:
                    pad = sdl_controller.Controller(event.device_index)
                    self.pads[pad.as_joystick().get_instance_id()] = GamepadDevice(pad, True)
                except pg.error:
                    pass
                return True
            if event.type == pg.CONTROLLERDEVICEREMOVED:
                self.pads.pop(event.instance_id, None)
                return True
            return event.type in (pg.JOYDEVICEADDED, pg.JOYDEVICEREMOVED)
        if event.type == pg.JOYDEVICEADDED:
            joystick = pg.joystick.Joystick(event.device_index)
            self.pads[joystick.get_instance_id()] = GamepadDevice(joystick, False)
            return True
        if event.type == pg.JOYDEVICEREMOVED:
            self.pads.pop(event.instance_id, None)
            return True
        return False

    def _pad_buttons(self, event):
        """ Nombres de los botones presionados en este evento, o None si no es un evento del mando """
        if sdl_controller:
            if event.type == pg.CONTROLLERBUTTONDOWN:
                return [SDL_BUTTONS[event.button]] if event.button in SDL_BUTTONS else []
            if event.type in (pg.CONTROLLERBUTTONUP, pg.CONTROLLERAXISMOTION,
                              pg.JOYBUTTONDOWN, pg.JOYBUTTONUP, pg.JOYAXISMOTION, pg.JOYHATMOTION, pg.JOYBALLMOTION):
                return []  # Con GameController activo, los eventos de joystick crudos se ignoran
            return None
        if event.type == pg.JOYBUTTONDOWN:
            return [JOY_BUTTONS[event.button]] if event.button in JOY_BUTTONS else []
        if event.type == pg.JOYHATMOTION:
            x, y = event.value
            return [name for name, on in (("left", x < 0), ("right", x > 0), ("up", y > 0), ("down", y < 0)) if on]
        if event.type in (pg.JOYBUTTONUP, pg.JOYAXISMOTION, pg.JOYBALLMOTION):
            return []
        return None

    # ------------------------------------------------------------------ eventos
    def events(self, context):
        """ Reemplazo de pg.event.get(): devuelve los eventos normales más los del mando convertidos en teclas """
        keys = CONTEXT_KEYS[context]
        out = []
        for event in pg.event.get():
            if self._handle_device_event(event):
                continue
            buttons = self._pad_buttons(event)
            if buttons is None:
                if event.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
                    self.last_device = "keyboard"
                out.append(event)
                continue
            if buttons:
                self.last_device = "gamepad"
            for name in buttons:
                if name in keys:
                    out.append(self.key_event(keys[name]))
        for name in self._poll_edges(context):
            if name in keys:
                out.append(self.key_event(keys[name]))
        return out

    @staticmethod
    def key_event(key):
        return pg.event.Event(pg.KEYDOWN, key=key, mod=0, unicode="", scancode=0, from_gamepad=True)

    def _poll_edges(self, context):
        """ Convierte el stick (en menús) y el gatillo derecho (en partida) en "botones" al cruzar el umbral """
        lx, ly, rx, ry, trigger = self.raw_axes()
        names = []
        dominant = context in DOMINANT_AXIS
        if context in STICK_AS_ARROWS:
            names += self._stick_edges(lx, ly, "stick_state", "", dominant)
        else:
            self.stick_state = (0, 0)
        if context in RIGHT_STICK_EDGES:
            names += self._stick_edges(rx, ry, "rstick_state", "r_", dominant)
        else:
            self.rstick_state = (0, 0)
        pressed = trigger > TRIGGER_PRESS
        if pressed and not self.trigger_down:
            names.append("rt")
        self.trigger_down = pressed
        if names:
            self.last_device = "gamepad"
        return names

    def _stick_edges(self, x, y, state_attr, prefix, dominant):
        """ Nombres de dirección ("up", "r_left"...) cuando el stick cruza el umbral desde otra dirección.
        Con dominant=True solo cuenta el eje más inclinado (una diagonal no da dos direcciones). """
        if dominant:
            if abs(x) >= abs(y):
                y = 0.0
            else:
                x = 0.0
        direction = (0 if abs(x) < STICK_PRESS else (1 if x > 0 else -1),
                     0 if abs(y) < STICK_PRESS else (1 if y > 0 else -1))
        previous = getattr(self, state_attr)
        names = []
        if direction != previous:
            if direction[0] and direction[0] != previous[0]:
                names.append(prefix + ("right" if direction[0] > 0 else "left"))
            if direction[1] and direction[1] != previous[1]:
                names.append(prefix + ("down" if direction[1] > 0 else "up"))
            setattr(self, state_attr, direction)
        return names

    # ------------------------------------------------------------------ sticks
    def raw_axes(self):
        """ Ejes del mando que se está usando: si hay varios conectados (o uno virtual), gana el que tenga
        los sticks o el gatillo más movidos. Sin mandos devuelve ceros. """
        best, best_amount = (0.0, 0.0, 0.0, 0.0, 0.0), 0.0
        for pad in self.pads.values():
            axes = pad.axes()
            amount = sum(abs(v) for v in axes)
            if amount > best_amount:
                best, best_amount = axes, amount
        return best

    def move_axes(self):
        """ Movimiento con los sticks, ya con zona muerta: (lateral, adelante, giro). Adelante = stick hacia arriba. """
        lx, ly, rx, _, _ = self.raw_axes()
        strafe, forward = apply_deadzone(lx, -ly)
        turn, _ = apply_deadzone(rx, 0.0)
        if strafe or forward or turn:
            self.last_device = "gamepad"
        return strafe, forward, turn

    # ------------------------------------------------------------------ textos y vibración
    @property
    def connected(self):
        return bool(self.pads)

    def label(self, action):
        """ Texto de la tecla o botón para una acción, según el último dispositivo usado """
        return LABELS[self.last_device][action]

    def labels(self):
        return LABELS[self.last_device]

    def qte_label(self, key, keyboard_name):
        """ Nombre y color de una tecla del evento rápido: letra del teclado o botón del mando """
        if self.last_device == "gamepad" and key in QTE_GAMEPAD:
            return QTE_GAMEPAD[key]
        return keyboard_name, None

    def rumble(self, low=0.5, high=0.5, duration_ms=200):
        """ Vibración del mando (si lo admite). low/high: intensidad 0 a 1 de los motores grave y agudo """
        for pad in self.pads.values():
            pad.rumble(low, high, duration_ms)


CONTROLS = Controls()
