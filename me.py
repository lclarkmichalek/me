#!/usr/bin/python2
RELEASE = False

from math import pi, cos, sin, hypot
from datetime import datetime
import random, os, sys, json

import pygame
from pygame import draw, display, image, key, font, transform, mouse

pygame.init()
#mouse.set_visible(False)
key.set_repeat(10, 75)

try:
    import android
except ImportError:
    android = None

import particles

if RELEASE:
    modes = display.list_modes()
    VWIDTH, VHEIGHT = modes[0]
else:
    VWIDTH, VHEIGHT = 1080, 960

FPS = 60
TURNS = 10

color_schemes = ["blue", "red", "green", "yellow"]
COLOR_SPARKS = map(pygame.Color, ["#E6E6AC", "#777278", "#A9A990"])
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

path_counts = {
    'easy': 100,
    'medium': 500,
    'hard': 1000
}

avatar_speeds = {
    'easy': 150,
    'medium': 200,
    'hard': 300
}

def randrange(start, end):
    """
    Return a random variable between start and end. Will be a float

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

def format_score(score):
    rvst = str(int(score))[::-1]
    return ','.join(rvst[i:i+3] for i in\
                        range(0, len(rvst), 3))[::-1]

def to_cartesian(t, r, o=(0, 0), force_int=False):
    if force_int:
        return int(r * cos(t) + o[0]), int(r * sin(t) + o[1])
    return r * cos(t) + o[0], r * sin(t) + o[1]

class Logic():
    bonus_decay = 0.7
    bonus_increase = 10
    color_difficulties = {
        'easy': ['blue', 'red'],
        'medium': ['blue', 'red', 'green'],
        'hard': ['blue', 'red', 'green', 'yellow']
        }
    exit_keys = (pygame.K_ESCAPE,)
    down_keys = (pygame.K_DOWN,)
    up_keys = (pygame.K_UP,)

    def __init__(self, screen, difficulty):
        self.last_updated = 0
        self.difficulty = difficulty
        self.current_color = "blue"
        self.screen = screen
        self.running = True
        self.bonus = 0
        self.score = 0

    def create_spiral_dependants(self):
        self.avatar = Avatar(self, self.screen)
        self.particles = ParticleManager(self, self.screen)
        self.hud = HUD(self.screen, self)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key in self.exit_keys:
                self.running = False
            elif event.key in self.down_keys:
                self.avatar.change_dev(-1)
            elif event.key in self.up_keys:
                self.avatar.change_dev(1)
            elif event.key in color_keymap:
                color = color_keymap[event.key]
                if color in self.colors:
                    self.change_color(self.colors.index(color))
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.hud.screen_pressed(event.pos):
                return
            self.screen_pressed(event.pos)

    def screen_pressed(self, pos):
        """
        Handles the screen being pressed. If the press is further away from the
        center of the spiral then change_dev(+1) else -1.

        Arguments:
        - `self`:
        - `pos`:
        """
        s_pos = self.screen.screen_pos
        s_center = self.screen.spiral.center
        s_pos = (pos[0] + s_pos[0] - s_center[0],
                 pos[1] + s_pos[1] - s_center[1])
        mag = hypot(*s_pos)
        if abs(mag) > abs(self.screen.spiral.radius(self.avatar.t)):
            self.avatar.change_dev(1)
        else:
            self.avatar.change_dev(-1)

    def update(self):
        """
        Updates the various objects. Namely:
         - Bonus decay

        """
        now = datetime.utcnow()
        if not self.last_updated:
            self.last_updated = now
        t_delta = (now - self.last_updated).total_seconds() or 0.000001
        if not self.avatar.on_path():
            self.bonus -= self.bonus_decay * self.bonus * t_delta
            if self.bonus < 1:
                self.bonus = 0
        else:
            self.bonus += self.bonus_increase * t_delta
        self.last_updated = now

        oldt = self.avatar.t

        self.avatar.update(t_delta)

        if self.avatar.on_any_path():
            path = self.avatar.get_on_path()
            point = path.passed(oldt, self.avatar.t)
            if point:
                if not point.unhittable:
                    point.hit = True
                if self.correct_point(point):
                    self.correct_point_hit()
                elif not self.avatar.bouncing:
                    self.incorrect_point_hit()

        self.particles.update(t_delta)

    def correct_point(self, point):
        return point.color == self.current_color

    @property
    def colors(self):
        return self.color_difficulties[self.difficulty]

    def change_color(self, index):
        self.current_color = self.colors[index]

    def correct_point_hit(self):
        self.score += self.bonus * 1000
        self.bonus += 10

        self.particles.correct_point_hit()
        self.avatar.correct_point_hit()

    def incorrect_point_hit(self):
        self.score /= 5
        self.bonus = 0

        self.particles.incorrect_point_hit()
        self.avatar.incorrect_point_hit()

    def game_ended(self):
        return

class Spiral():
    def __init__(self, width, height, colors,
                 screen, logic,
                 sample_interval=10, const=30,
                 init=1.0, max=2*pi*TURNS):
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
        for color in self.logic.colors:
            self.paths_by_color[color] = []
        self.paths_by_dev = {-2: [], -1: [], 0: [], 1: [], 2: []}

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
        count = path_counts[self.logic.difficulty]
        paths = []
        for _ in range(count):
            color = random.choice(self.logic.colors)
            dev = random.randrange(-2, 3)
            s = randrange(self.init + pi, self.max - pi/8)
            l = randrange(pi/8, pi/4)
            e = s + l
            if e > self.max:
                e = self.max
            path = Path(self, s, e, color, dev)
            if any(o.intersect(path) for o in paths):
                continue

            path.generate_points(1 + random.random() * 5)
            self.paths_by_color[color].append(path)
            self.paths_by_dev[dev].append(path)
            paths.append(path)

    def pre_draw_paths(self):
        for paths in self.paths_by_color.values():
            for path in paths:
                for bg in self.spirals.values():
                    path.draw(bg)

    def radius(self, t, dev=0):
        return self.const * (t + dev * pi/float(4))

    def get_background(self, surf):
        pos = self.screen.screen_pos
        color = self.logic.current_color
        surf.blit(self.spirals[color], (0, 0),
                  (pos, (pos[0] + VWIDTH, pos[1] + VHEIGHT)))

    def draw_points(self, surface):
        for paths in self.paths_by_color.values():
            for path in paths:
                for point in path.points:
                    point.draw(surface)

class Avatar():
    def __init__(self, logic, screen, size=12):
        self.logic = logic
        self.screen = screen
        self.spiral = screen.spiral
        self.t = screen.spiral.init
        self.speed = avatar_speeds[self.logic.difficulty]
        self.size = size
        self.dev = 0
        self.bouncing = False

    @property
    def polar(self):
        """
        The polar coords of the avatar. (r, theta)
        """
        return self.screen.spiral.radius(self.t, self.dev), self.t

    def change_dev(self, change):
        if -3 < self.dev + change < 3:
            self.dev += change

    def draw(self, surface):
        r = self.screen.spiral.radius(self.t, self.dev)
        abs_pos = self.screen.to_cart(self.t, r)
        s_pos = self.screen.screen_pos
        pos = (abs_pos[0] - s_pos[0], abs_pos[1] - s_pos[1])
        draw.circle(surface, self.screen.gc("avatar"), map(int, pos), self.size)

    def update(self, t_delta):
        d_delta = self.speed * t_delta
        self.t += d_delta / self.spiral.radius(self.t)
        if not (self.spiral.init < self.t < self.spiral.max):
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

    def on_any_path(self):
        for path in self.spiral.paths_by_dev[self.dev]:
            if path.inside(self.t, self.dev):
                return True
        return False

    def get_on_path(self):
        for path in self.spiral.paths_by_dev[self.dev]:
            if path.inside(self.t, self.dev):
                return path

class ParticleManager():
    def __init__(self, logic, screen):
        self.screen = screen
        self.logic = logic

        self.point_ps = {}
        for color in logic.colors:
            names = ("p1", "p2", "p3", "p4")
            particle_colors = []
            for name in names:
                particle_colors.append(self.screen.gc(name, color))
            self.point_ps[color] = particles.CircleExplosion(
                (0, 0), particle_colors, [0, 100], 20)
            self.path_ps = particles.SparkSystem(
                (0, 0), COLOR_SPARKS, [2, 10], 30, 0, 0,
                20)

    def update(self, t_delta):
        pos = self.logic.avatar.cart_viewport(True)
        for ps in self.point_ps.values():
            ps.pos = pos
            ps.update()

        self.path_ps.pos = pos
        # Make sure the angle is always behind the avatar
        angle = self.logic.avatar.t * 360/(2*pi) - 90
        self.path_ps.direction = angle
        self.path_ps.update()
        if self.logic.avatar.on_path() and not self.logic.avatar.bouncing:
            self.path_ps.density = 20
        else:
            self.path_ps.density = 0

    def correct_point_hit(self):
        ps = self.point_ps[self.logic.current_color]
        ps.explode()

    def incorrect_point_hit(self):
        pass

    def draw(self, surface):
        point_ps = self.point_ps[self.logic.current_color]
        point_ps.draw(surface)
        self.path_ps.draw(surface)

class AssetManager():
    font_size = 50

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
        items = self.logic.colors
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

        score = format_score(self.logic.score)
        score = assets.render_text(
            "Score: " + score,
            self.screen.gc("avatar"))
        y = VHEIGHT - 20 - score.get_height() * 2
        x = (VWIDTH - score.get_width())/2
        surface.blit(score, (x, y))

        bonus = assets.render_text(
            "Bonus: " + str(int(self.logic.bonus)),
            self.screen.gc("avatar"))
        y = VHEIGHT - 10 - bonus.get_height()
        x = (VWIDTH - bonus.get_width())/2
        surface.blit(bonus, (x, y))

    def screen_pressed(self, pos):
        for i, bound in enumerate(self.bounds):
            if bound.collidepoint(pos):
                self.logic.change_color(i)
                return True

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
                             self.logic.colors,
                             self, self.logic)
        self.logic.create_spiral_dependants()
        self.last = datetime.utcnow()
        self.assets = AssetManager()

    def show(self):
        self.spiral.prepare()
        self.start_music()
        self.logic.change_color(0)

        while self.logic.running:
            for event in pygame.event.get():
                self.logic.handle_event(event)
            self.update()

            self.draw_all()
            display.flip()
            self.clock.tick(FPS)

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
        self.spiral.draw_points(surface)
        self.logic.particles.draw(surface)
        self.logic.avatar.draw(surface)
        self.logic.hud.draw(surface)

    def draw_all(self):
        """
        Draws the whole game.

        Arguments:
        - `self`:
        """
        disp = display.get_surface()
        self.draw(disp)

    def to_cart(self, t, r=None, force_int=False):
        r = r or self.spiral.radius(t)
        return to_cartesian(t, r, self.spiral.center, force_int)

    def gc(self, color_name, current=None):
        return gc(color_name, current or self.logic.current_color)

    def adjust_to_viewport(self, (x, y)):
        return (x - self.screen_pos[0], y - self.screen_pos[1])

    def play_sound(self, name):
        if android:
            import android_mixer as mixer
        else:
            from pygame import mixer
            mixer.init()
        sound = mixer.Sound(os.path.join("data", "{0}.ogg".format(name)))
        sound.play()

    @property
    def screen_pos(self):
        screen_pos = list(self.to_cart(self.logic.avatar.t))
        screen_pos[0] -= VWIDTH/2
        screen_pos[1] -= VHEIGHT/2
        return tuple(screen_pos)

    def update(self):
        self.logic.update()
        self.last = datetime.utcnow()

    def start_music(self):
        self.play_sound("Intermission")

    def stop(self):
        try:
            import pygame.mixer as mixer
        except ImportError, NotImplementedError:
            import android_mixer as mixer
        mixer.fadeout(1000)

class MenuLogic(Logic):
    selected = 0
    entries = ("Easy", "Medium", "Hard", "Exit")

    def create_spiral_dependants(self):
        Logic.create_spiral_dependants(self)
        self.hud = MenuHUD(self.screen, self)

    def correct_point_hit(self):
        return
    def incorrect_point_hit(self):
        return

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.selected = self.entries.index("Exit")
            self.running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DOWN:
                self.selected += 1
            elif event.key == pygame.K_UP:
                self.selected -= 1
            elif event.key == pygame.K_RETURN:
                self.running = False
            elif event.key == pygame.K_ESCAPE:
                self.selected = self.entries.index("Exit")
                self.running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.hud.screen_pressed(event.pos)

    def update(self):
        Logic.update(self)
        if not self.running and (self.avatar.t > self.screen.spiral.max or\
                                 self.avatar.t < self.screen.spiral.init + 1):
            self.running = True
            self.avatar.speed *= -1

class MenuScreen(Screen):
    def __init__(self, clock):
        self.clock = clock
        self.logic = MenuLogic(self, "hard")
        self.spiral = Spiral(self.width, self.height,
                             self.logic.colors,
                             self, self.logic)
        self.logic.create_spiral_dependants()
        self.last = datetime.utcnow()
        self.assets = AssetManager()

    def show(self):
        Screen.show(self)
        index = self.logic.selected % len(self.logic.entries)
        return self.logic.entries[index].lower()

    def draw(self, surface):
        self.spiral.get_background(surface)
        self.logic.hud.draw(surface)

class MenuHUD(HUD):
    def draw(self, surface):
        self.bounds = []
        for i, entry in enumerate(self.logic.entries):
            if i == self.logic.selected % len(self.logic.entries)\
                    and not android:
                color = "spiral_color"
            else:
                color = "avatar"
            text = self.screen.assets.render_text(entry, self.screen.gc(color))
            y_offset = (VHEIGHT - text.get_height() * len(self.logic.entries) +\
                            20 * len(self.logic.entries))/2
            x = (VWIDTH - text.get_width())/2
            y = text.get_height() * i + 20 * i + y_offset
            surface.blit(text, (x, y))
            self.bounds.append(pygame.Rect(
                    (x, y),
                    (text.get_width(), text.get_height())))

    def screen_pressed(self, position):
        for i, bound in enumerate(self.bounds):
            if bound.collidepoint(position):
                self.logic.running = False
                self.logic.selected = i
                return True

class HighScoreManager():
    def __init__(self):
        if android:
            filename = "/sdcard/Me/highscores.json"
        elif sys.platform == "win32":
            return
        else:
            filename = os.environ["XDG_CONFIG_HOME"] + "/me_highscores.json"
        self.filename = filename

        try:
            os.makedirs(os.path.dirname(filename))
        except OSError:
            pass

        try:
            with open(filename, 'r') as score_file:
                self.scores = json.loads(score_file.read())
                self.scores.sort(reverse=True)
        except (ValueError, IOError):
            print "Creating new highscores file"
            with open(filename, "w") as empty:
                empty.write(json.dumps([0, 0, 0, 0, 0,]))
            self.scores = [0, 0, 0, 0, 0,]

    def score_position(self, score):
        if score < self.scores[-1]:
            return -1
        for i, high in enumerate(self.scores):
            if score > high:
                return i - 1
        return len(self.scores) - 1

    def add_score(self, score):
        if score in self.scores:
            return
        self.scores.append(score)
        self.scores.sort(reverse=True)
        self.scores = self.scores[:5]
        self.write_scores()

    def write_scores(self):
        with open(self.filename, "w") as score_file:
            score_file.write(json.dumps(self.scores))

class ScoreScreen():
    def __init__(self, clock, screen, score, color):
        self.clock = clock
        self.color = color
        self.screen = screen
        self.zoom_size = list(self.screen.get_size())
        self.points = score
        self.dim = 0
        self.menu_state = "ok"
        self.dimmer = None
        self.assets = AssetManager()
        self.running = True
        self.show_highscore = False
        self.highscore_bound = None
        self.scores = HighScoreManager()

    def draw(self):
        viewport = display.get_surface()
        if self.menu_state == "ok":
            self.menu_state = "dim_out_1"
        if self.menu_state == "dim_out_1":
            if not self.dimmer:
                self.dimmer = pygame.Surface(display.get_surface().get_size())
                self.dimmer.fill((0, 0, 0))
            self.dimmer.set_alpha(self.dim)
            self.dim += 1
            viewport.blit(self.dimmer, (0, 0))
            if self.dim > 30:
                self.menu_state = "dim_in_zoom"
                self.dimmer = None
        if self.menu_state in ("dim_in_zoom", "wait"):
            if not self.dimmer:
                self.dimmer = pygame.Surface(display.get_surface().get_size())
            scaled = transform.scale(self.screen, self.zoom_size)
            viewport.blit(scaled,
                          ((-scaled.get_width() + VWIDTH)/2,
                           (-scaled.get_height() + VHEIGHT)/2))

            self.draw_score(viewport)
            self.draw_highscores(viewport)
            self.scores.add_score(self.points)

            if self.menu_state == "dim_in_zoom":
                self.dimmer.set_alpha(self.dim)
                self.dim -= 1
                self.zoom_size[0] -= 10
                self.zoom_size[1] -= 10

            viewport.blit(self.dimmer, (0, 0))
            if self.dim < 4:
                self.menu_state = "wait"

    def draw_score(self, viewport):
        score = format_score(self.points)
        raw = "Score: {0}".format(score)
        surf = self.assets.render_text(raw, from_hex(
                colors[self.color]["avatar"]))
        y = 350
        x = (VWIDTH - surf.get_width())/2
        viewport.blit(surf, (x, y))

    def draw_highscores(self, viewport):
        highscore = self.scores.score_position(self.points)
        if highscore != -1:
            raw = "New Highscore!"
            surf = self.assets.render_text(raw, from_hex(
                    colors[self.color]["avatar"]))
            y = 420
            x = (VWIDTH - surf.get_width())/2
            viewport.blit(surf, (x, y))
            self.highscore_bound = pygame.Rect(
                (x, y), surf.get_size())
        if self.show_highscore:
            for i, high in enumerate(self.scores.scores):
                if high == 0:
                    continue
                if highscore == i:
                    color = colors["yellow"]["border_color"]
                else:
                    color = colors[self.color]["avatar"]
                raw = str(i + 1) + ": " + format_score(high)
                surf = self.assets.render_text(raw, from_hex(
                        color))
                y = 490 + 70 * i
                x = (VWIDTH - surf.get_width())/2
                viewport.blit(surf, (x, y))

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            sys.exit()
        if self.highscore_bound and event.type == pygame.MOUSEBUTTONDOWN:
            if self.highscore_bound.collidepoint(event.pos):
                self.show_highscore = not self.show_highscore
        elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.running = False

    def show(self):
        while self.running:
            self.draw()
            display.flip()
            self.clock.tick(FPS)
            for event in pygame.event.get():
                self.handle_event(event)
            if android:
                if android.check_pause():
                    android.wait_for_resume()

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
        t = self.start + s_offset
        d = ((self.end - e_offset) - (self.start - s_offset))/float(count)
        while t < self.end:
            unhittable = int(random.random() * 100) == 0
            self.points.append(Point(t, self, unhittable))
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

    def passed(self, start, end):
        for point in self.points:
            if start < point.t < end and not point.hit:
                return point

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

        draw.lines(surface, self.spiral.screen.gc("avatar", self.color),
                   False, points, 3)

class Point():
    def __init__(self, t, path, unhittable=False):
        self.t = t
        self.path = path
        self.spiral = path.spiral
        self.dev = path.dev
        self.r = self.spiral.radius(self.t, self.dev)
        self.color = path.color if not unhittable else "grey"
        self.hit = False
        self.unhittable = unhittable

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
        if self.unhittable:
            color = (100, 100, 100)
        else:
            color = self.spiral.screen.gc("avatar", self.color)
        draw.circle(surface, color, pos, 10, 1 if self.hit else 0)

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
        choice = MenuScreen(clock).show()
        if choice == "exit":
            return 0
        else:
            play_game(clock, choice)
    return 0

def play_game(clock, difficulty):
    s = Screen(clock, difficulty)
    s.show()
    color = s.logic.current_color
    screen = s.spiral.spirals[color]
    ss = ScoreScreen(clock, screen, s.logic.score or 0, color)
    ss.show()

if __name__ == "__main__":
    main()
