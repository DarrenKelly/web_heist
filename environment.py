"""
Environment and Level Representation
"""

import os
import re
import pygame
from config import TILE_SIZE, COLOUR_BLACK, WALL_CHARS, UP_CHARS, DOWN_CHARS, LEFT_CHARS, RIGHT_CHARS


class Floor(pygame.sprite.Sprite):
    SHARED_IMAGE = None

    def __init__(self, x, y):
        super().__init__()
        if Floor.SHARED_IMAGE is None:
            Floor.SHARED_IMAGE = pygame.Surface((TILE_SIZE, TILE_SIZE))
            Floor.SHARED_IMAGE.fill((46, 49, 56))
            pygame.draw.rect(Floor.SHARED_IMAGE, (54, 58, 66), (0, 0, TILE_SIZE, TILE_SIZE), 1)
        self.image = Floor.SHARED_IMAGE
        self.rect = self.image.get_rect(topleft=(x, y))


class Void(pygame.sprite.Sprite):
    SHARED_IMAGE = None

    def __init__(self, x, y):
        super().__init__()
        if Void.SHARED_IMAGE is None:
            Void.SHARED_IMAGE = pygame.Surface((TILE_SIZE, TILE_SIZE))
            Void.SHARED_IMAGE.fill(COLOUR_BLACK)
        self.image = Void.SHARED_IMAGE
        self.rect = self.image.get_rect(topleft=(x, y))


class Wall(pygame.sprite.Sprite):
    def __init__(self, x, y, char='─'):
        super().__init__()
        self.char = char
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.render_wall()

    def render_wall(self):
        self.image.fill((25, 28, 36))
        
        has_up = self.char in UP_CHARS
        has_down = self.char in DOWN_CHARS
        has_left = self.char in LEFT_CHARS
        has_right = self.char in RIGHT_CHARS

        if has_up or has_down or has_left or has_right:
            mid = TILE_SIZE // 2
            w = 12
            hw = w // 2
            pipe_col = (105, 120, 145)
            core_col = (165, 185, 215)
            
            pygame.draw.rect(self.image, pipe_col, (mid - hw, mid - hw, w, w))
            
            if has_up:
                pygame.draw.rect(self.image, pipe_col, (mid - hw, 0, w, mid + hw))
                pygame.draw.line(self.image, core_col, (mid, 0), (mid, mid), 4)
            if has_down:
                pygame.draw.rect(self.image, pipe_col, (mid - hw, mid - hw, w, mid + hw))
                pygame.draw.line(self.image, core_col, (mid, mid), (mid, TILE_SIZE), 4)
            if has_left:
                pygame.draw.rect(self.image, pipe_col, (0, mid - hw, mid + hw, w))
                pygame.draw.line(self.image, core_col, (0, mid), (mid, mid), 4)
            if has_right:
                pygame.draw.rect(self.image, pipe_col, (mid - hw, mid - hw, mid + hw, w))
                pygame.draw.line(self.image, core_col, (mid, mid), (TILE_SIZE, mid), 4)
        else:
            pygame.draw.rect(self.image, (65, 70, 85), (0, 0, TILE_SIZE, TILE_SIZE))
            pygame.draw.rect(self.image, (95, 105, 125), (0, 0, TILE_SIZE, TILE_SIZE), 2)
            pygame.draw.rect(self.image, (45, 50, 62), (4, 4, TILE_SIZE - 8, TILE_SIZE - 8))


