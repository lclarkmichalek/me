#!/usr/bin/python2
RELEASE = False

from math import pi, cos, sin, hypot
from datetime import datetime
import random, os, sys

import pygame
from pygame import draw, display, image, key, font, transform, mouse

pygame.init()
mouse.set_visible(False)
key.set_repeat(10, 75)

try:
    import android
except ImportError:
    android = None

import padlib

if RELEASE:
    modes = display.list_modes()
    VWIDTH, VHEIGHT = modes[0]
else:
    VWIDTH, VHEIGHT = 640, 480

color_schemes = ["blue", "red", "green", "yellow"]
color_keymap = {
    pygame.K_a: "blue",
    pygame.K_s: "red",
    pygame.K_d: "green",
    pygame.K_f: "yellow"
    }
colors = {
    'blue': {
        'background': '#545B74',
        'spiral_color': '#FFBB00',
        'border_color': '#616F9B',
        'pale': '#203065',
        'avatar': '#203065',
        'p1': '#009999',
        'p2': '#2419B2',
        'p3': '#FFC500',
        'p4': '#FF7400'
        },
    'red': {
        'background': '#AC7B75',
        'spiral_color': '#00B74A',
        'border_color': '#E58E84',
        'pale': '#8D1520',
        'avatar': '#8D1520',
        'p1': '#E40045',
        'p2': '#FF7C00',
        'p3': '#04859D',
        'p4': '#67E300'
        },
    'green': {
        'background': '#3E621F',
        'spiral_color': '#F5001D',
        'border_color': '#75AB48',
        'pale': '#70E500',
        'avatar': '#85EB6A',
        'p1': '#B72F00',
        'p2': '#00B454',
        'p3': '#FF3900',
        'p4': '#BC008D',
        },
    'yellow': {
        'background': '#A69600',
        'spiral_color': '#510FAD',
        'border_color': '#FFF173',
        'pale': '#FFDA00',
        'avatar': '#FFED40',
        'p1': '#FFD700',
        'p2': '#DFFA00',
        'p3': '#8C04A8',
        'p4': '#3E13AF',
        }
}

class GameEnded(RuntimeError):
    pass

def randrange(start, end):
    """
Return a random variable between start and end. May be a float

    Arguments:
    - `start`:
    - `end`:
    """
    return random.randrange(int(start*10000), int(end*10000))/10000.

def gc(color, cc=None):
    current = cc
    return from_hex(colors[current][color])

def from_hex(value):
    if isinstance(value, str):
        value = value.lstrip('#')
        lv = len(value)
        return tuple(int(value[i:i+lv/3], 16) for i in range(0, lv, lv/3))
    return value

def to_cartesian(t, r, o=(0, 0), force_int=False):
    if force_int:
        return int(r * cos(t) + o[0]), int(r * sin(t) + o[1])
    return r * cos(t) + o[0], r * sin(t) + o[1]

class Logic():
    score = 0
    bonus = 0
    bonus_decay = 0.3
    bonus_increase = 30
    colors = {
        'easy': ['blue', 'red'],
        'medium': ['blue', 'red', 'green'],
        'hard': ['blue', 'red', 'green', 'yellow']
        }
    running = True

    def __init__(self, screen, difficulty):
        self.last_updated = 0
        self.difficulty = difficulty
        self.current_color = "blue"
        self.screen = screen

    def create_spiral_dependants(self):
        self.avatar = Avatar(self, self.screen)
        self.particles = ParticleManager(self, self.screen)

    def update(self, bonus_path=False):
        now = datetime.utcnow()
        if not self.last_updated:
            self.last_updated = now
        t_delta = (now - self.last_updated).total_seconds() or 0.000001
        if not bonus_path:
            self.bonus -= self.bonus_decay * self.bonus * t_delta
            if self.bonus < 1:
                self.bonus = 0
        else:
            self.bonus += self.bonus_increase * t_delta
        self.last_updated = now

        self.avatar.update(t_delta)
        self.particles.update(t_delta)

    def change_color(self, index):
        self.current_color = self.colors[self.difficulty][index]

    def correct_point_hit(self):
        self.score += self.bonus * 1000
        self.bonus += 5

        self.particles.correct_point_hit()
        self.avatar.correct_point_hit()

    def incorrect_point_hit(self):
        self.score -= self.bonus/2 * 1000
        self.bonus = 0

        self.particles.incorrect_point_hit()
        self.avatar.incorrect_point_hit()

    def game_ended(self):
        return

