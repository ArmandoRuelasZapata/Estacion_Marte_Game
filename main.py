import math
import os
import time
import pygame as pg
import sys
from settings import RES, FPS, SECTORS, TILE, MUSIC_VOLUME, SFX_VOLUME, SOL_DURATION, FOOTSTEP_SOUND, PLAYER_CAN_SHOOT
from map import Map
from camera import Camera
from player import Player
from npc import NPC
from special_npc import SpecialNPC
from extra_npc import ExtraNPC
from projectile import Projectile
from menu import Menu, ListScreen
from resources import Resources
from missions import EnergyMission, SolarStormMission
from greenhouse import GreenhouseMission
from comms import CommsMission
from controls import CONTROLS
from hud import Hud
from render3d import Renderer3D


class VideoBackground:
    """ Fondo animado a partir de un video .mp4 en bucle para la portada y el menú (requiere OpenCV).
    Los cuadros se leen al vuelo, así no se carga todo el video en memoria. """
    def __init__(self, size, path):
        import cv2
        self.cv2 = cv2
        self.size = size
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise IOError(f"No se pudo abrir el video {path}")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_ms = 1000.0 / (fps if fps and fps > 0 and not math.isnan(fps) else 30.0)
        self.next_frame_at = 0
        self.current = None

    def read_frame(self):
        ret, frame = self.cap.read()
        if not ret:  # Fin del video: vuelve al inicio
            self.cap.set(self.cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if not ret:
                return
        frame = self.cv2.resize(frame, self.size, interpolation=self.cv2.INTER_LINEAR)
        rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
        self.current = pg.image.frombuffer(rgb.tobytes(), self.size, 'RGB')

    def draw(self, screen):
        now = pg.time.get_ticks()
        if self.current is None or now >= self.next_frame_at:
            self.read_frame()
            # Si el juego se atrasó mucho (por ejemplo, tras la cinemática), no intenta recuperar cuadros
            self.next_frame_at = max(self.next_frame_at + self.frame_ms, now)
        if self.current:
            screen.blit(self.current, (0, 0))
        else:
            screen.fill((0, 0, 0))


class AnimatedGifBackground:
    """ Fondo animado a partir de un GIF en bucle para la portada y el menú """
    def __init__(self, size, path):
        self.frames = []
        self.durations = []
        self.total_duration = 0
        try:
            from PIL import Image, ImageSequence
            img = Image.open(path)
            for frame in ImageSequence.Iterator(img):
                d = frame.info.get('duration', 100)
                if d <= 0:
                    d = 100
                self.durations.append(d)
                rgba = frame.convert('RGBA')
                surf = pg.image.fromstring(rgba.tobytes(), rgba.size, 'RGBA')
                surf = pg.transform.smoothscale(surf, size)
                self.frames.append(surf.convert())
            self.total_duration = sum(self.durations)
        except Exception as e:
            print(f"Error cargando GIF animado ({path}):", e)

    def draw(self, screen):
        screen.fill((0, 0, 0))
        if not self.frames:
            return
        if self.total_duration > 0:
            t = pg.time.get_ticks() % self.total_duration
            elapsed = 0
            current_frame = self.frames[0]
            for frame, dur in zip(self.frames, self.durations):
                elapsed += dur
                if t < elapsed:
                    current_frame = frame
                    break
        else:
            current_frame = self.frames[0]
        screen.blit(current_frame, (0, 0))

MINIMAP_CELL = 4         # Píxeles por celda en el minimapa
MINIMAP_WALL = (30, 30, 30)


class Game:
    def __init__(self):
        pg.init()
        CONTROLS.init()  # Mandos de Xbox y compatibles (ver controls.py)
        self.screen = pg.display.set_mode(RES)
        self.clock = pg.time.Clock()
        self.delta_time = 1
        self.score = 0
        self.time_left = SOL_DURATION

        # Sector inicial opcional: "python main.py 2" arranca directo en el sector 2, sin portada (lo usa el lanzador web)
        self.start_sector = self.parse_start_sector()
        self.music_volume = MUSIC_VOLUME
        self.sfx_volume = SFX_VOLUME
        self.current_sector = None
        self.current_music = None

        self.sector_message = ""
        self.sector_message_timer = 0


        self.map = Map(self)
        self.camera = Camera(self.map.width, self.map.height)
        self.minimap_base = self.build_minimap()
        self.hud = Hud(self)
        self.renderer = Renderer3D(self)

        self.shoot_sound = pg.mixer.Sound('music/projectile.MP3')
        self.hit_sound = pg.mixer.Sound('music/hit.MP3')
        # Los pasos usan un canal reservado para poder pararlos al instante sin cortar otros efectos
        pg.mixer.set_reserved(1)
        self.footstep_channel = pg.mixer.Channel(0)
        self.footstep_sound = pg.mixer.Sound(FOOTSTEP_SOUND)
        self.set_sfx_volume(self.sfx_volume)

        self.active_terminal = None
        self.end_reason = ""
        self.new_game()

        # Estados: "menu" (portada y menú), "playing" (partida), "paused" (pausa),
        # "terminal" (ventana de una misión abierta) y "game_over" (misión cumplida o fallida)
        self.menu = Menu(self)
        self.menu.screens["main"].items[0]["action"] = self.start_mission_with_cinematic
        # Fondo animado del menú: el video .mp4 (con OpenCV); si no se puede, el GIF de respaldo
        base_dir = os.path.dirname(os.path.abspath(__file__))
        video_path = os.path.join(base_dir, "Secuencia cósmica de Marte y estación espacial.mp4")
        gif_path = os.path.join(base_dir, "Secuencia cósmica de Marte y estación espacial.gif")
        try:
            self.menu.background = VideoBackground(self.screen.get_size(), video_path)
        except Exception as e:
            print("Aviso: no se pudo usar el video de fondo, se usa el GIF:", e)
            if os.path.exists(gif_path):
                self.menu.background = AnimatedGifBackground(self.screen.get_size(), gif_path)
        self.frozen_frame = None  # Imagen del juego que se muestra detrás de la pausa o de una terminal
        self.pause_screen = ListScreen(self.menu, [
            {"label": "REANUDAR",
             "description": "Vuelve a la misión.",
             "action": self.resume},
            {"label": "REINICIAR MISIÓN",
             "description": "Empieza la misión desde el principio. Perderás el progreso actual.",
             "action": self.start_game},
            {"label": "SALIR",
             "description": "Abandona la misión y vuelve al menú principal.",
             "action": self.exit_to_menu,
             "separator": True},
        ], on_back=self.resume, heading="EN PAUSA", backdrop=True)
        self.failure_screen = ListScreen(self.menu, [
            {"label": "REINICIAR MISIÓN",
             "description": lambda: f"{self.end_reason} ¡Inténtalo con otra estrategia!",
             "action": self.start_game},
            {"label": "SALIR",
             "description": "Vuelve al menú principal.",
             "action": self.exit_to_menu,
             "separator": True},
        ], heading="MISIÓN FALLIDA", backdrop=True)
        self.victory_screen = ListScreen(self.menu, [
            {"label": "JUGAR OTRO SOL",
             "description": lambda: self.end_reason,
             "action": self.start_game},
            {"label": "SALIR",
             "description": "Vuelve al menú principal.",
             "action": self.exit_to_menu,
             "separator": True},
        ], heading="MISIÓN CUMPLIDA", backdrop=True)
        self.end_screen = self.failure_screen

        if len(sys.argv) > 1:
            self.state = "playing"
            self.set_mouse_capture(True)
        else:
            self.state = "menu"
            self.set_mouse_capture(False)
            self.menu.open()

    def set_mouse_capture(self, capture):
        """ Oculta y captura el cursor en modo juego, o lo libera y muestra en menús/pausas """
        pg.mouse.set_visible(not capture)
        pg.event.set_grab(capture)
        if capture:
            pg.mouse.get_rel()

    def start_mission_with_cinematic(self):
        """ Inicia la misión reproduciendo primero la cinemática si existe """
        video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cinematica.mp4")
        if not os.path.exists(video_path):
            video_path = "cinematica.mp4"
        if os.path.exists(video_path):
            self.play_cinematic(video_path)
        self.start_game()

    def play_cinematic(self, video_path):
        """ Reproduce la cinemática MP4 sin sonido, a pantalla completa, sin recortes y con transiciones fluidas """
        try:
            import cv2
        except ImportError:
            print("Aviso: no se puede reproducir la cinemática porque falta OpenCV (pip install opencv-python)")
            return

        # 1. Fundido y corte de la música del menú
        pg.mixer.music.fadeout(500)

        # 2. Transición suave de salida del menú (fade-out a negro)
        screen_w, screen_h = self.screen.get_size()
        fade_surf = pg.Surface((screen_w, screen_h))
        fade_surf.fill((0, 0, 0))
        for alpha in range(0, 256, 18):
            self.menu.background.draw(self.screen)
            self.menu.screens["main"].draw(self.screen)
            fade_surf.set_alpha(alpha)
            self.screen.blit(fade_surf, (0, 0))
            pg.display.flip()
            self.clock.tick(60)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or math.isnan(fps):
            fps = 30.0

        frame_interval = 1.0 / fps
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fade_in_frames = min(20, max(6, int(fps * 0.6)))
        fade_out_frames = min(24, max(6, int(fps * 0.7)))

        # Texto para indicar que se puede saltar
        skip_hint = pg.font.Font(None, 28).render("Presiona cualquier tecla o botón para saltar", True, (200, 200, 200))
        skip_hint.set_alpha(170)
        hint_pos = (screen_w - skip_hint.get_width() - 24, screen_h - skip_hint.get_height() - 20)
        skip_events = (pg.KEYDOWN, pg.MOUSEBUTTONDOWN, pg.JOYBUTTONDOWN, pg.CONTROLLERBUTTONDOWN)

        # Descarta la tecla o botón con el que se eligió "Iniciar" para que no salte el video de inmediato
        pg.event.clear()

        frame_idx = 0
        start_time = time.perf_counter()

        while True:
            # Eventos: cualquier tecla, clic o botón del control salta la cinemática
            skip = False
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    cap.release()
                    self.quit_game()
                elif event.type in skip_events:
                    skip = True
                    break

            if skip:
                # Fundido a negro rápido al saltar
                for a in range(0, 256, 30):
                    fade_surf.set_alpha(a)
                    self.screen.blit(fade_surf, (0, 0))
                    pg.display.flip()
                    self.clock.tick(60)
                break

            ret, frame = cap.read()
            if not ret:
                break

            # Escalar proporcionalmente para llenar la pantalla sin deformar ni recortar
            h, w = frame.shape[:2]
            scale = min(screen_w / w, screen_h / h)
            new_w, new_h = int(w * scale), int(h * scale)
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            frame_surf = pg.image.frombuffer(rgb.data, (new_w, new_h), 'RGB')

            self.screen.fill((0, 0, 0))
            x_offset = (screen_w - new_w) // 2
            y_offset = (screen_h - new_h) // 2
            self.screen.blit(frame_surf, (x_offset, y_offset))

            # Fundido de entrada suave (fade-in)
            if frame_idx < fade_in_frames:
                alpha = int(255 * (1.0 - (frame_idx / fade_in_frames)))
                fade_surf.set_alpha(alpha)
                self.screen.blit(fade_surf, (0, 0))

            # Fundido de salida suave (fade-out) cerca del final
            elif total_frames > 0 and frame_idx >= (total_frames - fade_out_frames):
                out_progress = (frame_idx - (total_frames - fade_out_frames)) / fade_out_frames
                alpha = int(255 * min(1.0, out_progress))
                fade_surf.set_alpha(alpha)
                self.screen.blit(fade_surf, (0, 0))

            self.screen.blit(skip_hint, hint_pos)
            pg.display.flip()
            frame_idx += 1

            # Sincronización precisa con el reloj real para 30 FPS exactos y fluidos
            target_time = start_time + (frame_idx * frame_interval)
            now = time.perf_counter()
            sleep_time = target_time - now
            if sleep_time > 0:
                time.sleep(sleep_time)

        cap.release()

        # Pantalla en negro antes de renderizar el primer frame del juego
        self.screen.fill((0, 0, 0))
        pg.display.flip()

    def start_game(self):
        """ Empieza una partida nueva desde el menú """
        self.new_game()
        self.state = "playing"
        self.set_mouse_capture(True)

    def set_music_volume(self, volume):
        self.music_volume = round(min(max(volume, 0.0), 1.0), 1)
        pg.mixer.music.set_volume(self.music_volume)

    def set_sfx_volume(self, volume):
        self.sfx_volume = round(min(max(volume, 0.0), 1.0), 1)
        self.shoot_sound.set_volume(self.sfx_volume)
        self.hit_sound.set_volume(self.sfx_volume)
        self.footstep_sound.set_volume(self.sfx_volume)

    def parse_start_sector(self):
        """ Lee el sector inicial (1, 2 o 3) de la línea de comandos; si no es válido usa el 1 """
        try:
            number = int(sys.argv[1])
        except (IndexError, ValueError):
            return 0
        return min(max(number, 1), len(SECTORS)) - 1

    def spawn(self, entity_class, sector_index=None):
        """ Crea una entidad en una celda de piso al azar (de un sector concreto o de todo el mapa) """
        x, y = self.map.random_floor_cell(sector_index)
        return entity_class(self, x, y)

    def play_sector_music(self, sector):
        # Si el módulo usa la misma pista que ya suena, no se reinicia
        if sector["music"] == self.current_music:
            return
        self.current_music = sector["music"]
        pg.mixer.music.load(sector["music"])
        pg.mixer.music.set_volume(self.music_volume)
        pg.mixer.music.play(-1, 0.0, fade_ms=1000)

    def update_footsteps(self):
        """ Reproduce los pasos en bucle mientras el jugador camina y los corta cuando se detiene """
        if self.player.is_moving:
            if not self.footstep_channel.get_busy():
                self.footstep_channel.play(self.footstep_sound, loops=-1)
        elif self.footstep_channel.get_busy():
            self.footstep_channel.fadeout(120)

    def stop_footsteps(self):
        self.footstep_channel.stop()

    def show_sector_message(self, text):
        self.sector_message = text
        self.sector_message_timer = pg.time.get_ticks() + 3000

    def new_game(self):
        self.score = 0
        self.time_left = SOL_DURATION
        start_x, start_y = SECTORS[self.start_sector]["start"]
        self.player = Player(self, start_x, start_y)
        self.camera.update(self.player.x, self.player.y)
        # Un NPC de cada tipo por sector
        sector_ids = range(len(SECTORS))
        self.npcs = [self.spawn(NPC, i) for i in sector_ids]
        self.special_npcs = [self.spawn(SpecialNPC, i) for i in sector_ids]
        self.extra_npcs = [self.spawn(ExtraNPC, i) for i in sector_ids]
        self.projectiles = []
        self.resources = Resources()
        self.energy_mission = EnergyMission(self)
        self.storm_mission = SolarStormMission(self)
        self.greenhouse_mission = GreenhouseMission(self)
        # El orden importa: es el orden de prioridad de las alertas en pantalla
        self.comms_mission = CommsMission(self)
        self.missions = [self.energy_mission, self.storm_mission, self.greenhouse_mission, self.comms_mission]
        self.active_terminal = None
        self.end_reason = ""
        self.current_music = None   # La música arranca de nuevo en cada partida
        self.current_sector = None  # Fuerza la música y el mensaje del sector en el siguiente update

    # ------------------------------------------------------------------ pausas, ventanas y fin de partida
    def freeze_frame(self, gray=True):
        """ Copia la última imagen del juego oscurecida (y en escala de grises si gray=True) """
        frame = pg.transform.grayscale(self.screen) if gray else self.screen.copy()
        shade = pg.Surface(frame.get_size())
        shade.fill((0, 0, 0))
        shade.set_alpha(140 if gray else 150)
        frame.blit(shade, (0, 0))
        return frame

    def open_overlay(self, state, screen):
        """ Detiene el juego y muestra un menú (pausa o fin de misión) sobre la imagen congelada """
        self.set_mouse_capture(False)
        self.stop_footsteps()
        self.frozen_frame = self.freeze_frame()
        self.state = state
        screen.reset()
        screen.enter()

    def pause(self):
        pg.mixer.music.pause()
        self.open_overlay("paused", self.pause_screen)

    def resume(self):
        pg.mixer.music.unpause()
        self.state = "playing"
        self.set_mouse_capture(True)

    def end_mission(self, success, reason):
        """ Termina la partida: misión cumplida (sobreviviste al sol) o fallida (con la explicación) """
        self.end_reason = reason
        self.end_screen = self.victory_screen if success else self.failure_screen
        pg.mixer.music.fadeout(1500)
        self.draw()  # La imagen congelada debe mostrar el estado final
        self.open_overlay("game_over", self.end_screen)

    def open_terminal(self, window):
        """ Abre la ventana de una misión: el juego se detiene detrás de ella """
        self.set_mouse_capture(False)
        self.stop_footsteps()
        self.draw()
        self.frozen_frame = self.freeze_frame(gray=False)
        self.active_terminal = window
        window.start()
        self.state = "terminal"

    def close_terminal(self):
        self.active_terminal = None
        self.state = "playing"
        self.set_mouse_capture(True)

    def run_terminal_frame(self):
        terminal = self.active_terminal
        for event in CONTROLS.events(getattr(terminal, "input_context", "terminal")):
            if event.type == pg.QUIT:
                self.quit_game()
            terminal.handle_event(event)
            if self.state != "terminal":
                return
        terminal.update(self.delta_time)
        if self.state != "terminal":
            return
        self.screen.blit(self.frozen_frame, (0, 0))
        terminal.draw(self.screen)
        pg.display.flip()

    def exit_to_menu(self):
        self.set_mouse_capture(False)
        self.state = "menu"
        self.menu.open("main")

    def quit_game(self):
        pg.quit()
        sys.exit()

    # ------------------------------------------------------------------ juego
    def check_events(self):
        for event in CONTROLS.events("playing"):
            if event.type == pg.QUIT:
                self.quit_game()
            elif event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
                self.pause()
                return
            elif event.type == pg.KEYDOWN and event.key == pg.K_SPACE:
                self.shoot_projectile()
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                self.shoot_projectile()
            elif event.type == pg.KEYDOWN and event.key == pg.K_e:
                for mission in self.missions:
                    window = mission.try_interact()
                    if window:
                        self.open_terminal(window)
                        return

    def shoot_projectile(self):
        if not PLAYER_CAN_SHOOT:  # Disparo desactivado en settings.py
            return
        projectile = Projectile(self, self.player.x, self.player.y, self.player.angle)
        self.projectiles.append(projectile)
        self.shoot_sound.play()
        self.player.on_shoot()

    def check_sector_change(self):
        """ Detecta cuando el jugador cruza a otro sector: cambia la música y muestra su nombre """
        index = self.map.sector_index_at(self.player.x, self.player.y)
        if index != self.current_sector:
            self.current_sector = index
            sector = SECTORS[index]
            self.play_sector_music(sector)
            self.show_sector_message(sector["name"])

    def update(self):
        self.player.update()
        self.update_footsteps()
        self.camera.update(self.player.x, self.player.y)
        self.check_sector_change()

        for npc in self.npcs:
            npc.update()
        for snpc in self.special_npcs:
            snpc.update()
        for enpc in self.extra_npcs:
            enpc.update()
        self.update_projectiles()

        # Recursos y misiones
        self.resources.update(self.delta_time, energy_reserve=self.energy_mission.in_reserve)
        for mission in self.missions:
            mission.update(self.delta_time)

        reason = self.resources.failure_reason()
        if reason:
            self.end_mission(False, reason)
            return

        self.time_left -= self.delta_time / 1000
        if self.time_left <= 0:
            self.time_left = 0
            food_problem = self.greenhouse_mission.failure_reason()
            if food_problem:
                self.end_mission(False, food_problem)
            else:
                self.end_mission(True, self.victory_summary())
            return

        if self.storm_mission.pending_report:
            self.storm_mission.pending_report = False
            self.open_terminal(self.storm_mission.report)

    def update_projectiles(self):
        """ Mecánica heredada: darle a un NPC resta puntos """
        for projectile in self.projectiles[:]:
            projectile.move()
            for group, entity_class in ((self.npcs, NPC), (self.special_npcs, SpecialNPC), (self.extra_npcs, ExtraNPC)):
                hit = next((entity for entity in group if projectile.check_collision(entity)), None)
                if hit:
                    self.score -= 50
                    if projectile in self.projectiles:
                        self.projectiles.remove(projectile)
                    group.remove(hit)
                    group.append(self.spawn(entity_class))
                    self.hit_sound.play()
                    break

    def victory_summary(self):
        r = self.resources
        return (f"¡La tripulación sobrevivió al sol! Tanques rellenados: {self.energy_mission.completed}. "
                f"Tormentas superadas: {self.storm_mission.storms_survived}. "
                f"Comida cosechada: {self.greenhouse_mission.food} raciones. "
                f"Radiación recibida: {int(r.radiation)} de {r.radiation_limit}. Puntos: {self.score}.")

    # ------------------------------------------------------------------ dibujo
    def draw(self):
        self.renderer.draw()  # Primera persona con ray casting (render3d.py)
        self.storm_mission.draw_effects(self.screen)
        self.draw_minimap()
        self.hud.draw()  # Sol, estado de la base, alertas y nombre del sector (ver hud.py)
        pg.display.flip()

    def build_minimap(self):
        """ Dibuja una sola vez el fondo del minimapa: muros en gris y el piso con el color de su sector """
        cell = MINIMAP_CELL
        surface = pg.Surface((self.map.width * cell, self.map.height * cell))
        for j, row in enumerate(self.map.mini_map):
            for i, value in enumerate(row):
                color = MINIMAP_WALL if value else SECTORS[self.map.sector_grid[j][i]]["color"]
                pg.draw.rect(surface, color, (i * cell, j * cell, cell, cell))
        return surface

    def draw_minimap(self):
        cell = MINIMAP_CELL
        x0 = self.screen.get_width() - self.minimap_base.get_width() - 20
        y0 = 20
        w, h = self.minimap_base.get_size()
        frame = pg.Surface((w + 16, h + 16), pg.SRCALPHA)
        frame.fill((0, 0, 0, 180))
        self.screen.blit(frame, (x0 - 8, y0 - 8))
        pg.draw.line(self.screen, (200, 30, 30), (x0 - 8, y0 + h + 8), (x0 + w + 7, y0 + h + 8), 2)
        self.screen.blit(self.minimap_base, (x0, y0))
        for mission in self.missions:
            mission.draw_minimap_marker(x0, y0, cell)
        # Jugador con un cono que muestra hacia dónde mira (útil en la vista 3D)
        px, py = x0 + self.player.x * cell, y0 + self.player.y * cell
        for offset in (-0.5, 0.5):
            a = self.player.angle + offset
            pg.draw.line(self.screen, (255, 120, 120), (px, py), (px + math.cos(a) * 14, py + math.sin(a) * 14), 1)
        pg.draw.circle(self.screen, (255, 0, 0), (px, py), 3)

    def run_overlay_frame(self, screen):
        """ Un frame de la pausa o del fin de misión: el juego queda detenido y solo responde el menú """
        for event in CONTROLS.events("pause" if self.state == "paused" else "menu"):
            if event.type == pg.QUIT:
                self.quit_game()
            screen.handle_event(event)
            if self.state not in ("paused", "game_over"):
                return
        self.screen.blit(self.frozen_frame, (0, 0))
        screen.draw(self.screen)
        pg.display.flip()

    def run(self):
        while True:
            if self.state == "menu":
                self.menu.run_frame()
            elif self.state == "paused":
                self.run_overlay_frame(self.pause_screen)
            elif self.state == "game_over":
                self.run_overlay_frame(self.end_screen)
            elif self.state == "terminal":
                self.run_terminal_frame()
            else:
                self.check_events()
                # Si al procesar eventos se pausó o se abrió una ventana, el juego ya no avanza en este frame
                if self.state == "playing":
                    self.update()
                if self.state == "playing":
                    self.draw()
            self.delta_time = self.clock.tick(FPS)


if __name__ == "__main__":
    game = Game()
    game.run()
