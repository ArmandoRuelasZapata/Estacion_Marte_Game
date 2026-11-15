import pygame as pg

class Button:
    def __init__(self, x, y, width, height, text, action=None, texture=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.action = action
        self.texture = texture  # Textura para el botón

        # Inicializar el rectángulo del botón
        self.rect = pg.Rect(self.x, self.y, self.width, self.height)
        self.font = pg.font.Font(None, 36)
        self.text_surface = self.font.render(self.text, True, (255, 255, 255))

        # Si se ha proporcionado una textura, la cargamos
        if self.texture:
            self.image = pg.image.load(self.texture)
            self.image = pg.transform.scale(self.image, (self.width, self.height))  # Ajustar tamaño al botón
        else:
            self.image = None

    def draw(self, screen):
        """ Dibuja el botón en la pantalla """
        if self.image:
            # Si el botón tiene una textura, la dibujamos
            screen.blit(self.image, self.rect.topleft)
        else:
            # Si no hay textura, dibujamos un rectángulo simple
            pg.draw.rect(screen, (0, 0, 0), self.rect)

        # Dibujar el texto centrado en el botón
        screen.blit(self.text_surface, (self.rect.centerx - self.text_surface.get_width() // 2, 
                                       self.rect.centery - self.text_surface.get_height() // 2))

    def is_clicked(self):
        """ Verifica si el botón ha sido presionado """
        mouse_x, mouse_y = pg.mouse.get_pos()
        if self.rect.collidepoint(mouse_x, mouse_y):
            if pg.mouse.get_pressed()[0]:  # Si se presiona el botón izquierdo del ratón
                return True
        return False