class Spiral():
    def __init__(self, width, height, colors,
                 screen, logic,
                 sample_interval=10, const=30,
                 init=1.0, max=2*pi*5):
        self.screen = screen
        self.logic = logic

        self.width, self.height = width, height
        self.center = (width/2, height/2)
        self.interval = sample_interval
        self.const = const
        self.init = init
        self.max = max
        self.colors = colors
        self.paths_by_color = {}
        for color in self.logic.colors[self.logic.difficulty]:
            self.paths_by_color[color] = []
        self.paths_by_dev = {-3: [], -2: [], -1: [], 0: [], 1: [], 2: []}

        self.spirals = {}

    def prepare(self):
        self.pre_draw()
        self.generate_paths()
        self.pre_draw_paths()

    def pre_draw(self):
        self.spirals = {}
        for color in self.colors:
            surf = pygame.Surface((self.width, self.height), pygame.HWSURFACE)
            deviations = [pi/4 * x for x in range(-2, 3)]
            deviationlines = [[] for x in range(-2, 3)]
            t = self.init
            while t < self.max:
                t += self.interval/self.radius(t)
                for i, dev in enumerate(deviations):
                    deviationlines[i].append(
                        to_cartesian(t, self.radius(t + dev),
                                     o=self.center))

            surf.fill(gc('background', color))
            for dev, dpoints in zip(deviations, deviationlines):
                if android:
                    func = draw.lines
                else:
                    func = draw.aalines
                func(surf, self.screen.gc("border_color"), False, dpoints)
            self.spirals[color]  = surf

    def generate_paths(self):
        count = 100
        for _ in range(count):
            color = random.choice(self.logic.colors[self.logic.difficulty])
            dev = random.randrange(-3, 3)
            s = randrange(self.init + pi, self.max - 2 * pi)
            l = randrange(pi/8, pi/2)
            e = s + l
            path = Path(self, s, e, color, dev)
            path.generate_points(random.random() * 10)
            self.paths_by_color[color].append(path)
            self.paths_by_dev[dev].append(path)

    def pre_draw_paths(self):
        for paths in self.paths_by_color.values():
            for path in paths:
                for bg in self.spirals.values():
                    path.draw(bg)

    def radius(self, t, dev=0):
        return t * self.const + dev * pi/4.

    def get_background(self, surf):
        pos = self.screen.screen_pos
        color = self.logic.current_color
        surf.blit(self.spirals[color], (0, 0),
                  (pos, (pos[0] + VWIDTH, pos[1] + VHEIGHT)))
        self.draw_points(surf)

    def draw_points(self, surface):
        for paths in self.paths_by_color.values():
            for path in paths:
                for point in path.points:
                    point.draw(surface)

class Avatar():
    def __init__(self, logic, screen, speed=100, size=15):
        self.logic = logic
        self.screen = screen
        self.spiral = screen.spiral
        self.t = screen.spiral.init
        self.speed = speed
        self.size = size
        self.dev = 0
        self.bouncing = False

    def change_dev(self, change):
        if -3 < self.dev + change < 3:
            self.dev += change

    def draw(self, surface):
        r = self.screen.spiral.radius(self.t, self.dev)
        abs_pos = self.screen.to_cart(self.t, r)
        s_pos = self.screen.screen_position
        pos = (abs_pos[0] - s_pos[0], abs_pos[1] - s_pos[1])
        draw.circle(surface, self.screen.gc("avatar"), pos, self.size)

    def update(self, t_delta):
        d_delta = self.speed * t_delta
        self.t += d_delta / self.spiral.radius(self.t)
        if self.t > self.spiral.max:
            self.logic.running = False

        if self.bouncing:
            if self.speed < self.pre_speed:
                self.speed += 10
            else:
                self.bouncing = False

    def correct_point_hit(self):
        self.speed += 3

    def incorrect_point_hit(self):
        self.bouncing = True
        self.pre_speed = self.speed
        self.speed *= -1
        self.speed += 5

    def cart_screen(self, dev=True):
        r = self.screen.spiral.radius(self.t, self.dev)
        return self.screen.to_cart(self.t, r)

    def cart_viewport(self, dev=True):
        return self.screen.adjust_to_viewport(self.cart_screen(dev))

    def on_path(self):
        for path in self.spiral.paths_by_color[self.logic.current_color]:
            if path.inside(self.t, self.dev):
                return True
        return False

