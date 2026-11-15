from settings import WIDTH, HEIGHT, TILE


class Camera:
    """ Sigue al jugador y convierte coordenadas del mundo a coordenadas de pantalla """

    def __init__(self, map_width, map_height):
        self.width = WIDTH
        self.height = HEIGHT
        self.world_width = map_width * TILE
        self.world_height = map_height * TILE
        self.x = 0
        self.y = 0

    def update(self, target_x, target_y):
        """ Centra la cámara en (target_x, target_y), en celdas, sin salirse de los bordes del mapa """
        max_x = max(0, self.world_width - self.width)
        max_y = max(0, self.world_height - self.height)
        self.x = int(min(max(target_x * TILE - self.width / 2, 0), max_x))
        self.y = int(min(max(target_y * TILE - self.height / 2, 0), max_y))

    def apply(self, rect):
        """ Devuelve una copia del rect (en píxeles del mundo) desplazada a la pantalla """
        return rect.move(-self.x, -self.y)

    def to_screen(self, x, y):
        """ Convierte una posición en celdas a píxeles de pantalla """
        return x * TILE - self.x, y * TILE - self.y
