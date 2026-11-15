import pygame as pg
from settings import RESOURCES

ENERGY_COLOR = (255, 200, 0)
OXYGEN_COLOR = (80, 200, 255)
SHIELD_COLOR = (150, 120, 255)
RADIATION_COLOR = (235, 40, 40)
LOW_LEVEL = 20  # Debajo de este valor la barra parpadea


class Resources:
    """ Recursos de la base: energía, oxígeno y blindaje (0 a 100), más la radiación que recibe la tripulación.

    Cómo se conectan (cada decisión cuesta algo):
      - La base consume energía todo el tiempo; si el tanque está en reserva, consume más.
      - El generador de oxígeno solo funciona con energía suficiente; si se apaga, el oxígeno baja.
      - Subir el blindaje cuesta energía, y el blindaje se descarga solo con el tiempo.
      - La radiación de las tormentas solares se acumula y no baja: el blindaje la reduce.
    """

    def __init__(self):
        cfg = RESOURCES
        self.cfg = cfg
        self.energy = cfg["energy_start"]
        self.oxygen = cfg["oxygen_start"]
        self.shield = cfg["shield_start"]
        self.radiation = 0.0
        self.radiation_limit = cfg["radiation_limit"]

    @staticmethod
    def clamp(value):
        return min(max(value, 0.0), 100.0)

    @property
    def oxygen_generator_on(self):
        return self.energy >= self.cfg["oxygen_min_energy"]

    def update(self, dt_ms, energy_reserve=False):
        dt = dt_ms / 1000
        cfg = self.cfg
        drain = cfg["energy_drain"] + (cfg["energy_reserve_drain"] if energy_reserve else 0)
        self.energy = self.clamp(self.energy - drain * dt)
        if self.oxygen_generator_on:
            self.oxygen = self.clamp(self.oxygen + cfg["oxygen_gain"] * dt)
        else:
            self.oxygen = self.clamp(self.oxygen - cfg["oxygen_loss"] * dt)
        self.shield = self.clamp(self.shield - cfg["shield_decay"] * dt)

    def add_energy(self, amount):
        self.energy = self.clamp(self.energy + amount)

    def add_radiation(self, amount):
        self.radiation = min(self.radiation + amount, self.radiation_limit)

    def get_alert(self):
        """ Aviso en pantalla cuando la energía no alcanza para el generador de oxígeno """
        if self.oxygen_generator_on:
            return None
        return {
            "id": "energy_critical",
            "tag": "SOPORTE VITAL",
            "title": "¡Energía crítica!",
            "hint": "El generador de oxígeno se apagó: el oxígeno empieza a bajar.",
            "color": RADIATION_COLOR,
        }

    def failure_reason(self):
        """ Devuelve por qué fracasó la misión, o None si todo sigue bien """
        if self.oxygen <= 0:
            return ("La tripulación se quedó sin oxígeno. El generador de oxígeno necesita energía: "
                    "rellena el tanque a tiempo y no gastes toda la energía en el blindaje.")
        if self.radiation >= self.radiation_limit:
            return ("La tripulación recibió demasiada radiación. Sube el blindaje antes de que llegue "
                    "una tormenta solar, aunque cueste energía.")
        return None
