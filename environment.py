"""
Environment, Multi-Level World Builder, Progression Mapping, and Rendering
"""

from collections import defaultdict, deque
import json
import math
import os
import random
import re
import pygame

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, TILE_SIZE, COLOUR_BLACK,
    WALL_CHARS, UP_CHARS, DOWN_CHARS, LEFT_CHARS, RIGHT_CHARS, log_diag
)
from chest import Chest, OBJECT_DEFINITIONS, load_chest_sheet
from door import Door
from student import HeroStudent
from npc_student import NPCStudent
from questions import allocate_tiered_questions


DEFAULT_CHEST_TO_DOORS_MAP = {
    '0': ['Z'],  # Chest 0 (Bag of Jelly Snakes) is required for Door Z
    '1': ['B'],  # Chest 1 (Gold Key) is required for Door B
    '2': ['D'],  # Chest 2 (Emerald Key) is required for Door D
    '3': ['F'],  # Chest 3 (Sapphire Key) is required for Door F
    '4': ['E'],  # Chest 4 (Lock picks) is required for Door E
    '5': ['A'],  # Chest 5 (Ruby Key) is required for Door A
    '6': ['M'],  # Chest 6 (Battering Ram) is required for Door M
    '7': ['C'],  # Chest 7 (Skeleton Key) is required for Door C
    '8': ['N'],  # Chest 8 (Key Card) is required for Door N
    '9': ['I'],  # Chest 9 (Silver Key) is required for Door I
}


def load_chest_to_doors_map(filename="chest_to_doors.json"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        filename,
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "data", filename),
        "chest_to_doors.json",
        os.path.join(base_dir, "chest_to_doors.json"),
        os.path.join(base_dir, "data", "chest_to_doors.json"),
        os.path.join("data", "chest_to_doors.json"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                mapping = {}
                for k, v in raw_data.items():
                    k_str = str(k).strip()
                    if isinstance(v, list):
                        mapping[k_str] = [str(d).strip().upper() for d in v if str(d).strip()]
                    elif isinstance(v, str):
                        doors = [d.strip().upper() for d in v.split(",") if d.strip()]
                        mapping[k_str] = doors
                    elif v is not None:
                        mapping[k_str] = [str(v).strip().upper()]
                if mapping:
                    return mapping
            except Exception as e:
                print(f"Error loading chest to doors map from {candidate}: {e}")
    return dict(DEFAULT_CHEST_TO_DOORS_MAP)


def get_door_requirement(door_char, mapping=None):
    active_map = mapping if mapping is not None else load_chest_to_doors_map()
    for chest_id, doors in active_map.items():
        door_list = [doors] if isinstance(doors, str) else list(doors)
        if door_char in door_list:
            item_info = OBJECT_DEFINITIONS.get(str(chest_id), {})
            item_name = item_info.get("name", f"Chest {chest_id} Item")
            return item_name, str(chest_id)
    return None, None


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
        self.stairway_tiles = {}    # (col, row) -> char
        self.stairway_sprites = {}  # char -> Stairway
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
    candidates = [
        os.path.join(base_dir, "data", filename),
        os.path.join("data", filename),
        os.path.join(base_dir, filename),
        filename,
    ]
    for file_path in candidates:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.rstrip("\r\n") for line in f]
                while lines and not lines[-1].strip():
                    lines.pop()
                if lines:
                    return lines
    log_diag("WARN", f"Map file '{filename}' not found! Falling back to hardcoded default ASCII map.")
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
        "████████└───┴───┘████████",
    ]


def load_level_maps():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    level_files = {}

    pattern = re.compile(r"^LEVEL_MAP_(\d+)\.txt$", re.IGNORECASE)
    search_dirs = [os.path.join(base_dir, "data"), "data", base_dir]
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
        os.path.join(base_dir, "data", "LEVEL_MAP.txt"),
        os.path.join("data", "LEVEL_MAP.txt"),
        os.path.join(base_dir, "LEVEL_MAP.txt"),
        "LEVEL_MAP.txt",
    ]:
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                lines = [line.rstrip("\r\n") for line in f]
                while lines and not lines[-1].strip():
                    lines.pop()
                return {0: lines}

    return {0: load_level_map()}


