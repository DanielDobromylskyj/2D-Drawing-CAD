import pygame
from drawing import Drawing

pygame.init()

class Toolbar:
    TOOL_BAR_BACKGROUND_COLOR = (180, 180, 180)

    def __init__(self, screen_size):
        self.width = screen_size[0] * 0.8
        self.height = 55
        self.surface = None
        self.tool_id = ""

        self.options = [
            {
                "type": "tool",
                "tool_id": "line",
                "icon": pygame.image.load("assets/toolbar/line.png").convert_alpha(),
            },
            {
                "type": "tool",
                "tool_id": "pivot",
                "icon": pygame.image.load("assets/toolbar/pivot.png").convert_alpha(),
            },
        ]

    def click(self, xy, event):
        mx, my = xy
        if self.surface and self.surface.get_at((round(xy[0]), round(xy[1])))[3] > 0:
            x = 5
            for option in self.options:
                if (x < mx < x + 50) and (2 < my < 52):
                    self.tool_id = option["tool_id"]
                    break
                    
                x += 55
            return True
        return False

    def draw(self):
        self.height = 54
        self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(
            self.surface,
            self.TOOL_BAR_BACKGROUND_COLOR,
            (0, 0, self.width, 54),
            border_radius=5
        )

        x = 5
        for option in self.options:
            self.surface.blit(option["icon"], (x, 2))
            x += 55


