"""
Vista 3D en primera persona con ray casting (estilo Wolfenstein 3D) sobre el mismo mapa 2D.

Cómo funciona:
  1. Por cada columna de la pantalla se lanza un rayo desde el jugador (NUM_RAYS rayos repartidos en el FOV).
     El rayo avanza de cuadro en cuadro de la cuadrícula (algoritmo DDA: primero cruces con líneas
     horizontales, luego con verticales) hasta chocar con un muro.
  2. Con la distancia al muro se calcula la altura de esa columna: más lejos = más bajita.
     Se corrige el efecto "ojo de pez" multiplicando por cos(ángulo del rayo - ángulo del jugador).
  3. Las paredes usan texturas de paneles metálicos generadas por código, con el color de cada sector.
  4. NPCs, consolas, tanque y proyectiles son sprites 2D "billboard": siempre miran a la cámara y se
     escalan según la distancia.
  5. Columnas de pared y sprites se ordenan de lejos a cerca y se dibujan en ese orden, así un muro
     tapa a un sprite que está detrás.

Todo usa las coordenadas del mapa en celdas (game.player.x / y / angle), igual que la vista 2D.
"""
import math
import random
import pygame as pg
from settings import WIDTH, HEIGHT, SECTORS, RAYCAST
from controls import CONTROLS

FOV = math.radians(RAYCAST["fov_degrees"])
HALF_FOV = FOV / 2
SCALE = RAYCAST["column_width"]          # Ancho en píxeles de cada columna (un rayo por columna)
NUM_RAYS = WIDTH // SCALE
HALF_NUM_RAYS = NUM_RAYS // 2
DELTA_ANGLE = FOV / NUM_RAYS
SCREEN_DIST = (WIDTH / 2) / math.tan(HALF_FOV)  # Distancia a la "pantalla" de proyección
HALF_HEIGHT = HEIGHT // 2
MAX_DEPTH = 64                           # Máximo de cuadros que recorre un rayo

TEX = 256                                # Tamaño de las texturas de pared
HALF_TEX = TEX // 2
SHADE_LEVELS = 6                         # Niveles de oscurecimiento por distancia (precalculados)
SHADE_DEPTH = 11                         # Distancia (en celdas) a la que una pared llega al nivel más oscuro
FOG = (10, 10, 14)


# ====================================================================== texturas generadas
def make_wall_texture(accent, variant, seed):
    """ Panel metálico de la estación con una franja del color del sector.
    variant 0 = paneles con remaches, variant 1 = rejilla de ventilación """
    rng = random.Random(seed)
    tex = pg.Surface((TEX, TEX))
    tex.fill((74, 77, 86))
    # Ruido sutil para que el metal no se vea plano
    for _ in range(1400):
        shade = rng.randint(58, 92)
        tex.set_at((rng.randrange(TEX), rng.randrange(TEX)), (shade, shade + 2, shade + 8))
    half = TEX // 2
    for px in (0, half):
        for py in (0, half):
            panel = pg.Rect(px + 6, py + 6, half - 12, half - 12)
            pg.draw.rect(tex, (84, 88, 98), panel)
            pg.draw.line(tex, (110, 114, 126), panel.topleft, panel.topright, 2)      # Brillo arriba
            pg.draw.line(tex, (110, 114, 126), panel.topleft, panel.bottomleft, 2)    # Brillo izquierda
            pg.draw.line(tex, (48, 50, 58), panel.bottomleft, panel.bottomright, 2)   # Sombra abajo
            pg.draw.line(tex, (48, 50, 58), panel.topright, panel.bottomright, 2)     # Sombra derecha
            for cx, cy in ((panel.left + 8, panel.top + 8), (panel.right - 8, panel.top + 8),
                           (panel.left + 8, panel.bottom - 8), (panel.right - 8, panel.bottom - 8)):
                pg.draw.circle(tex, (130, 134, 146), (cx, cy), 3)
                pg.draw.circle(tex, (50, 52, 60), (cx + 1, cy + 1), 3, 1)
    # Juntas entre paneles
    pg.draw.line(tex, (34, 35, 42), (0, half), (TEX, half), 4)
    pg.draw.line(tex, (34, 35, 42), (half, 0), (half, TEX), 4)
    pg.draw.rect(tex, (34, 35, 42), tex.get_rect(), 4)
    if variant == 1:
        grill = pg.Rect(40, 34, TEX - 80, 70)
        pg.draw.rect(tex, (30, 31, 36), grill)
        for y in range(grill.top + 6, grill.bottom - 4, 9):
            pg.draw.line(tex, (95, 99, 110), (grill.left + 6, y), (grill.right - 6, y), 3)
        pg.draw.rect(tex, (120, 124, 136), grill, 2)
    # Franja de color del sector con luz
    stripe = pg.Rect(0, int(TEX * 0.62), TEX, 18)
    pg.draw.rect(tex, tuple(int(c * 0.55) for c in accent), stripe.inflate(0, 8))
    pg.draw.rect(tex, accent, stripe)
    pg.draw.line(tex, tuple(min(255, c + 70) for c in accent), stripe.topleft, stripe.topright, 2)
    return tex


