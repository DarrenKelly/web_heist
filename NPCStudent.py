"""
NPC Student Class with Multi-Level BFS Pathfinding
"""

import pygame
import random
import math
import time
from collections import deque, defaultdict
from student import Student
from config import TILE_SIZE


class NPCStudent(Student):
    def __init__(self, x, y, name, player_spawn_tile=None, door_z_tile=None, level_id=0, exit_level_id=0):
        super().__init__(x, y, name, sprite_file="studentNPC.png")
        self.speed = random.choice([3, 4])
        self.door_z_tile = door_z_tile
        self.level_id = level_id
        self.exit_level_id = exit_level_id
        self.last_stairway = None
        self.stairway_cooldown = 0.0
        self.arrival_stairway_tile = None
        self.target_stairway_tile = None
        self.target_stairway_char = None
        self.path = []
        self.mode = "seeking_z"  # "seeking_z", "seeking_stairway", or "wandering"
        self.offset_x = random.randint(-8, 8)
        self.offset_y = random.randint(-8, 8)
        self.stuck_frames = 0
        self.replan_cooldown = 0.0
        self.reached_door_z = False

    def get_grid_pos(self):
        return (self.rect.centerx // TILE_SIZE, self.rect.centery // TILE_SIZE)

    def compute_bfs_path(self, start_tile, target_tile, walkable_tiles, blocked_tiles):
        queue = deque([start_tile])
        came_from = {start_tile: None}

        while queue:
            curr = queue.popleft()
            if target_tile is not None and curr == target_tile:
                break
            cx, cy = curr
            for nx, ny in [(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)]:
                nxt = (nx, ny)
                if nxt not in came_from and nxt in walkable_tiles and nxt not in blocked_tiles:
                    came_from[nxt] = curr
                    queue.append(nxt)

        if target_tile is not None and target_tile in came_from:
            path = []
            step = target_tile
            while step != start_tile:
                path.append(step)
                step = came_from[step]
            path.reverse()
            return path, came_from.keys()

        return None, came_from.keys()

    def find_best_stairway(self, curr_tile, curr_level, game, walkable_tiles, blocked_tiles):
        reachable_stairways = []
        for s_tile, s_char in curr_level.stairway_tiles.items():
            dest_info = game.stairway_endpoints.get((self.level_id, s_tile[0], s_tile[1]))
            if not dest_info:
                continue
            (dest_lvl, dest_c, dest_r), ch = dest_info
            is_direct = (dest_lvl == self.exit_level_id)
            p, _ = self.compute_bfs_path(curr_tile, s_tile, walkable_tiles, blocked_tiles)
            if p is not None:
                lvl_dist = game.get_level_distance(dest_lvl, self.exit_level_id)
                reachable_stairways.append((is_direct, lvl_dist, len(p), s_tile, s_char, p))

        if not reachable_stairways:
            return None, None, None, False

        direct = [s for s in reachable_stairways if s[0]]
        if direct:
            direct.sort(key=lambda s: s[2])
            best = direct[0]
            return best[5], best[3], best[4], True

        reachable_stairways.sort(key=lambda s: (s[1], s[2]))
        best = reachable_stairways[0]
        return best[5], best[3], best[4], False

    def update_npc_multilevel(self, game):
        curr_tile = self.get_grid_pos()
        curr_level = game.levels[self.level_id]

        if not self.reached_door_z and self.level_id == self.exit_level_id and self.door_z_tile:
            # Manhattan distance <= 1 triggers as soon as the NPC reaches the tile in front of Door Z
            if abs(curr_tile[0] - self.door_z_tile[0]) + abs(curr_tile[1] - self.door_z_tile[1]) <= 1:
                self.reached_door_z = True
                if game.player:
                    game.player.score += 100
                    game.notification = f"{self.name} reached the school gate! (+100 pts)"
                    game.notification_timer = time.time() + 3.0

        # Clear arrival_stairway_tile once NPC has walked away from the arrival staircase
        if getattr(self, 'arrival_stairway_tile', None):
            arr_c, arr_r = self.arrival_stairway_tile
            arrival_rect = pygame.Rect(arr_c * TILE_SIZE, arr_r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            if not self.rect.colliderect(arrival_rect):
                self.arrival_stairway_tile = None

        # 1. Stairway transition check
        if curr_tile in curr_level.stairway_tiles:
            stair_char = curr_level.stairway_tiles[curr_tile]
            # NPCs only take stairways if they need them (not already on the exit level unless seeking a stairway)
            can_take_stairs = (self.level_id != self.exit_level_id or self.mode == "seeking_stairway")
            if can_take_stairs and getattr(self, 'arrival_stairway_tile', None) is None:
                dest_info = game.stairway_endpoints.get((self.level_id, curr_tile[0], curr_tile[1]))
                if dest_info:
                    (dest_lvl, dest_c, dest_r), ch = dest_info
                    self.level_id = dest_lvl
                    self.rect.centerx = dest_c * TILE_SIZE + TILE_SIZE // 2 + self.offset_x
                    self.rect.centery = dest_r * TILE_SIZE + TILE_SIZE // 2 + self.offset_y
                    self.pos_x = float(self.rect.x)
                    self.pos_y = float(self.rect.y)
                    self.last_stairway = ch
                    self.arrival_stairway_tile = (dest_c, dest_r)
                    self.path.clear()
                    self.mode = "seeking_z"
                    self.replan_cooldown = 0.0
                    curr_tile = (dest_c, dest_r)
                    curr_level = game.levels[self.level_id]
        else:
            self.last_stairway = None

        solid_objects = curr_level.get_solid_objects()
        walkable_tiles = curr_level.walkable_tiles
        blocked_tiles = curr_level.get_blocked_tiles()

        # 2. While wandering, occasionally check if Door Z or a direct stairway has become reachable
        if self.mode == "wandering" and self.path and random.random() < 0.02:
            if self.level_id == self.exit_level_id:
                if self.door_z_tile:
                    path_to_z, _ = self.compute_bfs_path(curr_tile, self.door_z_tile, walkable_tiles, blocked_tiles)
                    if path_to_z:
                        self.mode = "seeking_z"
                        self.path = path_to_z
            else:
                p, s_tile, s_char, is_direct = self.find_best_stairway(curr_tile, curr_level, game, walkable_tiles, blocked_tiles)
                if p and is_direct:
                    self.mode = "seeking_stairway"
                    self.path = p
                    self.target_stairway_tile = s_tile
                    self.target_stairway_char = s_char

        # 3. Path planning when path is empty
        if not self.path:
            now = time.time()
            if now < self.replan_cooldown:
                fake_keys = defaultdict(bool)
                super().update(fake_keys, solid_objects)
                return

            if self.mode == "wandering":
                self.mode = "seeking_z"

            if self.level_id == self.exit_level_id:
                if self.door_z_tile:
                    path_to_z, reachable = self.compute_bfs_path(curr_tile, self.door_z_tile, walkable_tiles, blocked_tiles)
                    if path_to_z:
                        self.path = path_to_z
                        self.mode = "seeking_z"
                    else:
                        zx, zy = self.door_z_tile
                        closest_tile = min(reachable, key=lambda t: (t[0] - zx)**2 + (t[1] - zy)**2) if reachable else curr_tile
                        if closest_tile != curr_tile:
                            path_to_closest, _ = self.compute_bfs_path(curr_tile, closest_tile, walkable_tiles, blocked_tiles)
                            if path_to_closest:
                                self.path = path_to_closest
                            else:
                                closest_tile = curr_tile
                        if closest_tile == curr_tile:
                            self.mode = "wandering"
                            candidates = [t for t in reachable if t != curr_tile]
                            if candidates:
                                rand_target = min(random.sample(candidates, min(len(candidates), 2)), key=lambda t: (t[0] - zx)**2 + (t[1] - zy)**2)
                                rand_path, _ = self.compute_bfs_path(curr_tile, rand_target, walkable_tiles, blocked_tiles)
                                if rand_path:
                                    self.path = rand_path
            else:
                p, s_tile, s_char, is_direct = self.find_best_stairway(curr_tile, curr_level, game, walkable_tiles, blocked_tiles)
                if p:
                    self.path = p
                    self.mode = "seeking_stairway"
                    self.target_stairway_tile = s_tile
                    self.target_stairway_char = s_char
                else:
                    all_stairs = list(curr_level.stairway_tiles.keys())
                    _, reachable = self.compute_bfs_path(curr_tile, None, walkable_tiles, blocked_tiles)
                    if reachable and all_stairs:
                        def dist_to_nearest_stair(t):
                            return min((t[0] - sx)**2 + (t[1] - sy)**2 for sx, sy in all_stairs)
                        closest_tile = min(reachable, key=dist_to_nearest_stair)
                        if closest_tile != curr_tile:
                            path_to_closest, _ = self.compute_bfs_path(curr_tile, closest_tile, walkable_tiles, blocked_tiles)
                            if path_to_closest:
                                self.path = path_to_closest
                            else:
                                closest_tile = curr_tile
                        if closest_tile == curr_tile:
                            self.mode = "wandering"
                            candidates = [t for t in reachable if t != curr_tile]
                            if candidates:
                                rand_target = random.choice(candidates)
                                rand_path, _ = self.compute_bfs_path(curr_tile, rand_target, walkable_tiles, blocked_tiles)
                                if rand_path:
                                    self.path = rand_path

            if not self.path:
                self.replan_cooldown = time.time() + random.uniform(0.4, 0.8)

        # 4. Movement along path
        fake_keys = defaultdict(bool)
        if self.path:
            next_col, next_row = self.path[0]
            if (next_col, next_row) in blocked_tiles and (next_col, next_row) != self.door_z_tile and (next_col, next_row) not in curr_level.stairway_tiles:
                self.path.clear()
            else:
                target_px = next_col * TILE_SIZE + (TILE_SIZE // 2) + self.offset_x
                target_py = next_row * TILE_SIZE + (TILE_SIZE // 2) + self.offset_y
                dx = target_px - self.rect.centerx
                dy = target_py - self.rect.centery

                if math.hypot(dx, dy) <= self.speed + 4:
                    self.path.pop(0)
                else:
                    if dx < -2: fake_keys[pygame.K_LEFT] = True
                    elif dx > 2: fake_keys[pygame.K_RIGHT] = True
                    if dy < -2: fake_keys[pygame.K_UP] = True
                    elif dy > 2: fake_keys[pygame.K_DOWN] = True

        old_x, old_y = self.rect.x, self.rect.y
        super().update(fake_keys, solid_objects)

        if self.path and self.rect.x == old_x and self.rect.y == old_y:
            self.stuck_frames += 1
            if self.stuck_frames > 20:
                self.path.clear()
                self.stuck_frames = 0
                self.mode = "wandering"
        else:
            self.stuck_frames = 0

    def update_npc(self, solid_objects, walkable_tiles, blocked_tiles):
        curr_tile = self.get_grid_pos()

        if self.mode == "wandering" and self.path and random.random() < 0.05:
            path_to_z, _ = self.compute_bfs_path(curr_tile, self.door_z_tile, walkable_tiles, blocked_tiles)
            if path_to_z:
                self.mode = "seeking_z"
                self.path = path_to_z

        if not self.path:
            if self.mode == "wandering":
                self.mode = "seeking_z"

            if self.mode == "seeking_z":
                path_to_z, reachable = self.compute_bfs_path(curr_tile, self.door_z_tile, walkable_tiles, blocked_tiles)
                if path_to_z:
                    self.path = path_to_z
                else:
                    if reachable:
                        zx, zy = self.door_z_tile
                        closest_tile = min(reachable, key=lambda t: (t[0] - zx) ** 2 + (t[1] - zy) ** 2)

                        if closest_tile != curr_tile:
                            path_to_closest, _ = self.compute_bfs_path(curr_tile, closest_tile, walkable_tiles, blocked_tiles)
                            if path_to_closest:
                                self.path = path_to_closest
                            else:
                                closest_tile = curr_tile

                        if closest_tile == curr_tile:
                            self.mode = "wandering"
                            candidates = [t for t in reachable if t != curr_tile]
                            if candidates:
                                if len(candidates) >= 2:
                                    cand1, cand2 = random.sample(candidates, 2)
                                    rand_target = min(cand1, cand2, key=lambda t: (t[0] - zx) ** 2 + (t[1] - zy) ** 2)
                                else:
                                    rand_target = candidates[0]

                                rand_path, _ = self.compute_bfs_path(curr_tile, rand_target, walkable_tiles, blocked_tiles)
                                if rand_path:
                                    self.path = rand_path

        fake_keys = defaultdict(bool)
        if self.path:
            next_col, next_row = self.path[0]
            if (next_col, next_row) in blocked_tiles and (next_col, next_row) != self.door_z_tile:
                self.path.clear()
            else:
                target_px = next_col * TILE_SIZE + (TILE_SIZE // 2) + self.offset_x
                target_py = next_row * TILE_SIZE + (TILE_SIZE // 2) + self.offset_y
                dx = target_px - self.rect.centerx
                dy = target_py - self.rect.centery

                if math.hypot(dx, dy) <= self.speed + 4:
                    self.path.pop(0)
                else:
                    if dx < -2: fake_keys[pygame.K_LEFT] = True
                    elif dx > 2: fake_keys[pygame.K_RIGHT] = True
                    if dy < -2: fake_keys[pygame.K_UP] = True
                    elif dy > 2: fake_keys[pygame.K_DOWN] = True

        old_x, old_y = self.rect.x, self.rect.y
        super().update(fake_keys, solid_objects)

        if self.path and self.rect.x == old_x and self.rect.y == old_y:
            self.stuck_frames += 1
            if self.stuck_frames > 20:
                self.path.clear()
                self.stuck_frames = 0
                self.mode = "wandering"
        else:
            self.stuck_frames = 0