class App:
    GRID_SPACING = 50
    ZOOM_MULTIPLIER = 0.1

    BACKGROUND_COLOR = (220, 220, 220)
    BACKGROUND_DOT_COLOUR = (40, 40, 40)
    BACKGROUND_DOT_RADIUS: int = 3

    def __init__(self):
        # View + interaction state
        self.zoom = 1.0
        self.dragging = False
        self.view_position = [0, 0]

        # Tool state
        self.line_start_coord = None
        self.drawing_line = False
        self.grid_lock = True

        # Window
        win_size = pygame.display.get_desktop_sizes()[0]
        self.screen = pygame.display.set_mode(win_size, pygame.SRCALPHA)

        # Drawing manager
        self.drawings = [Drawing("Unnamed Drawing")]
        self.active_drawing = 0

        # Icons
        self.VISIBLE_IMAGE = pygame.image.load("assets/drawing_manager/visible.png").convert_alpha()
        self.NOT_VISIBLE_IMAGE = pygame.image.load("assets/drawing_manager/not_visible.png").convert_alpha()
        self.PIVOT_IMAGE = pygame.image.load("assets/placables/pivot.png").convert_alpha()

        # UI
        self.font = pygame.font.SysFont("monospace", 16)
        self.__toolbar = Toolbar(win_size)
        self.__toolbar.draw()

        # Background cache
        self.__background_surface = self.__create_background()
        self.background_update_required = False

        # Drawing manager UI cache
        self.__drawing_manager_surface = self.__create_drawing_manager()
        self.drawing_manager_update_required = False

        # Undo
        self.max_undo_log = 100
        self.undo_log = []


        self.running = False

    def __log_ctrl_z(self, event_type, event_data):
        self.undo_log.insert(0, (event_type, event_data))

        if len(self.undo_log) > self.max_undo_log:
            self.undo_log.pop(-1)

    def undo(self):
        if len(self.undo_log) > 0:
            event_type, event_data = self.undo_log.pop(0)

            if event_type == "line.draw":
                drawing_index, target_index = event_data

                self.drawings[drawing_index].lines.pop(target_index)
                self.drawings[drawing_index].lines.insert(target_index, None)

            elif event_type == "pivot.draw":
                drawing_index, target_index = event_data

                self.drawings[drawing_index].pivots.pop(target_index)
                self.drawings[drawing_index].pivots.insert(target_index, None)

            else:
                raise NotImplementedError(f"Failed to undo value. Not implemented: {event_type}: {event_data}")


    def __create_drawing_manager(self):
        """Builds the drawing manager sidebar surface."""
        width = 250
        height = 20 + len(self.drawings) * 40
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((200, 200, 200, 220))

        y = 10
        for i, drawing in enumerate(self.drawings):
            # highlight active drawing
            if i == self.active_drawing:
                pygame.draw.rect(surface, (180, 180, 250), (5, y - 2, width - 10, 36), border_radius=5)

            # name text
            text = self.font.render(drawing.name, True, (0, 0, 0))
            surface.blit(text, (40, y + 8))

            # visibility toggle
            icon = self.VISIBLE_IMAGE if drawing.visible else self.NOT_VISIBLE_IMAGE
            surface.blit(icon, (10, y + 4))

            y += 40

        return surface.convert_alpha()

    def handle_drawing_manager_click(self, x, y):
        """Handle clicks inside the drawing manager."""
        if not self.__drawing_manager_surface:
            return False

        # Check if click is inside the sidebar
        dm_x, dm_y = 10, 10  # top-left corner of manager on screen
        if not (dm_x <= x <= dm_x + self.__drawing_manager_surface.get_width() and
                dm_y <= y <= dm_y + self.__drawing_manager_surface.get_height()):
            return False

        rel_y = y - dm_y - 10
        index = rel_y // 40
        if 0 <= index < len(self.drawings):
            if 10 <= (x - dm_x) <= 30:  # clicked visibility icon
                self.drawings[index].visible = not self.drawings[index].visible
            else:  # clicked row → set active
                self.active_drawing = index
            self.drawing_manager_update_required = True
            return True

        return False

    def __create_background(self):
        """Pre-rendered dotted background for performance."""
        true_grid_spacing = self.GRID_SPACING * self.zoom
        w, h = self.screen.get_size()
        surface = pygame.Surface(
            (w + int(true_grid_spacing * 2), h + int(true_grid_spacing * 2)),
            pygame.SRCALPHA,
        )
        surface.fill((*self.BACKGROUND_COLOR, 255))

        for x in range(0, surface.get_width(), round(true_grid_spacing)):
            for y in range(0, surface.get_height(), round(true_grid_spacing)):
                pygame.draw.circle(
                    surface,
                    self.BACKGROUND_DOT_COLOUR,
                    (x, y),
                    self.BACKGROUND_DOT_RADIUS,
                )

        return surface.convert_alpha()

    def run(self):
        self.running = True
        while self.running:
            spacing = self.GRID_SPACING * self.zoom

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    x, y = pygame.mouse.get_pos()
                    if ((self.screen.get_width() * 0.1 < x < self.screen.get_width() * 0.9) and
                        (self.screen.get_height() - self.__toolbar.height < y < self.screen.get_height()) and
                        self.__toolbar.click(
                            (x - (self.screen.get_width() * 0.1),
                             y - (self.screen.get_height() - 60)), event)):
                        continue

                    elif event.button == 3:
                        self.dragging = True

                    elif event.button == 1:
                        if self.handle_drawing_manager_click(x, y):
                            continue

                        elif self.__toolbar.tool_id == "line" and not self.drawing_line:
                            self.line_start_coord = (
                                (x - self.view_position[0]) / self.zoom,
                                (y - self.view_position[1]) / self.zoom
                            )
                            if self.grid_lock:
                                self.line_start_coord = (
                                    round((x - self.view_position[0]) / self.zoom / spacing) * spacing,
                                    round((y - self.view_position[1]) / self.zoom / spacing) * spacing
                                )

                            self.drawing_line = True

                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 3:
                        self.dragging = False

                    elif event.button == 1 and self.drawing_line:
                        mx, my = pygame.mouse.get_pos()
                        line_end = (
                            (mx - self.view_position[0]) / self.zoom,
                            (my - self.view_position[1]) / self.zoom
                        )
                        if self.grid_lock:
                            line_end = (
                                round((mx - self.view_position[0]) / self.zoom / spacing) * spacing,
                                round((my - self.view_position[1]) / self.zoom / spacing) * spacing
                            )

                        self.drawings[self.active_drawing].lines.append(
                            (self.line_start_coord, line_end)
                        )
                        self.__log_ctrl_z("line.draw", (self.active_drawing, len(self.drawings[self.active_drawing].lines) - 1))
                        self.drawing_line = False

                    elif event.button == 1 and self.__toolbar.tool_id == "pivot":
                        mx, my = pygame.mouse.get_pos()

                        px = ((mx - self.view_position[0]) / self.zoom) - (self.PIVOT_IMAGE.get_width()  // 2)
                        py = ((my - self.view_position[1]) / self.zoom) - (self.PIVOT_IMAGE.get_height() // 2)

                        if self.grid_lock:
                            grid_size = self.GRID_SPACING
                            px = round(px / (grid_size // 2)) * (grid_size // 2) - (self.PIVOT_IMAGE.get_width()  // 2)
                            py = round(py / (grid_size // 2)) * (grid_size // 2) - (self.PIVOT_IMAGE.get_height() // 2)

                        self.drawings[self.active_drawing].pivots.append(
                            (px, py, None)
                        )

                        self.__log_ctrl_z("pivot.draw",
                                          (self.active_drawing, len(self.drawings[self.active_drawing].pivots) - 1))

                elif event.type == pygame.MOUSEMOTION and self.dragging:
                    dx, dy = event.rel

                    self.view_position[0] += dx
                    self.view_position[1] += dy

                elif event.type == pygame.MOUSEWHEEL:
                    self.zoom += event.y * self.ZOOM_MULTIPLIER
                    if self.zoom < 0.2:
                        self.zoom = 0.2
                    self.background_update_required = True

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LSHIFT:
                        self.grid_lock = False


                elif event.type == pygame.KEYUP:
                    mods = pygame.key.get_mods()

                    if event.key == pygame.K_LSHIFT:
                        self.grid_lock = True

                    if event.key == pygame.K_z and mods & pygame.KMOD_CTRL:
                        self.undo()

            if self.background_update_required:
                self.background_update_required = False
                self.__background_surface = self.__create_background()

            if self.drawing_manager_update_required:
                self.drawing_manager_update_required = False
                self.__drawing_manager_surface = self.__create_drawing_manager()

            # draw background (with view offset)
            self.screen.blit(
                self.__background_surface,
                (self.view_position[0] % spacing - spacing,
                 self.view_position[1] % spacing - spacing)
            )

            # draw drawings
            for i, drawing in enumerate(self.drawings):
                if drawing.visible:
                    drawing.draw(self.screen, self.zoom, self.view_position, i == self.active_drawing)

            # Preview line

            mx, my = pygame.mouse.get_pos()
            if self.drawing_line:
                # start point: drawing → screen
                start = (
                    self.line_start_coord[0] * self.zoom + self.view_position[0],
                    self.line_start_coord[1] * self.zoom + self.view_position[1]
                )

                # Convert mouse → drawing space
                end_dx = (mx - self.view_position[0]) / self.zoom
                end_dy = (my - self.view_position[1]) / self.zoom

                if self.grid_lock:
                    grid_size = self.GRID_SPACING
                    end_dx = round(end_dx / grid_size) * grid_size
                    end_dy = round(end_dy / grid_size) * grid_size

                # back to screen space
                end = (
                    end_dx * self.zoom + self.view_position[0],
                    end_dy * self.zoom + self.view_position[1]
                )

                pygame.draw.line(
                    self.screen,
                    Drawing.ACTIVE_COLOUR,
                    start, end,
                    width=round(Drawing.LINE_WIDTH * self.zoom)
                )

            if self.__toolbar.tool_id == "pivot":
                px = (mx - self.view_position[0]) / self.zoom
                py = (my - self.view_position[1]) / self.zoom

                if self.grid_lock:
                    grid_size = self.GRID_SPACING
                    px = round(px / (grid_size//2)) * (grid_size//2)
                    py = round(py / (grid_size//2)) * (grid_size//2)

                self.screen.blit(
                    self.PIVOT_IMAGE, (px - (self.PIVOT_IMAGE.get_width() // 2), py - (self.PIVOT_IMAGE.get_height() // 2))
                )

            # draw UI
            self.screen.blit(self.__toolbar.surface, (self.screen.get_width() * 0.1, self.screen.get_height() - 60))
            self.screen.blit(self.__drawing_manager_surface, (10, 10))

            pygame.display.flip()

        pygame.quit()


if __name__ == "__main__":
    app = App()
    app.drawings.append(Drawing("Demo 2"))
    app.drawing_manager_update_required = True
    app.run()
