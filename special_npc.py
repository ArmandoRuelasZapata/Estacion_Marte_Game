import pygame as pg
from settings import TEXTURES
import random

class SpecialNPC:
    def __init__(self, game, x, y, speed=0.062):
        self.game = game
        self.x = x
        self.y = y
        self.speed = speed

        # La variante de sprites depende del sector donde aparece
        self.skin = game.map.sector_at(x, y)["skin"]
        self.load_texture(self.skin)
        self.frame_index = 0
        self.animation_timer = 0
        self.image = self.frames[0]
        self.rect = self.image.get_rect(center=(self.x * 100, self.y * 100))
        self.direction = random.choice(["up", "down", "left", "right"])

    def load_texture(self, level):
        """ Sprite de astronauta (igual en todos los módulos); "level" se conserva por compatibilidad """
        image = pg.image.load(TEXTURES["npc_2"]).convert_alpha()
        self.frames = [pg.transform.scale(image, (100, 100))]

    def move(self):
        dx, dy = 0, 0
        if self.direction == "up":
            dy = -self.speed
        elif self.direction == "down":
            dy = self.speed
        elif self.direction == "left":
            dx = -self.speed
        elif self.direction == "right":
            dx = self.speed

        new_x = self.x + dx
        new_y = self.y + dy

        if not self.game.map.is_wall(int(new_x), int(new_y)):
            self.x += dx
            self.y += dy
        else:
            self.direction = random.choice(["up", "down", "left", "right"])

        self.rect.center = (self.x * 100, self.y * 100)

    def animate(self):
        self.animation_timer += 1
        if self.animation_timer >= 10:
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.animation_timer = 0
        self.image = self.frames[self.frame_index]

    def draw(self):
        self.game.screen.blit(self.image, self.game.camera.apply(self.rect))

    def update(self):
        self.move()
        self.animate()