def shaded(texture, factor):
    """ Copia de la textura oscurecida (factor 1 = igual, 0 = negro) """
    copy = texture.copy()
    level = int(255 * factor)
    copy.fill((level, level, level), special_flags=pg.BLEND_RGB_MULT)
    return copy


def add_soil_texture(surface, color, seed):
    """ Granos de tierra sobre el piso: más grandes y claros cerca de la cámara (abajo), finos a lo lejos """
    rng = random.Random(seed)
    width, height = surface.get_size()
    for _ in range(5000):
        y = int(height * rng.random() ** 0.6)
        depth = y / height                      # 0 = horizonte, 1 = junto a la cámara
        size = 1 + int(depth * 3 * rng.random())
        shade = rng.uniform(0.55, 1.25) * (0.25 + 0.75 * depth)
        grain = tuple(max(0, min(255, int(c * shade))) for c in color)
        pg.draw.rect(surface, grain, (rng.randrange(width), y, size + 1, size))


def vertical_gradient(width, height, top, bottom):
    surface = pg.Surface((width, height))
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        pg.draw.line(surface, color, (0, y), (width, y))
    return surface


# ====================================================================== renderizador
class Renderer3D:
    def __init__(self, game):
        self.game = game
        # textures[sector][variante][lado][nivel de sombra]; el lado 1 (choque horizontal) es un poco más oscuro
        self.textures = []
        for s_index, sector in enumerate(SECTORS):
            variants = []
            for variant in (0, 1):
                base = make_wall_texture(sector["color"], variant, seed=s_index * 10 + variant)
                sides = []
                for side_factor in (1.0, 0.78):
                    sides.append([shaded(base, side_factor * (1 - 0.82 * level / (SHADE_LEVELS - 1)))
                                  for level in range(SHADE_LEVELS)])
                variants.append(sides)
            self.textures.append(variants)
        self.ceiling = vertical_gradient(WIDTH, HALF_HEIGHT, (52, 56, 68), FOG)
        # Piso de cada módulo (se usa el del módulo donde está el jugador); "soil" = tierra roja de Marte
        self.floors = []
        for index, sector in enumerate(SECTORS):
            floor = vertical_gradient(WIDTH, HEIGHT - HALF_HEIGHT, FOG, sector["floor_color"])
            if sector.get("soil"):
                add_soil_texture(floor, sector["floor_color"], seed=index)
            self.floors.append(floor)
        # Domos de vidrio sobre los módulos (necesita numpy; si no está, se usa el techo de degradado)
        self.dome = DomeCeiling(game) if np is not None else None
        self.prompt_font = pg.font.Font(None, 34)
        self.projectile_image = self.make_projectile_image()
        self.depths = [0.0] * NUM_RAYS

    @staticmethod
    def make_projectile_image():
        image = pg.Surface((24, 24), pg.SRCALPHA)
        pg.draw.circle(image, (255, 80, 60, 120), (12, 12), 12)
        pg.draw.circle(image, (255, 200, 160, 255), (12, 12), 6)
        return image

    # ------------------------------------------------------------------ paredes
    def wall_texture(self, tile, side, depth):
        sector = self.game.map.sector_grid[tile[1]][tile[0]]
        variant = 1 if (tile[0] * 7 + tile[1] * 13) % 5 == 0 else 0
        level = min(SHADE_LEVELS - 1, int(depth / SHADE_DEPTH * SHADE_LEVELS))
        return self.textures[sector][variant][side][level]

    def cast_walls(self):
        """ Lanza un rayo por columna y devuelve las columnas de pared como (profundidad, imagen, posición) """
        player = self.game.player
        walls = self.game.map.world_map
        ox, oy, angle = player.x, player.y, player.angle
        map_x, map_y = int(ox), int(oy)
        objects = []
        ray_angle = angle - HALF_FOV + 1e-4
        for ray in range(NUM_RAYS):
            sin_a = math.sin(ray_angle) or 1e-6
            cos_a = math.cos(ray_angle) or 1e-6

            # Cruces con líneas horizontales de la cuadrícula
            y_hor, dy = (map_y + 1, 1) if sin_a > 0 else (map_y - 1e-6, -1)
            depth_hor = (y_hor - oy) / sin_a
            x_hor = ox + depth_hor * cos_a
            delta_depth = dy / sin_a
            dx = delta_depth * cos_a
            tile_hor = None
            for _ in range(MAX_DEPTH):
                tile = (int(x_hor), int(y_hor))
                if tile in walls:
                    tile_hor = tile
                    break
                x_hor += dx
                y_hor += dy
                depth_hor += delta_depth

            # Cruces con líneas verticales de la cuadrícula
            x_vert, dx = (map_x + 1, 1) if cos_a > 0 else (map_x - 1e-6, -1)
            depth_vert = (x_vert - ox) / cos_a
            y_vert = oy + depth_vert * sin_a
            delta_depth = dx / cos_a
            dy = delta_depth * sin_a
            tile_vert = None
            for _ in range(MAX_DEPTH):
                tile = (int(x_vert), int(y_vert))
                if tile in walls:
                    tile_vert = tile
                    break
                x_vert += dx
                y_vert += dy
                depth_vert += delta_depth

            # El choque más cercano gana; offset = en qué parte del muro pegó (0 a 1) para elegir la columna de textura
            if tile_vert is not None and (tile_hor is None or depth_vert < depth_hor):
                depth, tile, side = depth_vert, tile_vert, 0
                y_vert %= 1
                offset = y_vert if cos_a > 0 else 1 - y_vert
            elif tile_hor is not None:
                depth, tile, side = depth_hor, tile_hor, 1
                x_hor %= 1
                offset = 1 - x_hor if sin_a > 0 else x_hor
            else:
                self.depths[ray] = MAX_DEPTH
                ray_angle += DELTA_ANGLE
                continue

            depth *= math.cos(angle - ray_angle)  # Sin esto las paredes se ven curvas ("ojo de pez")
            self.depths[ray] = depth
            proj_height = SCREEN_DIST / (depth + 1e-4)
            texture = self.wall_texture(tile, side, depth)
            tex_x = int(offset * (TEX - SCALE))
            if proj_height < HEIGHT:
                column = texture.subsurface(tex_x, 0, SCALE, TEX)
                column = pg.transform.scale(column, (SCALE, int(proj_height)))
                pos = (ray * SCALE, HALF_HEIGHT - int(proj_height) // 2)
            else:
                # Muy cerca: solo se usa la parte central de la textura que cabe en pantalla
                tex_h = TEX * HEIGHT / proj_height
                column = texture.subsurface(tex_x, HALF_TEX - tex_h / 2, SCALE, tex_h)
                column = pg.transform.scale(column, (SCALE, HEIGHT))
                pos = (ray * SCALE, 0)
            objects.append((depth, column, pos))
            ray_angle += DELTA_ANGLE
        return objects

    # ------------------------------------------------------------------ sprites (billboards)
    def project_sprite(self, x, y, image, scale=1.0, lift=0.0, shade=True, min_dist=0.25):
        """ Proyecta un sprite que siempre mira a la cámara. scale = altura respecto a una pared (1 = igual de alto);
        lift = cuánto flota sobre el piso (en alturas de pared). Devuelve (profundidad, imagen, posición) o None. """
        player = self.game.player
        dx, dy = x - player.x, y - player.y
        dist = math.hypot(dx, dy)
        if dist < min_dist:
            return None
        delta = (math.atan2(dy, dx) - player.angle + math.pi) % math.tau - math.pi
        if abs(delta) > HALF_FOV + 0.4:
            return None
        norm_dist = dist * math.cos(delta)
        if norm_dist < 0.3:
            return None
        wall_h = SCREEN_DIST / norm_dist           # Altura en pantalla de una pared a esa distancia
        proj_h = wall_h * scale
        if proj_h > HEIGHT * 3:
            return None
        proj_w = proj_h * image.get_width() / image.get_height()
        screen_x = (HALF_NUM_RAYS + delta / DELTA_ANGLE) * SCALE
        if screen_x + proj_w / 2 < 0 or screen_x - proj_w / 2 > WIDTH:
            return None
        sprite = pg.transform.scale(image, (max(1, int(proj_w)), max(1, int(proj_h))))
        if shade:
            level = max(0.25, 1 - 0.75 * min(1.0, norm_dist / SHADE_DEPTH))
            sprite.fill((int(255 * level),) * 3, special_flags=pg.BLEND_RGB_MULT)
        floor_y = HALF_HEIGHT + wall_h / 2         # Donde está el piso a esa distancia
        pos = (screen_x - proj_w / 2, floor_y - proj_h - lift * wall_h)
        return norm_dist, sprite, pos

    def collect_sprites(self):
        game = self.game
        items = []
        for npc in game.npcs + game.special_npcs + game.extra_npcs:
            # Los NPCs muy pegados a la cámara no se dibujan (si no, llenarían toda la pantalla)
            items.append((npc.x, npc.y, npc.image, 0.72, 0.0, True, 0.6))
        for mission in game.missions:
            items.extend(mission.billboards())
        for projectile in game.projectiles:
            items.append((projectile.x, projectile.y, self.projectile_image, 0.12, 0.42, False))
        sprites = []
        for item in items:
            projected = self.project_sprite(*item)
            if projected:
                sprites.append(projected)
        return sprites

    # ------------------------------------------------------------------ dibujo
    def draw(self):
        game = self.game
        screen = game.screen
        if self.dome:
            self.dome.draw(screen)
        else:
            screen.blit(self.ceiling, (0, 0))
        sector = game.map.sector_index_at(game.player.x, game.player.y)
        screen.blit(self.floors[sector], (0, HALF_HEIGHT))

        objects = self.cast_walls() + self.collect_sprites()
        objects.sort(key=lambda obj: obj[0], reverse=True)  # De lejos a cerca
        for _, image, pos in objects:
            screen.blit(image, pos)

        # Brazos en primera persona
        game.player.draw_arms(screen)

        # Mira en el centro de la pantalla
        cx, cy = WIDTH // 2, HALF_HEIGHT
        pg.draw.circle(screen, (255, 255, 255), (cx, cy), 3)
        pg.draw.circle(screen, (0, 0, 0), (cx, cy), 4, 1)
        self.draw_prompt(screen)

    def draw_prompt(self, screen):
        """ Aviso de interacción ("[E] RELLENAR TANQUE") abajo al centro, si hay una consola cerca """
        for mission in self.game.missions:
            text = mission.prompt()
            if text:
                surface = self.prompt_font.render(f"[{CONTROLS.label('interact')}]  {text}", True, (255, 220, 120))
                box = surface.get_rect(midbottom=(WIDTH // 2, HEIGHT - 150)).inflate(28, 14)
                panel = pg.Surface(box.size, pg.SRCALPHA)
                panel.fill((0, 0, 0, 190))
                screen.blit(panel, box.topleft)
                pg.draw.line(screen, (200, 30, 30), box.bottomleft, (box.right - 1, box.bottom), 2)
                screen.blit(surface, surface.get_rect(center=box.center))
                return


# ====================================================================== techo: domos de vidrio
try:
    import numpy as np
except ImportError:  # Sin numpy (por ejemplo en algunas versiones para navegador) se usa el techo de degradado
    np = None

DOME_RIBS = 12          # Nervios radiales de cada domo
DOME_RING_SPACING = 1.6  # Separación entre anillos del armazón (en celdas)
DOME_RIB_WIDTH = 0.07   # Grosor de las vigas (en celdas)
SKY_TOP = (12, 12, 32)        # Cielo de Marte al atardecer: oscuro arriba...
SKY_HORIZON = (178, 112, 82)  # ...y ocre rosado cerca del horizonte
FRAME_COLOR = (112, 118, 134)
GLASS_TINT = (40, 80, 100)
METAL_TOP = (52, 56, 68)


class DomeCeiling:
    """ Techo calculado píxel por píxel ("ceiling casting"), a baja resolución y con numpy.

    Para cada píxel del techo se sabe hacia qué ángulo mira (la columna) y a qué distancia está el techo
    (la fila: más cerca del horizonte = más lejos). Con eso se obtiene el punto del mapa que se ve.
      - Si el punto está dentro de un módulo circular, es un domo de vidrio: vigas radiales que convergen
        al centro del módulo, anillos concéntricos, placa en la cima y borde del color del módulo.
        Entre las vigas se ve el cielo de Marte (con estrellas, la Tierra y Fobos) a través del vidrio.
      - Si no (los tubos), se ve el techo metálico.
    Durante el impacto de una tormenta solar el vidrio se tiñe de naranja.
    """

    def __init__(self, game):
        self.game = game
        self.scale = RAYCAST.get("ceiling_scale", 4)
        self.cw, self.ch = WIDTH // self.scale, HALF_HEIGHT // self.scale
        cols = (np.arange(self.cw) + 0.5) * self.scale
        rows = (np.arange(self.ch) + 0.5) * self.scale
        # Mismo reparto de ángulos que los rayos de las paredes
        self.rel = -HALF_FOV + (cols / SCALE) * DELTA_ANGLE
        depth = SCREEN_DIST / (2 * (HALF_HEIGHT - rows))            # Distancia perpendicular al techo por fila
        self.dist = (depth[:, None] / np.cos(self.rel)[None, :]).astype(np.float32)  # Distancia a lo largo de cada rayo
        self.rel = self.rel.astype(np.float32)
        self.fog = np.clip(1 - depth / 14, 0.12, 1.0)[:, None, None]
        t = (rows / HALF_HEIGHT)[:, None, None]
        self.metal = np.array(METAL_TOP) * (1 - t) + np.array(FOG) * t  # (filas, 1, 3)
        self.sky = self.build_sky().astype(np.float32)
        self.surface = pg.Surface((self.cw, self.ch))
        self.modules = [(s["center"][0], s["center"][1], s["radius"], np.array(s["color"], dtype=np.float32))
                        for s in SECTORS]
        # Valores precalculados para que draw() sea rápido
        self.metal_image = np.broadcast_to(self.metal, (self.ch, self.cw, 3)).reshape(-1, 3).astype(np.float32)
        self.fog_rows = self.fog[:, 0, 0].astype(np.float32)
        self.glass_tint = np.array(GLASS_TINT, dtype=np.float32) * 0.16
        self.storm_color = np.array((255, 140, 0), dtype=np.float32)
        self.frame_color = np.array(FRAME_COLOR, dtype=np.float32)
        self.fog_color = np.array(FOG, dtype=np.float32)

    def build_sky(self):
        """ Panorama del cielo de Marte (una vuelta completa): degradado, estrellas, la Tierra y Fobos """
        width = int(self.cw * math.tau / FOV)
        rng = np.random.default_rng(7)
        t = (np.arange(self.ch) / (self.ch - 1)) ** 1.7                # 0 arriba, 1 en el horizonte
        sky = (np.array(SKY_TOP) * (1 - t[:, None]) + np.array(SKY_HORIZON) * t[:, None])[:, None, :]
        sky = np.repeat(sky, width, axis=1).astype(np.float32)
        # Estrellas: más visibles arriba, donde el cielo es más oscuro
        count = width * self.ch // 60
        ys = (rng.random(count) ** 1.8 * self.ch * 0.8).astype(int)
        xs = rng.integers(0, width, count)
        bright = rng.uniform(90, 255, count)[:, None] * (1 - t[ys])[:, None]
        sky[ys, xs] = np.maximum(sky[ys, xs], bright)
        # La Tierra: desde Marte se ve como una estrella azul brillante al atardecer
        ex, ey = int(width * 0.30), int(self.ch * 0.42)
        sky[ey - 1:ey + 2, ex - 1:ex + 2] = (60, 120, 220)
        sky[ey, ex] = (170, 210, 255)
        # Fobos, la luna más grande de Marte (forma irregular y gris)
        px, py = int(width * 0.72), int(self.ch * 0.22)
        sky[py - 2:py + 2, px - 3:px + 3] = (120, 112, 104)
        sky[py - 1:py + 1, px - 2:px + 1] = (150, 142, 132)
        return sky

    def draw(self, screen):
        """ Calcula el techo de este frame. Para que sea rápido, las cuentas caras (ángulo, vigas, cielo)
        solo se hacen para los píxeles que caen dentro de algún domo. """
        player = self.game.player
        angles = np.float32(player.angle) + self.rel
        wx = (np.float32(player.x) + np.cos(angles)[None, :] * self.dist).ravel()
        wy = (np.float32(player.y) + np.sin(angles)[None, :] * self.dist).ravel()
        sky_cols = ((angles % math.tau) / math.tau * self.sky.shape[1]).astype(np.int32) % self.sky.shape[1]

        image = self.metal_image.copy()          # (filas * columnas, 3): techo metálico de fondo
        storm = self.game.storm_mission.state == "impact"
        pulse = (math.sin(pg.time.get_ticks() / 120) + 1) / 2
        fog_flat = self.fog_rows

        for cx, cy, radius, color in self.modules:
            d2 = (wx - cx) ** 2 + (wy - cy) ** 2
            idx = np.flatnonzero(d2 < radius * radius)
            if idx.size == 0:
                continue
            dx, dy = wx[idx] - cx, wy[idx] - cy
            d = np.sqrt(d2[idx])
            theta = np.arctan2(dy, dx)
            row, col = idx // self.cw, idx % self.cw

            rib_phase = theta * DOME_RIBS / math.tau
            rib = (np.abs(rib_phase - np.round(rib_phase)) * math.tau * d / DOME_RIBS < DOME_RIB_WIDTH) & (d > 0.5)
            ring_phase = d / DOME_RING_SPACING
            ring = np.abs(ring_phase - np.round(ring_phase)) * DOME_RING_SPACING < DOME_RIB_WIDTH * 0.8
            structure = rib | ring | (d < 0.35)  # Vigas, anillos y la placa de la cima
            rim = d > radius - 0.3
            fog = fog_flat[row][:, None]

            # Vidrio: cielo con un tinte frío, un poco del color del módulo y brillo naranja con tormenta
            out = self.sky[row, sky_cols[col]] * np.float32(0.84) + (self.glass_tint + color * np.float32(0.05))
            if storm:
                out = out * np.float32(1 - 0.35 * pulse) + self.storm_color * np.float32(0.35 * pulse)
            # Armazón metálico (solo los píxeles que son viga): luz según el lado de la viga y niebla con la distancia
            beams = np.flatnonzero(structure)
            if beams.size:
                shade = (np.float32(0.78) + np.float32(0.22) * np.cos(theta[beams] - np.float32(0.8)))[:, None]
                f = fog[beams]
                out[beams] = self.frame_color * shade * f + self.fog_color * (1 - f)
            edges = np.flatnonzero(rim)
            if edges.size:
                f = fog[edges]
                out[edges] = color * np.float32(0.55) * f + self.fog_color * (1 - f)  # Borde del domo, más tenue
            image[idx] = out

        pixels = image.reshape(self.ch, self.cw, 3).astype(np.uint8)
        pg.surfarray.blit_array(self.surface, np.ascontiguousarray(pixels.swapaxes(0, 1)))
        screen.blit(pg.transform.scale(self.surface, (WIDTH, HALF_HEIGHT)), (0, 0))
