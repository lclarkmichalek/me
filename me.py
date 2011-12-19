#!/usr/bin/python2
RELEASE = True

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

POINTS = 0

running = True

color_schemes = ["blue", "red", "green", "yellow"]
current_color = "blue"
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

n_paths = {'easy': 25,
           'medium': 50,
           'hard': 100}
path_colors = {
    'easy': ['blue', 'red'],
    'medium': ['blue', 'red', 'green'],
    'hard': ['blue', 'red', 'green', 'yellow']
}

class GameEnded(RuntimeError):
    pass

def gc(color, cc=None):
    current = cc or current_color
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

    def __init__(self, avatar, particles):
        self.last_updated = datetime.utcnow()
        self.avatar = avatar
        self.particles = particles

    def update(self, bonus_path=False):
        now = datetime.utcnow()
        t_delta = (now - self.last_updated).total_seconds()
        if not bonus_path:
            self.bonus -= self.bonus_decay * self.bonus / t_delta
            if self.bonus < 1:
                self.bonus = 0
        else:
            self.bonus += self.bonus_increase / t_delta
        self.last_updated = now

        self.avatar.update(t_delta)
        self.particles.update(t_delta)

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

class Spiral(list):
    def __init__(self, width, height, colors,
                 sample_interval=10, const=5,
                 init=1.0, max=2*pi*5):
        self.width, self.height = width, height
        self.center = (width/2, height/2)
        self.interval = sample_interval
        self.const = const
        self.init = init
        self.max = max
        self.colors = colors

    def pre_draw(self):
        self.spirals = {}
        for color in self.colors:
            surf = pygame.Surface((self.width, self.height), pygame.HWSURFACE)
            deviations = [pi/4 * x for x in range(-2, 3)]
            deviationlines = [[] for x in range(-2, 3)]
            t = self.spiral_init
            while t < self.spiral_max:
                t += self.sample_interval/self.radius(t)
                for i, dev in enumerate(deviations):
                    deviationlines[i].append(
                        to_cartesian(t, self.radius(t + dev),
                                     o=self.spiral_center))

            surf.fill(gc('background', color))
            for dev, dpoints in zip(deviations, deviationlines):
                if android:
                    func = draw.lines
                else:
                    func = draw.aalines
                func(surf, gc("border_color"), False, dpoints)
            self.spirals[color]  = surf

    def radius(self, t):
        return t * self.const

    def blit(self, surf, pos=(0, 0), color=None):
        cc = color or current_color
        surf.blit(self.spirals[cc], pos)

class Avatar():
    def __init__(self, screen, speed, size=15):
        self.screen = screen
        self.spiral = screen.spiral
        self.t = screen.spiral.init
        self.speed = speed
        self.size = size

    def draw(self, surface):
        abs_pos = self.screen.to_cartesian(self.t)
        s_pos = self.screen.screen_position
        pos = (abs_pos[0] - s_pos[0], abs_pos[1] - s_pos[1])
        draw.circle(surface, self.screen.gc("avatar"), pos, self.size)

    def update(self, t_delta):
        d_delta = self.speed * t_delta
        self.t += d_delta / self.spiral.radius(self.t)
        if self.t > self.spiral.max:
            raise GameEnded()