class ParticleManager():
    def __init__(self, logic, screen):
        self.screen = screen
        self.logic = logic

        self.point_ps = {}
        for color in logic.colors[logic.difficulty]:
            names = ("p1", "p2", "p3", "p4")
            particle_colors = []
            for name in names:
                particle_colors.append(self.screen.gc(name, color))
            self.point_ps[color] = padlib.particle_system(
                (0, 0), particle_colors, [20, 30], 360, 0, 0,
                20 if android else 30)
            self.path_ps = padlib.particle_system(
                (0, 0), particle_colors, [20, 30], 360, 0, 0,
                5 if android else 10)

    def update(self, t_delta):
        pos = self.logic.avatar.cart_viewport(True)
        for ps in self.point_ps.values():
            ps.change_position(pos)
            ps.update()

            if ps.density <= 5:
                ps.density = 0
            else:
                ps.density = int(ps.density * (0.5 if android else 0.9))
            if ps.speedrange[1] < 30:
                ps.speedrange[1] = 30
            else:
                ps.speedrange[1] = int(ps.speedrange[1] * 0.8)

        self.path_ps.change_position(pos)
        self.path_ps.update()
        if self.logic.avatar.on_path():
            self.path_ps.density = 20
        else:
            if self.path_ps.density < 2:
                self.path_ps.density = 0
            else:
                self.path_ps.density = int(self.path_ps.density * 0.9)

    def correct_point_hit(self):
        ps = self.point_ps[self.logic.color]
        ps.density = 100
        ps.speedrange[1] = 100

    def incorrect_point_hit(self):
        for ps in self.point_ps.values():
            ps.density = 0
        self.path_ps.density = 0

    def draw(self, surface):
        point_ps = self.point_ps[self.logic.color]
        point_ps.draw(surface)
        self.path_ps.draw(surface)

class AssetManager():
    def __init__(self):
        names = {'blue': 'a',
                 'red': 's',
                 'green': 'd',
                 'yellow': 'f'}
        self.assets = {}
        for color, key in names.items():
            surf = image.load(os.path.join("data", key + ".png")).convert()
            surf.set_colorkey((0, 0, 0))
            self.assets[color] = surf

        self.font = font.Font(os.path.join("data", "DIMIS___.TTF"),
                              self.font_size)

    def render_text(self, text, color):
        return self.font.render(text, True, color)

    def get(self, name):
        return self.assets[name]

class HUD():
    def __init__(self, screen, logic):
        self.screen = screen
        self.logic = logic
        self.bounds = []

    def draw(self, surface):
        assets = self.screen.assets
        items = self.logic.colors[self.logic.difficulty]
        width_needed = 124 * len(items) + 12 * (len(items)-1)
        x = (VWIDTH - width_needed)/2
        y = 12
        self.bounds = []
        for i, l in enumerate(items):
            surface.blit(assets.get(l),
                         (x + i * (124 + 12), y))
            self.bounds.append(pygame.Rect(
                    (x + i * (124 + 12), y),
                    (assets.get(l).get_width(), assets.get(l)
                     .get_height())
                    ))

        score = assets.render_text(
            "Score: " + str(int(self.points)),
            self.screen.gc("avatar"))
        y = VHEIGHT - 20 - score.get_height() * 2
        x = (VWIDTH - score.get_width())/2
        surface.blit(score, (x, y))

        bonus = assets(
            "Bonus: " + str(int(self.bonus)),
            gc("avatar"))
        y = VHEIGHT - 10 - bonus.get_height()
        x = (VWIDTH - bonus.get_width())/2
        surface.blit(bonus, (x, y))

    def screen_pressed(self, pos):
        for i, bound in self.bounds:
            if bound.collidepoint(pos):
                self.logic.change_color(i)

