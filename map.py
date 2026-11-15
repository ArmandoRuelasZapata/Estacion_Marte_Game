"""
Mapa de la estación marciana, generado por código a partir de los módulos y los tubos.

Diseño (vista desde arriba):

                 ( Cultivos )            ← módulo superior, con suelo rojo de Marte
                      ||
                ( Soporte Vital )        ← módulo central grande (blindaje contra la radiación solar)
               //              \\
   ( Comunicaciones )      ( Energía )   ← módulos inferiores

Cada módulo es un círculo (centro y radio en SECTORS, settings.py) y los tubos son pasillos rectos entre
los centros de dos módulos (STATION_TUBES). Todo lo que no es módulo ni tubo es muro.

El resultado se guarda como cuadrícula:
  mini_map[j][i]    → 1 = muro, 0 = piso          (j = fila / y, i = columna / x)
  sector_grid[j][i] → índice del sector en SECTORS (los muros toman el sector del piso más cercano)
  doors             → celdas de los tubos (no aparecen NPCs ahí al empezar la partida)
"""
import math
import random
from collections import deque
from settings import SECTORS, STATION_TUBES, TUBE_HALF_WIDTH


def _distance_to_segment(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    length2 = abx * abx + aby * aby
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / length2))
    return math.hypot(px - (ax + abx * t), py - (ay + aby * t))


def build_station():
    """ Genera la cuadrícula de la estación: devuelve (mini_map, sector_grid, celdas de tubo) """
    width = int(max(s["center"][0] + s["radius"] for s in SECTORS)) + 2
    height = int(max(s["center"][1] + s["radius"] for s in SECTORS)) + 2
    walls = [[1] * width for _ in range(height)]
    sectors = [[None] * width for _ in range(height)]

    # Módulos circulares
    for index, sector in enumerate(SECTORS):
        cx, cy = sector["center"]
        for j in range(height):
            for i in range(width):
                if math.hypot(i + 0.5 - cx, j + 0.5 - cy) <= sector["radius"]:
                    walls[j][i] = 0
                    sectors[j][i] = index

    # Tubos: pasillos rectos entre los centros de dos módulos (pertenecen al primer sector del par)
    tubes = set()
    for a, b in STATION_TUBES:
        (ax, ay), (bx, by) = SECTORS[a]["center"], SECTORS[b]["center"]
        for j in range(height):
            for i in range(width):
                if walls[j][i] and _distance_to_segment(i + 0.5, j + 0.5, ax, ay, bx, by) <= TUBE_HALF_WIDTH:
                    walls[j][i] = 0
                    sectors[j][i] = a
                    tubes.add((i, j))

    # Los muros toman el sector del piso más cercano (para el color de sus paneles en 3D)
    queue = deque((i, j) for j in range(height) for i in range(width) if sectors[j][i] is not None)
    while queue:
        i, j = queue.popleft()
        for ni, nj in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= ni < width and 0 <= nj < height and sectors[nj][ni] is None:
                sectors[nj][ni] = sectors[j][i]
                queue.append((ni, nj))
    return walls, sectors, tubes


class Map:
    def __init__(self, game):
        self.game = game
        self.mini_map, self.sector_grid, self.doors = build_station()
        self.width, self.height = len(self.mini_map[0]), len(self.mini_map)
        self.get_map()

    def get_map(self):
        """ Diccionario de muros {(x, y): 1} que usan las colisiones y el ray casting """
        self.world_map = {}
        for j, row in enumerate(self.mini_map):
            for i, value in enumerate(row):
                if value:
                    self.world_map[(i, j)] = value

    def sector_index_at(self, x, y):
        """ Índice del sector en la posición (x, y), en celdas """
        i = min(max(int(x), 0), self.width - 1)
        j = min(max(int(y), 0), self.height - 1)
        return self.sector_grid[j][i]

    def sector_at(self, x, y):
        return SECTORS[self.sector_index_at(x, y)]

    def random_floor_cell(self, sector_index=None):
        """ Centro (x, y) de una celda de piso al azar (fuera de los tubos), opcionalmente dentro de un sector """
        cells = [
            (i, j)
            for j, row in enumerate(self.mini_map)
            for i, value in enumerate(row)
            if not value
            and (i, j) not in self.doors
            and (sector_index is None or self.sector_grid[j][i] == sector_index)
        ]
        i, j = random.choice(cells)
        return i + 0.5, j + 0.5

    def is_wall(self, x, y):
        """ True si la celda (x, y) es un muro """
        return (x, y) in self.world_map

    def get_map_size(self):
        return self.width, self.height
