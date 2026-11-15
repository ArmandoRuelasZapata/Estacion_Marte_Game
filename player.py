import os
import pygame as pg
from settings import TEXTURES
from settings import PLAYER_POS, PLAYER_ANGLE, PLAYER_SPEED, PLAYER_ROT_SPEED, MOUSE_SENSITIVITY
import math
from controls import CONTROLS

class Player:
    def __init__(self, game, x=None, y=None):
        self.game = game
        self.x, self.y = (x, y) if x is not None else PLAYER_POS
        self.angle = PLAYER_ANGLE
        self.speed = PLAYER_SPEED
        self.rot_speed = PLAYER_ROT_SPEED

        # Brazos en primera persona
        self.arms_image = None
        self.arms_base_x = 0
        self.arms_base_y = 0
        arms_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brazos.png")
        if not os.path.exists(arms_path):
            arms_path = "brazos.png"
        if os.path.exists(arms_path):
            try:
                raw_arms = pg.image.load(arms_path).convert_alpha()
                img_w = 1650
                img_h = int(raw_arms.get_height() * (img_w / raw_arms.get_width()))
                self.arms_image = pg.transform.smoothscale(raw_arms, (img_w, img_h))
                self.arms_base_x = (1600 - img_w) // 2
                self.arms_base_y = 900 - img_h
            except Exception as e:
                print("Error cargando brazos.png:", e)
                self.arms_image = None

        self.bob_timer = 0.0
        self.recoil = 0.0
        self.is_moving = False

        # Cargar animaciones
        self.frames = [
            pg.image.load("textures/Jugador_Frame1.png").convert_alpha(),
            pg.image.load("textures/Jugador_Frame2.png").convert_alpha(),
            pg.image.load("textures/Jugador_Frame3.png").convert_alpha()
        ]
        self.static_image = pg.image.load("textures/Jugador_Estatico.png").convert_alpha()
        self.frame_index = 0
        self.animation_timer = 0

        self.image = pg.transform.scale(self.static_image, (50, 50))
        self.rect = self.image.get_rect(center=(self.x * 100, self.y * 100))

    RADIUS = 0.3  # Radio del jugador para chocar con los muros (evita "meter la cara" en la pared en 3D)

    def movement(self):
        """ Movimiento en primera persona: W/S avanza y retrocede hacia donde mira el jugador, A/D se desliza
        a los lados y ←/→ (o el stick derecho) gira. Funciona igual en la vista 3D y en el mapa 2D. """
        sin_a, cos_a = math.sin(self.angle), math.cos(self.angle)
        speed = PLAYER_SPEED * self.game.delta_time
        keys = pg.key.get_pressed()
        pad_strafe, pad_forward, pad_turn = CONTROLS.move_axes()
        forward = max(-1.0, min(1.0, keys[pg.K_w] - keys[pg.K_s] + pad_forward))
        strafe = max(-1.0, min(1.0, keys[pg.K_d] - keys[pg.K_a] + pad_strafe))

        # Adelante = dirección de la mirada (cos, sin). Derecha = (-sin, cos), porque el eje y crece hacia abajo.
        dx = (cos_a * forward - sin_a * strafe) * speed
        dy = (sin_a * forward + cos_a * strafe) * speed
        magnitude = math.hypot(dx, dy)
        if magnitude > speed:  # En diagonal no se va más rápido
            dx, dy = dx * speed / magnitude, dy * speed / magnitude
        self.move_with_collision(dx, dy)

        turn = keys[pg.K_RIGHT] - keys[pg.K_LEFT] + pad_turn
        mouse_dx, _ = pg.mouse.get_rel() if pg.mouse.get_focused() else (0, 0)
        self.angle = (self.angle + PLAYER_ROT_SPEED * self.game.delta_time * turn + mouse_dx * MOUSE_SENSITIVITY) % math.tau
        moving = (dx != 0 or dy != 0)
        self.is_moving = moving
        if moving:
            self.bob_timer += self.game.delta_time * 0.007
        else:
            self.bob_timer += self.game.delta_time * 0.002
        if self.recoil > 0:
            self.recoil = max(0.0, self.recoil - self.game.delta_time * 0.006)
        self.animate(moving)

    def on_shoot(self):
        """ Activa retroceso de los brazos al disparar """
        self.recoil = 1.0

    def draw_arms(self, screen):
        """ Dibuja los brazos del personaje en primera persona con balanceo suave y retroceso """
        if not self.arms_image:
            return

        if self.is_moving:
            bob_x = math.sin(self.bob_timer) * 9
            bob_y = abs(math.sin(self.bob_timer * 2)) * 8 + self.recoil * 26
        else:
            bob_x = math.sin(self.bob_timer) * 3
            bob_y = (math.sin(self.bob_timer) + 1) * 2 + self.recoil * 26

        pos_x = self.arms_base_x + bob_x
        pos_y = self.arms_base_y + bob_y
        screen.blit(self.arms_image, (pos_x, pos_y))

    def move_with_collision(self, dx, dy):
        """ Mueve en cada eje por separado: si un eje choca, el otro sigue (se desliza junto a la pared) """
        r = self.RADIUS
        if not self.game.map.is_wall(int(self.x + dx + math.copysign(r, dx)), int(self.y)):
            self.x += dx
        if not self.game.map.is_wall(int(self.x), int(self.y + dy + math.copysign(r, dy))):
            self.y += dy

    def animate(self, moving):
        if moving:
            self.animation_timer += 1
            if self.animation_timer >= 10:
                self.frame_index = (self.frame_index + 1) % len(self.frames)
                self.animation_timer = 0
            self.image = pg.transform.scale(self.frames[self.frame_index], (100, 100))
        else:
            self.image = pg.transform.scale(self.static_image, (100, 100))

    def check_wall_collision(self, dx, dy):
        new_x = self.x + dx
        new_y = self.y + dy
        if self.game.map.is_wall(int(new_x), int(new_y)):
            return True
        return False

    def draw(self):
        screen_x, screen_y = self.game.camera.to_screen(self.x, self.y)
        self.game.screen.blit(self.image, (screen_x - self.image.get_width() // 2, screen_y - self.image.get_height() // 2))
        line_length = 50
        end_x = screen_x + line_length * math.cos(self.angle)
        end_y = screen_y + line_length * math.sin(self.angle)
        pg.draw.line(self.game.screen, (255, 0, 0), (screen_x, screen_y), (end_x, end_y), 3)

    def update(self):
        self.movement()
        return self.x, self.y

    @property
    def pos(self):
        return self.x, self.y

    @property
    def map_pos(self):
        return int(self.x), int(self.y)