class Screen():
    width, height = 5000, 5000
    dimmer = None
    dim = 0
    menu_state = "ok"
    running = True

    def __init__(self, clock, difficulty):
        self.clock = clock
        self.logic = Logic(self, difficulty)
        self.spiral = Spiral(self.width, self.height,
                             self.logic.colors[self.logic.difficulty],
                             self, self.logic)
        self.logic.create_spiral_dependants()
        self.last = datetime.utcnow()

    def show(self):

        self.start_music()
        self.logic.change_color("blue")

        while self.logic.running:
            for event in pygame.event.get():
                self.logic.handle_event(event)
                if android:
                    if event.type == pygame.MOUSEBUTTONDOWN and\
                            event.button == 1:
                        self.logic.screen_pressed(event.pos)
            self.update()

            self.flip()
            self.clock.tick(60)

            if android:
                if android.check_pause():
                    android.wait_for_resume()

        while self.logic.running:
            self.draw_spiral()
            self.draw_score()
            self.flip()
            self.clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN,
                                     pygame.K_ESCAPE):
                        self.stop()
                        return
                if event.type == pygame.MOUSEBUTTON_DOWN and android:
                    self.stop()
                    return
            if android:
                if android.check_pause():
                    android.wait_for_resume()

    def draw(self, surface):
        """
        Draw the game onto the given surface

        Arguments:
        - `self`:
        - `surface`:
        """
        self.spiral.get_background(surface)

    def flip(self):
        disp = display.get_surface()
        disp.blit(self.disp, (0, 0))
        display.flip()

    def to_cart(self, t, r=None, force_int=False):
        r = r or self.spiral.radius(t)
        return to_cartesian(t, r, self.spiral.center, force_int)

    def gc(self, color_name, current=None):
        return gc(color_name, current or self.logic.current_color)

    def adjust_to_viewport(self, (x, y)):
        return (x - self.screen_pos[0], y - self.screen_pos[1])

    def load_assets(self):
        names = {'blue': 'a',
                 'red': 's',
                 'green': 'd',
                 'yellow': 'f'}
        self.assets = {}
        for color, key in names.items():
            surf = image.load(os.path.join("data", key + ".png")).convert()
            surf.set_colorkey((0, 0, 0))
            self.assets[color] = surf

        self.font = font.Font(os.path.join("data", "DIMIS___.TTF"),
                              self.font_size)

    def play_sound(self, name):
        if android:
            import android_mixer as mixer
        else:
            from pygame import mixer
            mixer.init()
        sound = mixer.Sound(os.path.join("data", "{0}.ogg".format(name)))
        sound.play()

    def screen_pressed(self, position):
        for i, bound in enumerate(self.button_bounds):
            if bound.collidepoint(position):
                color = path_colors[self.difficulty][i]
                self.change_color(color)
                return

        s_pos = (position[0] + self.screen_pos[0] - self.spiral_center[0],
                 position[1] + self.screen_pos[1] - self.spiral_center[1])
        print s_pos
        mag = hypot(*s_pos)
        print mag
        print self.radius(self.avatar_t)
        if abs(mag) > abs(self.radius(self.avatar_t)):
            self.change_avatar_dev(1)
        else:
            self.change_avatar_dev(-1)

    def draw_hud(self):
        items = path_colors[self.difficulty]
        viewport = self.disp
        width_needed = 124 * len(items) + 12 * (len(items)-1)
        assert width_needed < VWIDTH, "Not enough room to draw hud"
        x = (VWIDTH - width_needed)/2
        y = 12
        self.button_bounds = []
        for i, l in enumerate(items):
            viewport.blit(self.assets[l], (x + i * (124 + 12), y))
            self.button_bounds.append(pygame.Rect(
                    (x + i * (124 + 12), y),
                    (self.assets[l].get_width(), self.assets[l].get_height())
                    ))

        score = self.font.render("Score: " + str(int(self.points)),
                                 True, gc("avatar"))
        y = VHEIGHT - 20 - score.get_height() * 2
        x = (VWIDTH - score.get_width())/2
        viewport.blit(score, (x, y))

        bonus = self.font.render("Bonus: " + str(int(self.bonus)),
                                 True, gc("avatar"))
        y = VHEIGHT - 10 - bonus.get_height()
        x = (VWIDTH - bonus.get_width())/2
        viewport.blit(bonus, (x, y))

    def draw_score(self):
        viewport = self.disp
        if self.menu_state == "ok":
            self.menu_state = "dim_out_1"
        if self.menu_state == "dim_out_1":
            if not self.dimmer:
                self.dimmer = pygame.Surface(display.get_surface().get_size())
                self.dimmer.fill((0, 0, 0))
            self.dimmer.set_alpha(self.dim)
            self.dim += 1
            viewport.blit(self.dimmer, (0, 0))
            if self.dim == 200:
                self.menu_state = "dim_in_zoom"
                self.dimmer = None
        if self.menu_state == "dim_in_zoom":
            self.zoom_size[0] += 20
            self.zoom_size[1] += 20
            self.draw_paths()
            self.draw_hot_paths()
            try:
                scaled = transform.scale(self.screen, self.zoom_size)
            except ValueError:
                self.menu_state = "wait"
            viewport.blit(scaled,
                          ((-scaled.get_width() + VWIDTH)/2,
                           (-scaled.get_height() + VHEIGHT)/2))
            raw = "Score: {0}".format(int(self.points))
            surf = self.font.render(raw, True, gc("avatar"))
            y = (VHEIGHT - surf.get_height())/2
            x = (VWIDTH - surf.get_width())/2
            viewport.blit(surf, (x, y))

            if not self.dimmer:
                self.dimmer = pygame.Surface(display.get_surface().get_size())
                self.dimmer.fill((0, 0, 0))
            self.dimmer.set_alpha(self.dim)
            self.dim -= 4
            viewport.blit(self.dimmer, (0, 0))
            if self.dim == 0:
                self.menu_state = "wait"
        if self.menu_state == "wait":
            return

    @property
    def screen_pos(self):
        screen_pos = list(self.to_cart(self.logic.avatar.t))
        screen_pos[0] -= VWIDTH/2
        screen_pos[1] -= VHEIGHT/2
        return tuple(screen_pos)

    def update(self):
        time_delta = (datetime.utcnow() - self.last).total_seconds()
        self.logic.update(time_delta)
        self.last = datetime.utcnow()

    def generate_paths(self):
        self.paths = {}
        for color in path_colors[self.difficulty]:
            self.paths[color] = self.generate_path(color)

    def draw_paths(self):
        for color, path in self.paths.iteritems():
            self.draw_path(color, path)

    def generate_path(self, color):
        rpoints = []
        for _ in range(n_paths[self.difficulty]):
            start = random.randrange((self.avatar_init + 2) * 1000,
                                 (self.spiral_max - 1) * 1000) / 1000.
            end = start + random.random()
            level = random.randrange(-2, 3)
            for s, e, l in self.ranges:
                if level == l and (s < start < e or s < end < e):
                    break
            else:
                self.ranges.append((start, end, level))
                distance = (end - start) / random.randrange(1, 5)
                i = 0
                while start + i * distance < end:
                    rpoints.append((level, start + i * distance))
                    i += 1

        polar_points = []
        for d, t in rpoints:
            polar_points.append(Point(t, self.radius(t + d * pi/4), color))
        return polar_points

    def draw_path(self, color, path):
        disp = self.disp
        for p in path:
            if self.logic.current_color == color:
                draw_color = gc("avatar")
            else:
                draw_color = from_hex(colors[color]["pale"])
            x, y = p.cart(self)
            x -= self.screen_pos[0]
            y -= self.screen_pos[1]
            if 0 < x < VWIDTH and 0 < y < VHEIGHT:
                draw.circle(disp, draw_color, (int(x), int(y)),
                            self.avatar_size - 2,
                            0 if not p.hit else 1)

    def generate_hot_paths(self):
        for _ in range(100):
            start = random.randrange((self.avatar_init + 2) * 1000,
                                     (self.spiral_max - 2) * 1000) / 1000.
            size =  1 + random.random()
            end = start + size
            color = random.choice(path_colors[self.difficulty])
            dev = random.randrange(-2, 3)
            hot = Hot(start, end, color, dev)
            for h in self.hots:
                if h.intersect(hot):
                    break
            else:
                self.hots.append(hot)

    def draw_hot_paths(self):
        for hot in self.hots:
            for bg in self.backgrounds:
                draw.lines(bg,
                           from_hex(colors[hot.color]["pale"]),
                           False, hot.get_points(self), 3)

    def start_music(self):
        self.play_sound("Intermission")

    def stop(self):
        try:
            import pygame.mixer as mixer
        except ImportError, NotImplementedError:
            import android_mixer as mixer
        mixer.fadeout(1000)

