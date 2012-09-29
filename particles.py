import random
from math import cos, sin, radians

import pygame
import pygame.draw

def get_color(proportion, colorarray):
    index = proportion * len(colorarray)
    int_index = int(index)

    start_color = colorarray[int_index-1]
    try:
        end_color = colorarray[int_index]
    except:
        end_color = colorarray[int_index-1]

    part_through = index - int_index
    red = start_color[0]
    green = start_color[1]
    blue = start_color[2]
    red_difference = end_color[0] - red
    green_difference = end_color[1] - green
    blue_difference = end_color[2] - blue
    red += red_difference * part_through
    green += green_difference * part_through
    blue += blue_difference * part_through
    between_color = (int(red),int(green),int(blue))
    return between_color

class SparkSystem(object):
    """
    A system for creating particles that maybe look a little bit like
    sparks coming off a rail. Derived from padlib.py.
    """
    def __init__(self, position, colorarray, speedrange, disperse, direction, density, frames):
        self.pos = position
        self.colorarray = colorarray
        self.speedrange = speedrange
        self.disperse = disperse
        self.direction = direction
        self.density = density
        self.frames = float(frames)
        self.particles = []

    def change_position(self, pos):
        self.pos = pos

    def update(self):
        for x in xrange(self.density):
            self.create_new_particle()
        for p in self.particles:
            p[0][0] += p[1][0]
            p[0][1] += p[1][1]
            p[2] += 1
            if p[2] == self.frames:
                self.particles.remove(p)

    def create_new_particle(self):
        PosBx = self.pos[0]
        PosBy = self.pos[1]
        angle = radians(self.direction+((random.random()-0.5)*self.disperse))
        speed = (random.uniform(self.speedrange[0],self.speedrange[1]))/4.0
        Speed = [speed*cos(angle),speed*sin(angle)]
        self.particles.append([[PosBx,PosBy],Speed,0, angle])

    def draw(self, surface):
        speed = 4
        for p in self.particles:
            v = [speed * cos(p[3]), speed * sin(p[3])]
            color = get_color(p[2] / self.frames, self.colorarray)
            pygame.draw.line(surface, color, map(int, p[0]),
                             [int(p[0][0] + v[0]), int(p[0][1] + v[1])])

class CircleExplosion(object):
    def __init__(self, pos, colorarray, radiusrange, frames):
        self.pos = pos
        self.colorarray = colorarray
        self.sradius, self.eradius = radiusrange
        self.frames = float(frames)
        self.circles = []

    def explode(self):
        self.circles.append(0)

    def update(self):
        self.circles = map((lambda x: x+1), self.circles)
        self.circles = filter((lambda x: x < self.frames), self.circles)

    def draw(self, surface):
        for f in self.circles:
            prop = f / self.frames
            color = get_color(prop, self.colorarray)
            radius = int(self.sradius + (self.eradius - self.sradius) * prop)
            pygame.draw.circle(surface, color, map(int, self.pos), radius, 1)