class Stairway(pygame.sprite.Sprite):
    _badge_font = None

    def __init__(self, x, y, char, dest_level=None):
        super().__init__()
        self.char = char
        self.dest_level = dest_level
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.render_stairway()

    def render_stairway(self):
        self.image.fill((36, 40, 50))
        pygame.draw.rect(self.image, (60, 68, 85), (0, 0, TILE_SIZE, TILE_SIZE), 2)
        
        num_steps = 5
        step_h = (TILE_SIZE - 12) // num_steps
        for i in range(num_steps):
            sy = 6 + i * step_h
            pygame.draw.rect(self.image, (100, 110, 130), (6, sy, TILE_SIZE - 12, step_h - 2))
            pygame.draw.rect(self.image, (25, 28, 38), (6, sy + step_h - 2, TILE_SIZE - 12, 2))

        mid = TILE_SIZE // 2
        badge_radius = 16
        pygame.draw.circle(self.image, (20, 24, 34), (mid, mid), badge_radius)
        pygame.draw.circle(self.image, (240, 200, 80), (mid, mid), badge_radius, 2)
        
        char_font = pygame.font.SysFont(None, 26, bold=True)
        txt = char_font.render(self.char, True, (255, 225, 110))
        self.image.blit(txt, (mid - txt.get_width() // 2, mid - txt.get_height() // 2))

    def draw_badge(self, surface, camera_offset, dest_level_id=None):
        mid_x = self.rect.centerx - camera_offset[0]
        mid_y = self.rect.top - camera_offset[1] - 14
        if getattr(self, '_cached_badge_surf', None) is None:
            if Stairway._badge_font is None:
                Stairway._badge_font = pygame.font.SysFont(None, 18, bold=True)
            dest_str = f"Level {dest_level_id}" if dest_level_id is not None else "Stairs"
            txt = Stairway._badge_font.render(f"Stairs [{self.char}] -> {dest_str}", True, (255, 235, 140))
            bw, bh = txt.get_width() + 8, txt.get_height() + 4
            bsurf = pygame.Surface((bw, bh), pygame.SRCALPHA)
            bsurf.fill((20, 24, 36))
            pygame.draw.rect(bsurf, (200, 160, 60), (0, 0, bw, bh), 1, border_radius=4)
            bsurf.blit(txt, (4, 2))
            self._cached_badge_surf = bsurf

        bg_rect = self._cached_badge_surf.get_rect(center=(mid_x, mid_y))
        surface.blit(self._cached_badge_surf, bg_rect)


class Level:
    def __init__(self, level_id):
        self.level_id = level_id
        self.floors = pygame.sprite.Group()
        self.walls = pygame.sprite.Group()
        self.interactables = pygame.sprite.Group()
        self.solid_objects = pygame.sprite.Group()
        self.stairways = pygame.sprite.Group()
        self.walkable_tiles = set()
        self.stairway_tiles = {}   # (col, row) -> char
        self.stairway_sprites = {} # char -> Stairway
        self.door_z_tile = None
        self.player_spawn_tile = None
        self.npc_spawn_tiles = []
        self.bg_image = None
        self.width = 0
        self.height = 0
        self.max_cols = 0
        self.num_rows = 0
        self.static_wall_blocked = frozenset()

    def init_static_cache(self):
        self.solid_objects = pygame.sprite.Group(self.walls, self.interactables)
        self.static_wall_blocked = frozenset(
            (w.rect.x // TILE_SIZE, w.rect.y // TILE_SIZE) for w in self.walls
        )

    def get_solid_objects(self):
        return self.solid_objects

    def get_blocked_tiles(self):
        interactable_blocked = {
            (i.rect.x // TILE_SIZE, i.rect.y // TILE_SIZE)
            for i in self.interactables
        }
        return self.static_wall_blocked | interactable_blocked


def load_level_map(filename="LEVEL_MAP.txt"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, filename)
    if not os.path.exists(file_path):
        file_path = filename
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\r\n") for line in f]
            while lines and not lines[-1].strip():
                lines.pop()
            if lines:
                return lines
    return [
        "████████┌───────┐████████",
        "████████│       │████████",
        "████┌───┼───Z───┼───┐████",
        "████│!1 │       │ 7!│████",
        "┌───┼─A─┤       ├─B─┼───┐",
        "│!3 D   G       H   F 6!│",
        "│   │ ! │       │ ! │   │",
        "└───┴───┤       ├───┴───┘",
        "████████│   *   │████████",
        "┌───┬───┤       ├───┬───┐",
        "│   │ ! │       │ ! │   │",
        "│!2 C   J       K   E 8!│",
        "└───┼─M─┤       ├─N─┼───┘",
        "████│ 4 │       │ 9 │████",
        "████└───┼─L─┬─I─┼───┘████",
        "████████│ 5 │ 0 │████████",
        "████████└───┴───┘████████"
    ]


def load_level_maps():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    level_files = {}

    pattern = re.compile(r"^LEVEL_MAP_(\d+)\.txt$", re.IGNORECASE)
    search_dirs = [base_dir, os.path.join(base_dir, "data"), "data"]
    for d in search_dirs:
        if os.path.exists(d):
            for fname in os.listdir(d):
                match = pattern.match(fname)
                if match:
                    lvl_id = int(match.group(1))
                    if lvl_id not in level_files:
                        level_files[lvl_id] = os.path.join(d, fname)

    maps = {}
    if level_files:
        for lvl_id in sorted(level_files.keys()):
            fpath = level_files[lvl_id]
            with open(fpath, "r", encoding="utf-8") as f:
                lines = [line.rstrip("\r\n") for line in f]
                while lines and not lines[-1].strip():
                    lines.pop()
                maps[lvl_id] = lines
        return maps

    for candidate in [
        os.path.join(base_dir, "LEVEL_MAP.txt"),
        os.path.join(base_dir, "data", "LEVEL_MAP.txt"),
        "LEVEL_MAP.txt"
    ]:
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                lines = [line.rstrip("\r\n") for line in f]
                while lines and not lines[-1].strip():
                    lines.pop()
                return {0: lines}

    return {0: load_level_map()}