class Menu(Screen):
    selected = 0
    entries = ("Easy", "Medium", "Hard", "Exit")

    @staticmethod
    def show(clock):
        s = Menu(clock, "hard")
        disp = display.get_surface()
        s.spiral.prepare()
        while 1:
            if android:
                if android.check_pause():
                    android.wait_for_resume()

            s.logic.avatar.speed = 500
            s.update()
            s.draw(disp)
            display.flip()

            clock.tick(60)
            print clock.get_fps()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        s.selected += 1
                    elif event.key == pygame.K_UP:
                        s.selected -= 1
                    elif event.key == pygame.K_RETURN:
                        return s.entries[s.selected].lower()
                    elif event.key == pygame.K_ESCAPE:
                        return "Exit"
                    else:
                        global current_color
                        current_color = random.choice(color_schemes)
                        s.change_color(current_color)
                if android or not RELEASE:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            out = s.button_pressed(event.pos)
                            if out != -1:
                                return s.entries[out]
                            else:
                                global current_color
                                current_color = random.choice(color_schemes)
                                s.change_color(current_color)

        s.stop()

    def button_pressed(self, position):
        for i, bound in enumerate(self.bounds):
            if bound.collidepoint(position):
                return i
        else:
            return -1

    def draw_hud(self):
        viewport = self.disp

        self.bounds = []
        for i, entry in enumerate(self.entries):
            if i == self.selected % len(self.entries) and not android:
                color = "spiral_color"
            else:
                color = "avatar"
            text = self.font.render(entry, True, gc(color))
            y_offset = (VHEIGHT - text.get_height() * len(self.entries) +\
                            20 * len(self.entries))/2
            x = (VWIDTH - text.get_width())/2
            y = text.get_height() * i + 20 * i + y_offset
            viewport.blit(text, (x, y))
            self.bounds.append(pygame.Rect(
                    (x, y),
                    (text.get_width(), text.get_height())))