class Screen():
    ranges = []
    avatar_rebound = False
    avatar_just_hit = False
    hots = []
    paths = {}
    assets = {}
    points = 0
    bonus = 0
    font_size = 50
    difficulty = "easy"
    dimmer = None
    dim = 0
    menu_state = "ok"
    current_color = "blue"

    def __init__(self, clock, difficulty, spiral):
        self.clock = clock
        self.difficulty = difficulty
        self.zoom_size = [VWIDTH, VHEIGHT]
        self.disp = pygame.Surface((VWIDTH, VHEIGHT), pygame.HWSURFACE)
        self.logic = Logic()

    def flip(self):
        disp = display.get_surface()
        disp.blit(self.disp, (0, 0))
        display.flip()

    def to_cart(self, t, r=None, force_int=False):
        r = r or self.radius(t)
        return to_cartesian(t, r, self.screen_center, force_int)

    def gc(self, color_name, current=None):
        return gc(color_name, current or self.current_color)

    def change_color(self, color):
        assert color in color_schemes, "Invalid color"
        self.current_color = color

    def configure_avatar(self, avatar_init=pi * 1.5, avatar_speed=5,
                         avatar_size=5):
        self.avatar_init = avatar_init
        self.avatar_speed = avatar_speed
        self.avatar_size = avatar_size

        self.avatar_dev = 0

        self.avatar_t = avatar_init
        self.avatar_last = datetime.utcnow()
        self.setup_particle_systems()

    def setup_particle_systems(self):
        self.avatar_path_ps = {}
        for color in color_schemes:
            names = ("p1", "p2", "p3", "p4")
            particle_colors = []
            for name in names:
                particle_colors.append(from_hex(colors[color][name]))
            self.avatar_path_ps[color] = padlib.particle_system(
                (0, 0), particle_colors, [20, 30], 360, 0, 0,
                20 if android else 30)
            self.hot_ps = padlib.particle_system(
                (0, 0), particle_colors, [20, 30], 360, 0, 0,
                5 if android else 10)

    def update_particle_systems(self):
        for ps in self.avatar_path_ps.values():
            x, y = list(self.avatar_cart())
            x -= self.screen_pos[0]
            y -= self.screen_pos[1]
            ps.change_position((x, y))
            ps.update()

            if ps.density <= 5:
                ps.density = 0
            else:
                ps.density = int(ps.density * (0.5 if android else 0.9))
            if ps.speedrange[1] < 30:
                ps.speedrange[1] = 30
            else:
                ps.speedrange[1] = int(ps.speedrange[1] * 0.8)
        if all(map((lambda ps: ps.density < 5), self.avatar_path_ps.values())):
            self.avatar_just_hit = False

        self.hot_ps.change_position((x, y))
        self.hot_ps.update()

    def draw_particle_systems(self):
        self.avatar_path_ps[current_color].draw(self.disp)
        self.hot_ps.draw(self.disp)

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

    def blit_viewport(self, x, y):
        assert 0 < x < self.width, "X out of bounds"
        assert 0 < y < self.height, "Y out of bounds"

        self.disp.blit(self.screen,
                       (0, 0), area=(x, y, x + VWIDTH, y + VHEIGHT))

    def draw_spiral(self):
        self.update_screen_pos()
        self.blit_viewport(*self.screen_pos)

    def update_screen_pos(self):
        self.screen_pos = list(to_cartesian(self.avatar_t,
                                            self.radius(self.avatar_t),
                                            self.spiral_center))
        self.screen_pos[0] -= VWIDTH/2
        self.screen_pos[1] -= VHEIGHT/2

    def update(self):
        self.draw_spiral()

        time_delta = (datetime.utcnow() - self.avatar_last).total_seconds()
        self.avatar.update(time_delta)


        for path in self.paths.values():
            for p in path:
                if p.passed(oldt, self.avatar_t,
                            self.radius(oldt + self.avatar_dev * pi/4)) and \
                            not self.avatar_rebound:
                    p.hit = True

                    if p.color == current_color:
                        sound = random.choice(
                            ("exp1", "exp2", "exp3", "exp4"))
                        self.play_sound(sound)
                        self.avatar_speed += 3
                        self.avatar_just_hit = True
                        if android:
                            newd = 50
                        else:
                            newd = 100
                        self.avatar_path_ps[current_color].density = newd
                        self.avatar_path_ps[current_color].speedrange[1] = 100

                        self.logic.correct_point_hit()
                        self.bonus += 5
                    else:
                        sound = random.choice(("bad1", "bad2"))
                        self.play_sound(sound)
                        for ps in self.avatar_path_ps.values():
                            ps.density = 0
                        self.hot_ps.density = 0

                        self.avatar_rebound = self.avatar_speed
                        self.avatar_speed *= -1
                        self.logic.incorrect_point_hit()
        if self.avatar_rebound:
            if self.avatar_speed > self.avatar_rebound:
                self.avatar_rebound = False
            else:
                self.avatar_speed += 10

        for h in self.hots:
            if h.inside(self.avatar_t, self.avatar_dev) and \
                    h.color == current_color and not self.avatar_rebound:
                if self.hot_ps.density < 5:
                    self.hot_ps.density += 1
                self.bonus = self.bonus + 10/(self.clock.get_fps() or 1)
                break
        else:
            self.hot_ps.density = 0
            if self.bonus < 1:
                self.bonus = 0
            else:
                self.bonus = self.bonus - \
                    self.bonus * (0.3/(self.clock.get_fps() or 1))
        self.update_particle_systems()

    def screen_adjust(self, (x, y)):
        return (x - self.screen_pos[0], y - self.screen_pos[1])

    def draw_avatar(self):
        x, y = self.screen_adjust(self.avatar_cart())

        draw.circle(self.disp, gc("pale"), (int(x), int(y)),
                    self.avatar_size)

    def avatar_cart(self):
        return to_cartesian(self.avatar_t,
                            self.radius(self.avatar_t + self.avatar_dev*pi/4),
                            o=self.spiral_center)

    def change_avatar_dev(self, d):
        if -3 < self.avatar_dev + d < 3:
            self.avatar_dev += d

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
            if current_color == color:
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
        s = Menu(4000, 4000, clock, "hard")
        s.configure_spiral(spiral_center=(2000, 2000), spiral_const=30,
                           spiral_init=20, sample_interval=20,
                           spiral_max=50)
        s.configure_avatar(avatar_speed=200, avatar_init=20,
                           avatar_size=10)
        s.load_assets()
        while 1:
            if android:
                if android.check_pause():
                    android.wait_for_resume()

            s.avatar_speed = 500
            s.update()
            s.draw_spiral()
            s.draw_hud()
            s.flip()
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

