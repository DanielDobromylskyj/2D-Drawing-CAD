import pygame

class Drawing:
    LINE_WIDTH = 3

    ACTIVE_COLOUR = (0, 0, 0, 255)
    UNACTIVE_COLOUR = (100, 100, 100, 50)

    def __init__(self, name, visible=True):
        self.name = name
        self.visible = visible

        self.pivots = []   # (cx, cy, {...})
        self.lines = []    # ((x1, y1), (x2, y2))

    def get_bounds(self):
        xs, ys = [], []

        for cx, cy, *_ in self.pivots:
            xs.append(cx)
            ys.append(cy)

        for (x1, y1), (x2, y2) in self.lines:
            xs.extend([x1, x2])
            ys.extend([y1, y2])

        if not xs or not ys:
            return (0, 0), (0, 0)

        return (min(xs) - self.LINE_WIDTH, min(ys) - self.LINE_WIDTH), (
            max(xs) + self.LINE_WIDTH, max(ys) + self.LINE_WIDTH
        )

    def draw(self, screen, zoom, view_position, is_active):
        """Draws directly onto the given screen surface."""
        line_colour = self.ACTIVE_COLOUR if is_active else self.UNACTIVE_COLOUR

        for (x1, y1), (x2, y2) in self.lines:
            # scale + offset into screen space
            sx1 = x1 * zoom + view_position[0]
            sy1 = y1 * zoom + view_position[1]
            sx2 = x2 * zoom + view_position[0]
            sy2 = y2 * zoom + view_position[1]

            pygame.draw.line(
                screen,
                line_colour,
                (sx1, sy1), (sx2, sy2),
                width=round(self.LINE_WIDTH * zoom)
            )