class Path():
    def __init__(self, spiral,
                 start, end, color, dev):
        self.start = start
        self.end = end
        self.color = color
        self.points = []
        self.dev = dev
        self.spiral = spiral

    def generate_points(self, count):
        length = self.end - self.start
        s_offset = random.random() * length / 3.
        e_offset = random.random() * length / 3.
        t = s_offset
        d = ((self.end - e_offset) - (self.start - s_offset))/float(count)
        while len(self.points) < count:
            self.points.append(Point(t, self))
            t += d

    def intersect(self, path):
        if self.dev != path.dev:
            return False

        if path.start < self.start < path.end:
            return True
        if path.start < self.end < path.end:
            return True
        if self.start < path.start < self.end:
            return True
        if self.start < path.end < self.end:
            return True
        return False

    def inside(self, t, dev):
        if dev != self.dev:
            return False
        return self.start < t < self.end

    def draw(self, surface):
        points = []
        t = self.start
        si = self.spiral.interval
        while t <= self.end:
            t += si / self.spiral.radius(t)
            r = self.spiral.radius(t + self.dev * pi/4.)
            pos = self.spiral.screen.to_cart(t, r)
            points.append(pos)

        draw.lines(surface, self.spiral.screen.gc("avatar"),
                   False, points, 3)

class Point():
    def __init__(self, t, path):
        self.t = t
        self.path = path
        self.spiral = path.spiral
        self.dev = path.dev
        self.r = self.spiral.radius(self.t, path.dev)

    def passed(self, t1, t2, r):
        if self.hit:
            return False
        if abs(r - self.r) > 1:
            return False
        if t1 < self.t < t2:
            return True
        else:
            return False

    x = None
    y = None
    def cart(self):
        if not self.y:
            x, y = self.spiral.screen.to_cart(self.t, self.r)
            self.x = x
            self.y = y
        return self.x, self.y

    screen = pygame.Rect((0, 0), (VWIDTH, VHEIGHT))
    def draw(self, surface):
        pos = self.spiral.screen.adjust_to_viewport(self.cart())
        if not self.screen.collidepoint(pos):
            return
        pos = map(int, pos)
        color = self.spiral.screen.gc("avatar", self.path.color)
        draw.circle(surface, color, pos, 10)

def main():
    flags = 0
    if RELEASE:
        flags |= pygame.FULLSCREEN
    if not android:
        flags |= pygame.HWSURFACE
    display.set_mode((VWIDTH, VHEIGHT), flags)
    if android:
        android.init()
        android.map_key(android.KEYCODE_BACK, pygame.K_ESCAPE)
    while 1:
        clock = pygame.time.Clock()
        choice = Menu.show(clock).lower()
        if choice == "exit":
            return 0
        else:
            play_game(clock, choice)
    return 0

def play_game(clock, difficulty):
    s = Screen(clock, difficulty)
    s.show()

if __name__ == "__main__":
    main()