class Hot():
    def __init__(self, start, end, color, dev):
        self.start = start
        self.end = end
        self.color = color
        self.covered = 0
        self.dev = dev

    def intersect(self, hot):
        if self.dev != hot.dev:
            return False

        if hot.start < self.start < hot.end:
            return True
        if hot.start < self.end < hot.end:
            return True
        if self.start < hot.start < self.end:
            return True
        if self.start < hot.end < self.end:
            return True
        return False
    def points(self, spiral):
        points = []
        t = self.start
        while t < self.end:
            t += spiral.sample_interval/spiral.radius(t)
            points.append(to_cartesian(t, spiral.radius(t + self.dev * pi/4),
                                       o=spiral.spiral_center))
        return points

    points_cache = None

    def get_points(self, spiral):
        if not self.points_cache:
            self.points_cache = self.points(spiral)
        return self.points_cache

    def inside(self, t, dev):
        if dev != self.dev:
            return False
        return self.start < t < self.end

class Point():
    def __init__(self, t, r, color):
        self.t = t
        self.r = r
        self.hit = False
        self.color = color

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
    def cart(self, spiral):
        if not self.y:
            x, y = to_cartesian(self.t, self.r, spiral.spiral_center)
            self.x = x
            self.y = y
        return self.x, self.y

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
    if android:
        s = Screen(4000, 4000, clock, difficulty)
        center = (2000, 2000)
        a_speed = 200
        a_size = 15
        sample_interval = 20
        s_const = 40
        s_max = 30
        s_init = 10
    else:
        s = Screen(5000, 5000, clock, difficulty)
        center = (2500, 2500)
        a_speed = 200
        a_size = 15
        sample_interval = 20
        s_const = 30
        s_init = 20
        s_max = 30
    s.configure_spiral(spiral_center=center, spiral_const=s_const,
                       spiral_init=s_init, sample_interval=sample_interval,
                       spiral_max=s_max)
    s.configure_avatar(avatar_speed=a_speed, avatar_init=s_init,
                       avatar_size=a_size)
    s.load_assets()

    s.generate_paths()
    s.generate_hot_paths()
    s.draw_hot_paths()
    s.start_music()
    s.change_color("blue")

    global running
    while running:
#        if (datetime.utcnow() - last_speedup).total_seconds() > 3:
#            if abs(s.avatar_speed) < 50:
#                s.avatar_speed *= 1.1
#            else:
#                s.avatar_speed = ((s.avatar_speed + 20) ** 2 /
#                                  float(s.avatar_speed))
#            last_speedup = datetime.utcnow()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_RIGHT):
                    s.change_avatar_dev(+1)
                elif event.key in (pygame.K_DOWN, pygame.K_LEFT):
                    s.change_avatar_dev(-1)
                elif event.key in color_keymap and \
                        color_keymap[event.key] in path_colors[s.difficulty]:
                    s.change_color(color_keymap[event.key])
                elif event.key == pygame.K_ESCAPE:
                    return
            if android:
                if event.type == pygame.MOUSEBUTTONDOWN and\
                        event.button == 1:
                    s.screen_pressed(event.pos)
        s.update()
        s.draw_spiral()
        s.draw_particle_systems()
        s.draw_avatar()
        s.draw_paths()
        s.draw_hud()
        s.flip()
        clock.tick(60)

        if android:
            if android.check_pause():
                android.wait_for_resume()

    running = True
    while running:
        s.draw_spiral()
        s.draw_score()
        s.flip()
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN,
                                 pygame.K_ESCAPE):
                    s.stop()
                    return
            if event.type == pygame.MOUSEBUTTON_DOWN and android:
                s.stop()
                return
        if android:
            if android.check_pause():
                android.wait_for_resume()

if __name__ == "__main__":
    main()
