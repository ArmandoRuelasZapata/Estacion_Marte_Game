import pygame as pg
import math

class Projectile:
    def __init__(self, game, x, y, angle):
        self.game = game
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = 0.2  # Velocidad del proyectil
        self.image = pg.Surface((10, 5))
        self.image.fill((255, 0, 0))  # Color rojo para el proyectil
        self.rect = self.image.get_rect(center=(self.x * 100, self.y * 100))
        
    def move(self):
        """ Mueve el proyectil en la dirección del ángulo del jugador y verifica colisiones con el mapa """
        dx = self.speed * math.cos(self.angle)
        dy = self.speed * math.sin(self.angle)
        new_x = self.x + dx
        new_y = self.y + dy
        
        # Verifica si el proyectil colisiona con un muro antes de moverse
        if not self.game.map.is_wall(int(new_x), int(new_y)):
            self.x += dx
            self.y += dy
            self.rect.center = (self.x * 100, self.y * 100)
        else:
            # Si colisiona, elimina el proyectil
            self.game.projectiles.remove(self)
    
    def draw(self):
        """ Dibuja el proyectil en la pantalla """
        self.game.screen.blit(self.image, self.game.camera.apply(self.rect))

    def check_collision(self, entity):
        """ Verifica si el proyectil choca con una entidad """
        if self.rect.colliderect(entity.rect):
            return True
        return False
