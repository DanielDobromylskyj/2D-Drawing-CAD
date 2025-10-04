import math
from collections import defaultdict

import pygame

from drawing import Drawing



def is_closed_polygon(lines):
    adj = defaultdict(set)
    for (x1, y1), (x2, y2) in lines:
        adj[(x1, y1)].add((x2, y2))
        adj[(x2, y2)].add((x1, y1))

    # Every vertex must connect to exactly 2
    if not all(len(neighbors) == 2 for neighbors in adj.values()):
        return False, None

    start = next(iter(adj))
    visited_edges = set()
    current = start
    prev = None
    polygon = [current]

    while True:
        neighbors = adj[current]
        next_vertex = [n for n in neighbors if n != prev][0]
        edge = tuple(sorted([current, next_vertex]))

        if edge in visited_edges:
            break

        visited_edges.add(edge)
        polygon.append(next_vertex)
        prev, current = current, next_vertex

    # Closed if we ended back at start and used all edges (This caused some troubles, forgot to check for all edges)
    if polygon[0] == polygon[-1] and len(visited_edges) == len(lines):
        return True, polygon
    return False, None

def polygon_area(polygon):  # https://www.mathsisfun.com/geometry/area-irregular-polygons.html
    area = 0
    for line in polygon:
        (x1, y1), (x2, y2) = line
        area += x1 * y2 - x2 * y1
    return abs(area) / 2

def polygon_centroid(polygon):
    """ Polygon Must Be Closed (First == Last) """
    A = 0
    Cx = 0
    Cy = 0
    for line in polygon:
        (x0, y0), (x1, y1) = line
        cross = x0 * y1 - x1 * y0
        A += cross
        Cx += (x0 + x1) * cross
        Cy += (y0 + y1) * cross

    A = A / 2
    if A == 0:
        return None  # Bad stuff, dont want to X / 0

    Cx = Cx / (6 * A)
    Cy = Cy / (6 * A)
    return Cx, Cy


def transform_point(local_point, body_data):
    """Transform a local pivot point (x,y) into world space given position+rotation."""
    lx, ly = local_point
    px, py = body_data["position"]
    theta = body_data["rotation"]

    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    wx = cos_t * lx - sin_t * ly + px
    wy = sin_t * lx + cos_t * ly + py
    return wx, wy


class SimulationException(Exception):
    pass