class World:
    """
    Owns all loaded Levels, stairway topology, player/NPC groups, map construction,
    and camera-culled world rendering.
    """

    def __init__(self):
        self.levels = {}
        self.stairway_connections = {}
        self.stairway_endpoints = {}
        self.exit_level_id = 0
        self.exit_tile = None
        self.chest_to_doors_map = load_chest_to_doors_map()

        self.npcs = pygame.sprite.Group()
        self.students = pygame.sprite.Group()
        self.player = None
        self.name_font = pygame.font.SysFont(None, 22)

    @property
    def current_level(self):
        if self.player and self.player.level_id in self.levels:
            return self.levels[self.player.level_id]
        if self.levels:
            return next(iter(self.levels.values()))
        return None

    def get_level_distance(self, start_lvl, target_lvl):
        if start_lvl == target_lvl:
            return 0
        queue = deque([(start_lvl, 0)])
        visited = {start_lvl}
        while queue:
            curr, dist = queue.popleft()
            if curr == target_lvl:
                return dist
            for (lvl1, _, _), (lvl2, _, _) in self.stairway_connections.values():
                neighbor = None
                if lvl1 == curr:
                    neighbor = lvl2
                elif lvl2 == curr:
                    neighbor = lvl1
                if neighbor is not None and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        return 999

    def load(self, hero_name, npc_names, questions):
        """
        Builds all Level instances from LEVEL_MAP_*.txt, connects stairways,
        spawns the hero and NPCs, and allocates tiered questions.
        Returns an optional audit warning message if the question bank is smaller
        than the number of map triggers.
        """
        try:
            load_chest_sheet()
        except Exception as e:
            print(f"Error loading chest sheet: {e}")

        level_maps = load_level_maps()

        stairway_locs = defaultdict(list)
        player_spawn_loc = None
        door_z_loc = None

        for lvl_id, lines in level_maps.items():
            for r_idx, row in enumerate(lines):
                for c_idx, ch in enumerate(row):
                    if ch.isalpha() and ch.islower():
                        stairway_locs[ch].append((lvl_id, c_idx, r_idx))
                    elif ch in ('*', 'P') and player_spawn_loc is None:
                        player_spawn_loc = (lvl_id, c_idx, r_idx)
                    elif ch == 'Z':
                        door_z_loc = (lvl_id, c_idx, r_idx)

        self.stairway_connections = {}
        self.stairway_endpoints = {}
        for ch, locs in stairway_locs.items():
            if len(locs) == 2:
                loc1, loc2 = locs[0], locs[1]
                self.stairway_connections[ch] = (loc1, loc2)
                self.stairway_endpoints[loc1] = (loc2, ch)
                self.stairway_endpoints[loc2] = (loc1, ch)
            else:
                print(f"Warning: Stairway '{ch}' appeared {len(locs)} times across maps (expected exactly 2)")

        if door_z_loc:
            self.exit_level_id = door_z_loc[0]
            self.exit_tile = (door_z_loc[1], door_z_loc[2])
        else:
            log_diag("WARN", "No exit door 'Z' found in level maps! Defaulting exit_tile to Level 0, (12, 2).")
            self.exit_level_id = 0
            self.exit_tile = (12, 2)

        if player_spawn_loc:
            player_start_lvl, player_start_col, player_start_row = player_spawn_loc
        else:
            log_diag("WARN", "No player spawn ('*' or 'P') found in level maps! Defaulting spawn to Level 0, (12, 8).")
            player_start_lvl, player_start_col, player_start_row = 0, 12, 8

        self.levels = {}
        self.npcs.empty()
        self.students.empty()
        self.player = None

        candidate_npc_spawns = []
        door_z_list = []
        chest_list = []
        key_door_list = []
        unkeyed_door_list = []

        base_dir = os.path.dirname(os.path.abspath(__file__))

        for lvl_id, lines in level_maps.items():
            lvl = Level(lvl_id)
            if door_z_loc and door_z_loc[0] == lvl_id:
                lvl.door_z_tile = self.exit_tile

            max_cols = max(len(row) for row in lines) if lines else 0
            num_rows = len(lines)
            lvl.width = max_cols * TILE_SIZE
            lvl.height = num_rows * TILE_SIZE

            bg_candidates = [
                os.path.join(base_dir, "img", f"LEVEL_BG_{lvl_id}.png"),
                os.path.join(base_dir, f"LEVEL_BG_{lvl_id}.png"),
                os.path.join(base_dir, "img", f"LEVEL_BG_{lvl_id}.jpg"),
                os.path.join(base_dir, f"LEVEL_BG_{lvl_id}.jpg"),
            ]
            for bg_path in bg_candidates:
                if os.path.exists(bg_path):
                    try:
                        bg_raw = pygame.image.load(bg_path).convert()
                        lvl.bg_image = pygame.transform.smoothscale(bg_raw, (lvl.width, lvl.height))
                        break
                    except Exception as e:
                        print(f"Error loading background image from {bg_path}: {e}")

            for r_idx, row in enumerate(lines):
                for c_idx in range(max_cols):
                    tile = row[c_idx] if c_idx < len(row) else '█'
                    x, y = c_idx * TILE_SIZE, r_idx * TILE_SIZE

                    if tile == '█':
                        lvl.floors.add(Void(x, y))
                    elif tile in WALL_CHARS:
                        lvl.walls.add(Wall(x, y, tile))
                    elif tile.isalpha() and tile.islower():
                        dest_info = self.stairway_endpoints.get((lvl_id, c_idx, r_idx))
                        dest_lvl = dest_info[0][0] if dest_info else None
                        stair = Stairway(x, y, tile, dest_lvl)
                        lvl.stairways.add(stair)
                        lvl.stairway_tiles[(c_idx, r_idx)] = tile
                        lvl.stairway_sprites[tile] = stair
                        lvl.walkable_tiles.add((c_idx, r_idx))
                    elif tile == '.':
                        lvl.walkable_tiles.add((c_idx, r_idx))
                        if lvl.bg_image is None:
                            lvl.floors.add(Floor(x, y))
                    else:
                        lvl.floors.add(Floor(x, y))
                        lvl.walkable_tiles.add((c_idx, r_idx))

                        if tile in ('*', 'P'):
                            if self.player is None:
                                self.player = HeroStudent(x, y, hero_name, lvl_id)
                        elif tile == '!':
                            candidate_npc_spawns.append((lvl_id, x, y))
                        elif tile.isdigit():
                            chest = Chest(x, y, tile, None)
                            lvl.interactables.add(chest)
                            chest_list.append(chest)
                        elif tile.isalpha() and tile.isupper():
                            req_item, req_chest_id = get_door_requirement(tile, self.chest_to_doors_map)
                            door = Door(x, y, tile, None, req_item, req_chest_id)
                            lvl.interactables.add(door)
                            if tile == 'Z':
                                door_z_list.append(door)
                            elif req_item is not None:
                                key_door_list.append(door)
                            else:
                                unkeyed_door_list.append(door)

            lvl.max_cols = max_cols
            lvl.num_rows = num_rows
            lvl.init_static_cache()
            self.levels[lvl_id] = lvl

        audit_warning = allocate_tiered_questions(
            questions, door_z_list, chest_list, key_door_list, unkeyed_door_list
        )

        random.shuffle(candidate_npc_spawns)
        shuffled_npcs = list(npc_names)
        random.shuffle(shuffled_npcs)
        spawned_count = min(len(shuffled_npcs), len(candidate_npc_spawns))
        print(
            f"[AUDIT] Candidate '!' Spawns: {len(candidate_npc_spawns)} | "
            f"NPC Students to Spawn: {len(shuffled_npcs)} | Spawned: {spawned_count}"
        )
        for s_name, (spawn_lvl_id, sx, sy) in zip(shuffled_npcs, candidate_npc_spawns):
            npc = NPCStudent(
                sx, sy, s_name,
                player_spawn_tile=(player_start_col, player_start_row),
                door_z_tile=self.exit_tile,
                level_id=spawn_lvl_id,
                exit_level_id=self.exit_level_id,
            )
            self.npcs.add(npc)
            self.students.add(npc)

        if self.player is None:
            px, py = player_start_col * TILE_SIZE, player_start_row * TILE_SIZE
            self.player = HeroStudent(px, py, hero_name, player_start_lvl)

        self.students.add(self.player)
        return audit_warning

    def open_door(self, door, level):
        pos_x, pos_y = door.rect.x, door.rect.y
        door.kill()
        if level:
            level.floors.add(Floor(pos_x, pos_y))
            level.walkable_tiles.add((pos_x // TILE_SIZE, pos_y // TILE_SIZE))
        self.reset_npc_replan_cooldowns()

    def reset_npc_replan_cooldowns(self):
        for npc in self.npcs:
            npc.replan_cooldown = 0.0

    def draw(self, screen, camera_offset):
        curr_level = self.current_level
        if not curr_level:
            return

        cam_x, cam_y = camera_offset
        cull_rect = pygame.Rect(
            cam_x - TILE_SIZE, cam_y - TILE_SIZE,
            WINDOW_WIDTH + 2 * TILE_SIZE, WINDOW_HEIGHT + 2 * TILE_SIZE,
        )

        if curr_level.bg_image:
            bg_w = curr_level.bg_image.get_width()
            bg_h = curr_level.bg_image.get_height()
            src_x = max(0, cam_x)
            src_y = max(0, cam_y)
            dest_x = max(0, -cam_x)
            dest_y = max(0, -cam_y)
            src_w = min(bg_w - src_x, WINDOW_WIDTH - dest_x)
            src_h = min(bg_h - src_y, WINDOW_HEIGHT - dest_y)
            if src_w > 0 and src_h > 0:
                view_rect = pygame.Rect(src_x, src_y, src_w, src_h)
                screen.blit(curr_level.bg_image, (dest_x, dest_y), area=view_rect)

        for floor in curr_level.floors:
            if cull_rect.colliderect(floor.rect):
                screen.blit(floor.image, (floor.rect.x - cam_x, floor.rect.y - cam_y))

        for stair in curr_level.stairways:
            if cull_rect.colliderect(stair.rect):
                screen.blit(stair.image, (stair.rect.x - cam_x, stair.rect.y - cam_y))

        for wall in curr_level.walls:
            if cull_rect.colliderect(wall.rect):
                screen.blit(wall.image, (wall.rect.x - cam_x, wall.rect.y - cam_y))

        for item in curr_level.interactables:
            if cull_rect.colliderect(item.rect):
                screen.blit(item.image, (item.rect.x - cam_x, item.rect.y - cam_y))

        for npc in self.npcs:
            if self.player and npc.level_id == self.player.level_id and cull_rect.colliderect(npc.rect):
                screen.blit(npc.image, (npc.rect.x - cam_x, npc.rect.y - cam_y))
                npc.draw_name(screen, camera_offset, self.name_font)

        if self.player:
            screen.blit(self.player.image, (self.player.rect.x - cam_x, self.player.rect.y - cam_y))
            self.player.draw_name(screen, camera_offset, self.name_font)

        for item in curr_level.interactables:
            if cull_rect.colliderect(item.rect):
                item.draw_lockout_icon(screen, camera_offset)
                if isinstance(item, Door):
                    has_item = item.has_required_item(self.player.inventory) if self.player else False
                    item.draw_requirement_badge(
                        screen, camera_offset, has_item,
                        self.player.rect.center if self.player else None,
                    )

        if self.player:
            for stair in curr_level.stairways:
                dist = math.hypot(
                    stair.rect.centerx - self.player.rect.centerx,
                    stair.rect.centery - self.player.rect.centery,
                )
                if dist < 140:
                    stair.draw_badge(screen, camera_offset, stair.dest_level)