class Simulation:
    GRAVITY = -9.81  # m/s^2 (downwards)
    MASS_PER_AREA = 0.05  # kg/m^2

    def __init__(self, drawings, gravity=True):
        self.drawings = drawings
        self.current_tick = 0
        self.use_gravity = gravity

        self.pivot_image = pygame.image.load("assets/placables/pivot.png").convert_alpha()

        self.__prepare_drawings()

    def __calculate_mass(self, drawing):
        area = polygon_area(drawing.lines) * 1e-6  # convert mm^2 → m^2
        return self.MASS_PER_AREA * area if area > 0 else 1.0

    def __calculate_center_of_mass(self, drawing):
        return polygon_centroid(drawing.lines)


    def __prepare_drawings(self):
        for drawing in self.drawings:
            closed, polygon = is_closed_polygon(drawing.lines)

            if not closed:
                raise SimulationException("Polygon is not enclosed or is multiple objects")

            drawing.simulator_data = {
                "tick": -1,
                "mass": self.__calculate_mass(drawing),
                "center_of_mass": self.__calculate_center_of_mass(drawing),

                "rotation": 0.0,
                "rotational_velocity": 0.0,

                "position": (0.0, 0.0),
                "vertical_velocity": 0.0,
                "horizontal_velocity": 0.0,

                "forces": []
            }

    def tick(self, delta_time):
        """Advance simulation by delta_time seconds."""
        # 1. Apply forces (gravity, user-defined)
        for drawing in self.drawings:
            data = drawing.simulator_data
            if self.use_gravity and not drawing.anchored:
                data["forces"].append((0.0, data["mass"] * self.GRAVITY))

        # 2. Integrate motion
        for drawing in self.drawings:
            data = drawing.simulator_data

            if drawing.anchored:
                # Keep locked in place
                data["position"] = (0.0, 0.0)
                data["horizontal_velocity"] = 0.0
                data["vertical_velocity"] = 0.0
                data["rotation"] = 0.0
                data["rotational_velocity"] = 0.0
                data["forces"] = []
                continue

            # Sum forces
            fx = sum(f[0] for f in data["forces"])
            fy = sum(f[1] for f in data["forces"])

            ax = fx / data["mass"]
            ay = fy / data["mass"]

            # Linear motion
            data["horizontal_velocity"] += ax * delta_time
            data["vertical_velocity"] += ay * delta_time

            px, py = data["position"]
            px += data["horizontal_velocity"] * delta_time
            py += data["vertical_velocity"] * delta_time
            data["position"] = (px, py)

            # Angular motion (TODO: apply torques if needed)
            data["rotation"] += data["rotational_velocity"] * delta_time

            # Reset forces
            data["forces"] = []

        # 3. Enforce pivot constraints
        for d1 in self.drawings:
            for pivot in d1.pivots:
                if not pivot:
                    continue

                px, py, info = pivot
                if not isinstance(info, dict):
                    continue

                if "connected_to" not in info:
                    continue

                d2, other_pivot = info["connected_to"]

                # world positions of pivot points
                w1 = transform_point((px, py), d1.simulator_data)
                w2 = transform_point(other_pivot[:2], d2.simulator_data)

                dx, dy = (w2[0] - w1[0], w2[1] - w1[1])
                dist = math.hypot(dx, dy)

                if dist > 1e-6:  # tolerance
                    correction = (dx / 2.0, dy / 2.0)
                    if not d1.anchored:
                        p1x, p1y = d1.simulator_data["position"]
                        d1.simulator_data["position"] = (p1x + correction[0], p1y + correction[1])

                    if not d2.anchored:
                        p2x, p2y = d2.simulator_data["position"]
                        d2.simulator_data["position"] = (p2x - correction[0], p2y - correction[1])

        self.current_tick += 1

    def render(self, screen, zoom, view_position):
        """Render all drawings with their simulated transforms applied."""
        for drawing in self.drawings:
            data = drawing.simulator_data
            pos = data["position"]
            rot = data["rotation"]

            # draw polygon lines
            line_colour = Drawing.ACTIVE_COLOUR
            cos_t, sin_t = math.cos(rot), math.sin(rot)
            for (x1, y1), (x2, y2) in drawing.lines:
                # transform into world space
                wx1 = cos_t * x1 - sin_t * y1 + pos[0]
                wy1 = sin_t * x1 + cos_t * y1 + pos[1]
                wx2 = cos_t * x2 - sin_t * y2 + pos[0]
                wy2 = sin_t * x2 + cos_t * y2 + pos[1]

                sx1 = wx1 * zoom + view_position[0]
                sy1 = wy1 * zoom + view_position[1]
                sx2 = wx2 * zoom + view_position[0]
                sy2 = wy2 * zoom + view_position[1]

                pygame.draw.line(
                    screen,
                    line_colour,
                    (sx1, sy1), (sx2, sy2),
                    width=round(Drawing.LINE_WIDTH * zoom)
                )

            # draw pivots
            for pivot in drawing.pivots:
                if not pivot:
                    continue
                px, py, _ = pivot
                wx, wy = transform_point((px, py), data)
                screen_x = wx * zoom + view_position[0]
                screen_y = wy * zoom + view_position[1]
                screen.blit(
                    self.pivot_image,
                    (
                        screen_x - self.pivot_image.get_width() // 2,
                        screen_y - self.pivot_image.get_height() // 2,
                    )
                )


