"""
Maths Heist: The Vault of Lollies
Main Entry Point and Game Coordinator
"""
import asyncio
import pygame
import sys
import platform
import urllib.parse
import time
import math
import os
import json
import random
import inspect

from collections import deque, defaultdict

# Detect class_id from URL query string (?class=7MAT1) or command-line argument
class_id = "DEFAULT"
if sys.platform == "emscripten":
    try:
        # 1. Inject CSS to force the Pygbag HTML prompts to be white
        platform.window.eval("""
            var style = document.createElement('style');
            style.innerHTML = 'div, span, #status, #box { color: white !important; text-shadow: 1px 1px 2px black !important; }';
            document.head.appendChild(style);
        """)
        
        # 2. Your existing URL parsing code
        url = platform.window.location.href
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        class_id = params.get("class", ["DEFAULT"])[0]
    except Exception as e:
        print(f"Error reading URL parameters or setting styles: {e}")
elif len(sys.argv) > 1:
    class_id = sys.argv[1]

import config
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, TILE_SIZE,
    COLOUR_BLACK, COLOUR_WHITE, COLOUR_GREY, COLOUR_RED, COLOUR_GREEN,
    WALL_CHARS, SIN_BIN_TIERS, get_class_config
)
from audio import SoundManager
from questions import (
    load_questions, parameterise_question, check_answer,
    load_chest_to_doors_map, get_door_requirement, CHEST_TO_DOORS_MAP
)
from environment import (
    Floor, Void, Wall, Stairway, Level,
    load_level_maps, load_level_map
)
from student import Student, HeroStudent
from NPCStudent import NPCStudent
from door import Door
from chest import Chest, OBJECT_DEFINITIONS, load_chest_sheet, get_chest_images, CHEST_IMAGES
from ui import UIManager

auto_open_for_testing = False
FIREBASE_URL = getattr(config, "FIREBASE_URL", "https://YOUR-FIREBASE-PROJECT-ID-default-rtdb.firebaseio.com")

# Pre-initialise mixer for crisp low-latency 1990s retro audio
pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()
pygame.mixer.init()

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Maths Heist: The MCE Lolly Vault")
clock = pygame.time.Clock()


# --- Helpers to Instantiate Door & Chest Flexibly ---

def create_door_instance(x, y, door_char, q_data, req_item, req_chest_id):
    sig = inspect.signature(Door.__init__)
    params = [p for p in list(sig.parameters.values())[1:] if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    kwargs = {}
    args = []
    for p in params:
        name = p.name.lower()
        if name == 'x': args.append(x)
        elif name == 'y': args.append(y)
        elif name in ('door_char', 'char', 'tile', 'label', 'door_id'): args.append(door_char)
        elif name in ('question_data', 'question', 'q_data', 'q'): args.append(q_data)
        elif name in ('required_item', 'req_item', 'item'): args.append(req_item)
        elif name in ('required_chest_id', 'req_chest_id', 'chest_id'): args.append(req_chest_id)
        elif p.default is not inspect.Parameter.empty:
            pass
        else:
            args.append(None)
    door = Door(*args, **kwargs)
    door.is_door = True
    door.door_char = door_char
    door.question_data = q_data
    door.required_item = req_item
    door.required_chest_id = req_chest_id
    return door


def create_chest_instance(x, y, chest_char, q_data):
    sig = inspect.signature(Chest.__init__)
    params = [p for p in list(sig.parameters.values())[1:] if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    args = []
    for p in params:
        name = p.name.lower()
        if name == 'x': args.append(x)
        elif name == 'y': args.append(y)
        elif name in ('chest_id', 'char', 'tile', 'obj_id', 'chest_char', 'obj_char', 'obj', 'id'): args.append(str(chest_char))
        elif name in ('question_data', 'question', 'q_data', 'q'): args.append(q_data)
        elif p.default is not inspect.Parameter.empty:
            pass
        else:
            args.append(str(chest_char))
    chest = Chest(*args)
    chest.question_data = q_data
    chest.chest_id = str(chest_char)
    chest.obj_char = str(chest_char)
    return chest


# --- Game State Manager ---

class Game:
    def __init__(self):
        self.class_config = get_class_config(class_id)
        print(f"[INIT] Active Class Config: {self.class_config}")

        self.levels = {}
        self.stairway_connections = {}
        self.stairway_endpoints = {}
        self.exit_level_id = 0
        self.exit_tile = None

        self.npcs = pygame.sprite.Group()
        self.students = pygame.sprite.Group()

        self.player = None
        self.player_id = 0
        self.camera_offset = [0, 0]
        self.name_font = pygame.font.SysFont(None, 22)

        self.sound = SoundManager()
        self.ui = UIManager()
        self.chest_to_doors_map = load_chest_to_doors_map()
        self.questions = load_questions(self.class_config.get("questions_file", "questions.json"))
        self.notification = ""
        self.notification_timer = 0
        self.door_popup = None
        self.last_locked_door_char = None

        # Sin-Bin / Focus-Loss Anti-AI State
        self.sin_bin_offences = 0
        self.sin_bin_end_time = 0.0
        self.sin_bin_duration = 0
        self.sin_bin_reason = ""

        # Menu and State Initialisation
        self.state = "name_selection"
        self.current_interactable = None
        self.user_text = ""
        self.menu_index = 0

        self.all_student_names = self.load_students_json(
            self.class_config.get("students_file", "students.json")
        )
        self.hero_name = ""
        self.npc_names = []

        # Cache fonts to prevent browser lockup
        pygame.font.init()
        self.menu_title_font = pygame.font.SysFont(None, 48, bold=True)
        self.menu_sub_font = pygame.font.SysFont(None, 26)
        self.menu_class_font = pygame.font.SysFont(None, 24, bold=True)
        self.menu_name_font = pygame.font.SysFont(None, 24)
        self.menu_hint_font = pygame.font.SysFont(None, 22)
        self.sin_bin_title_font = pygame.font.SysFont(None, 54, bold=True)
        self.sin_bin_timer_font = pygame.font.SysFont(None, 72, bold=True)
        self.sin_bin_body_font = pygame.font.SysFont(None, 28)
        self.hud_score_font = pygame.font.SysFont(None, 28, bold=True)
        self.victory_score_font = pygame.font.SysFont(None, 44, bold=True)

        self.init_focus_tracker()

    @property
    def current_level(self):
        if self.player and self.player.level_id in self.levels:
            return self.levels[self.player.level_id]
        if self.levels:
            return next(iter(self.levels.values()))
        return None

    def send_telemetry(self):
        """
        Sends an anonymised HTTP PUT request to Firebase Realtime Database using
        the student's integer array index (self.player_id) so no student names
        are ever stored in the database. Replaces prior status for that user.
        """
        if sys.platform != "emscripten" or not self.player:
            return
        if not FIREBASE_URL or "YOUR-FIREBASE-PROJECT-ID" in FIREBASE_URL:
            return

        safe_class = urllib.parse.quote(str(class_id).strip().upper())
        endpoint = f"{FIREBASE_URL.rstrip('/')}/classes/{safe_class}/players/{self.player_id}.json"

        payload = json.dumps({
            "id": self.player_id,
            "score": getattr(self.player, "score", 0),
            "inventory": list(getattr(self.player, "inventory", [])),
            "sin_binned": self.state == "sin_bin",
            "escaped": self.state == "victory",
            "updated_at": int(time.time())
        })

        js_code = f"""
        fetch({json.dumps(endpoint)}, {{
            method: 'PUT',
            headers: {{ 'Content-Type': 'application/json' }},
            body: {json.dumps(payload)}
        }}).catch(function(err) {{ console.warn('Telemetry error:', err); }});
        """
        try:
            platform.window.eval(js_code)
        except Exception as e:
            print(f"Telemetry error: {e}")

    def init_focus_tracker(self):
        """
        Registers persistent JavaScript blur and visibilitychange listeners on both
        window and window.top so focus loss is latched even if Chrome suspends
        requestAnimationFrame while the student is in another tab or snipping tool.
        """
        if sys.platform == "emscripten":
            try:
                platform.window.eval("""
                    (function() {
                        if (window._heistTrackerInstalled) return;
                        window._heistTrackerInstalled = true;
                        window._heistFocusLost = false;
                        function markLost() { window._heistFocusLost = true; }
                        window.addEventListener('blur', markLost);
                        document.addEventListener('visibilitychange', function() {
                            if (document.hidden || document.visibilityState !== 'visible') {
                                window._heistFocusLost = true;
                            }
                        });
                        try {
                            if (window.top && window.top !== window) {
                                window.top.addEventListener('blur', markLost);
                                window.top.document.addEventListener('visibilitychange', function() {
                                    if (window.top.document.hidden) window._heistFocusLost = true;
                                });
                            }
                        } catch (e) {}
                    })();
                """)
            except Exception as e:
                print(f"[WARN] Could not install JS focus tracker: {e}")

    def reset_focus_latch(self):
        if sys.platform == "emscripten":
            try:
                platform.window.eval("window._heistFocusLost = false;")
            except Exception:
                print(f"Error resetting focus latch in JS: {e}")

    def check_browser_focus_lost(self):
        if sys.platform == "emscripten":
            try:
                res = platform.window.eval("""
                    (function() {
                        var topHidden = false;
                        var topFocused = true;
                        try {
                            if (window.top && window.top !== window) {
                                topHidden = !!window.top.document.hidden;
                                topFocused = window.top.document.hasFocus();
                            }
                        } catch (e) {}
                        if (window._heistFocusLost || document.hidden || !document.hasFocus() || topHidden || !topFocused) {
                            window._heistFocusLost = false;
                            return "1";
                        }
                        return "0";
                    })()
                """)
                return str(res) == "1"
            except Exception as e:
                print(f"Focus check error: {e}")
        return False

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

    def load_students_json(self, filename="students.json"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            filename,
            os.path.join(base_dir, filename),
            os.path.join(base_dir, "data", filename),
            os.path.join(base_dir, "data", "rosters", filename),
            os.path.join("data", "rosters", filename),
            os.path.join(base_dir, "students.json"),
            "students.json",
            os.path.join(base_dir, "data", "rosters", "7mat2_students.json"),
            os.path.join("data", "rosters", "7mat2_students.json")
        ]
        names = []
        seen = set()
        unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

        for path in unique_candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for s in data.get("students", []):
                        name = s.get("name", "Student").strip()
                        if name:
                            names.append(name)
                    if names:
                        print(f"[INFO] Loaded {len(names)} students from '{path}'.")
                        break
                except Exception as e:
                    print(f"Error loading students roster from '{path}': {e}")

        if not names:
            names = ["John", "Mary", "David", "Sarah"]
        return names

    def show_door_locked_popup(self, door_item):
        door_char = getattr(door_item, "door_char", "?")
        item_name = getattr(door_item, "required_item", "Key")
        chest_id = getattr(door_item, "required_chest_id", "?")
        if self.last_locked_door_char != door_char:
            self.sound.play("door_locked")
            self.last_locked_door_char = door_char
        self.door_popup = {
            "door_char": door_char,
            "item_name": item_name,
            "chest_id": chest_id,
            "expires_at": time.time() + 2.5
        }

    def allocate_tiered_questions(self, door_z_list, chest_list, key_door_list, unkeyed_door_list):
        total_triggers = (
            len(door_z_list) + len(chest_list) +
            len(key_door_list) + len(unkeyed_door_list)
        )
        bank_size = len(self.questions)

        print(
            f"[AUDIT] Map Question Triggers: {total_triggers} "
            f"(Door Z: {len(door_z_list)}, Chests: {len(chest_list)}, "
            f"Key Doors: {len(key_door_list)}, Standard Doors: {len(unkeyed_door_list)}) | "
            f"Question Bank Size: {bank_size}"
        )

        if bank_size < total_triggers:
            shortfall = total_triggers - bank_size
            print(
                f"[AUDIT WARNING] Question bank has {bank_size} questions for {total_triggers} triggers. "
                f"Shortfall: {shortfall}. Pool will be reshuffled for remaining triggers."
            )
            self.notification = f"Audit Warning: {total_triggers} doors/chests vs {bank_size} questions in bank"
            self.notification_timer = time.time() + 4.0

        def build_sorted_pool():
            pool = [dict(q) for q in self.questions]
            random.shuffle(pool)
            pool.sort(key=lambda q: q.get("points", 100), reverse=True)
            return pool

        pool = build_sorted_pool()

        def pop_next_question():
            nonlocal pool
            if not pool:
                pool = build_sorted_pool()
            raw_q = pool.pop(0)
            return parameterise_question(raw_q, force_regenerate=False)

        for door_z in door_z_list:
            door_z.question_data = pop_next_question()

        chest_questions = [pop_next_question() for _ in chest_list]
        random.shuffle(chest_questions)
        for chest, q_data in zip(chest_list, chest_questions):
            chest.question_data = q_data

        key_door_questions = [pop_next_question() for _ in key_door_list]
        random.shuffle(key_door_questions)
        for k_door, q_data in zip(key_door_list, key_door_questions):
            k_door.question_data = q_data

        unkeyed_questions = [pop_next_question() for _ in unkeyed_door_list]
        random.shuffle(unkeyed_questions)
        for u_door, q_data in zip(unkeyed_door_list, unkeyed_questions):
            u_door.question_data = q_data

    def load_map(self):
        try:
            load_chest_sheet()
        except Exception:
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
            self.exit_level_id = 0
            self.exit_tile = (12, 2)

        if player_spawn_loc:
            player_start_lvl = player_spawn_loc[0]
            player_start_col = player_spawn_loc[1]
            player_start_row = player_spawn_loc[2]
        else:
            player_start_lvl = 0
            player_start_col, player_start_row = 12, 8

        self.levels = {}
        self.npcs.empty()
        self.students.empty()
        self.player = None

        candidate_npc_spawns = []
        door_z_list = []
        chest_list = []
        key_door_list = []
        unkeyed_door_list = []

        for lvl_id, lines in level_maps.items():
            lvl = Level(lvl_id)
            if door_z_loc and door_z_loc[0] == lvl_id:
                lvl.door_z_tile = self.exit_tile

            max_cols = max(len(row) for row in lines) if lines else 0
            num_rows = len(lines)
            lvl.width = max_cols * TILE_SIZE
            lvl.height = num_rows * TILE_SIZE

            base_dir = os.path.dirname(os.path.abspath(__file__))
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
                        void = Void(x, y)
                        lvl.floors.add(void)
                    elif tile in WALL_CHARS:
                        wall = Wall(x, y, tile)
                        lvl.walls.add(wall)
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
                            floor = Floor(x, y)
                            lvl.floors.add(floor)
                    else:
                        floor = Floor(x, y)
                        lvl.floors.add(floor)
                        lvl.walkable_tiles.add((c_idx, r_idx))

                        if tile in ('*', 'P'):
                            if self.player is None:
                                self.player = HeroStudent(x, y, self.hero_name, lvl_id)
                                if not hasattr(self.player, "score"):
                                    self.player.score = 0
                        elif tile == '!':
                            candidate_npc_spawns.append((lvl_id, x, y))
                        elif tile.isdigit():
                            chest = create_chest_instance(x, y, tile, None)
                            lvl.interactables.add(chest)
                            chest_list.append(chest)
                        elif tile.isalpha() and tile.isupper():
                            req_item, req_chest_id = get_door_requirement(tile, self.chest_to_doors_map)
                            door = create_door_instance(x, y, tile, None, req_item, req_chest_id)
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

        self.allocate_tiered_questions(door_z_list, chest_list, key_door_list, unkeyed_door_list)

        random.shuffle(candidate_npc_spawns)
        random.shuffle(self.npc_names)
        spawned_count = min(len(self.npc_names), len(candidate_npc_spawns))
        print(
            f"[AUDIT] Candidate '!' Spawns: {len(candidate_npc_spawns)} | "
            f"NPC Students to Spawn: {len(self.npc_names)} | Spawned: {spawned_count}"
        )
        for s_name, (spawn_lvl_id, sx, sy) in zip(self.npc_names, candidate_npc_spawns):
            npc = NPCStudent(
                sx, sy, s_name,
                player_spawn_tile=(player_start_col, player_start_row),
                door_z_tile=self.exit_tile,
                level_id=spawn_lvl_id,
                exit_level_id=self.exit_level_id
            )
            self.npcs.add(npc)
            self.students.add(npc)

        if self.player is None:
            px, py = player_start_col * TILE_SIZE, player_start_row * TILE_SIZE
            self.player = HeroStudent(px, py, self.hero_name, player_start_lvl)
            if not hasattr(self.player, "score"):
                self.player.score = 0

        self.students.add(self.player)

    def trigger_sin_bin(self, reason="Focus lost while viewing a question!"):
        tier_idx = min(self.sin_bin_offences, len(SIN_BIN_TIERS) - 1)
        penalty = SIN_BIN_TIERS[tier_idx]
        self.sin_bin_offences += 1
        self.sin_bin_duration = penalty
        self.sin_bin_end_time = time.time() + penalty
        self.sin_bin_reason = reason

        if self.current_interactable and getattr(self.current_interactable, "question_data", None):
            self.current_interactable.question_data = parameterise_question(
                self.current_interactable.question_data,
                force_regenerate=True
            )

        self.sound.play("wrong_answer")
        self.user_text = ""
        self.current_interactable = None
        self.state = "sin_bin"
        self.send_telemetry()

    def draw_sin_bin_overlay(self):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((25, 8, 12, 230))
        screen.blit(overlay, (0, 0))

        box_w, box_h = 740, 380
        box_rect = pygame.Rect((WINDOW_WIDTH - box_w) // 2, (WINDOW_HEIGHT - box_h) // 2, box_w, box_h)
        pygame.draw.rect(screen, (45, 14, 20), box_rect, border_radius=12)
        pygame.draw.rect(screen, (235, 70, 70), box_rect, 4, border_radius=12)

        title_surf = self.sin_bin_title_font.render("SECURITY LOCKOUT: SIN-BINNED!", True, (255, 95, 95))
        screen.blit(title_surf, (WINDOW_WIDTH // 2 - title_surf.get_width() // 2, box_rect.top + 30))

        offence_surf = self.sin_bin_body_font.render(
            f"Offence #{self.sin_bin_offences} — {self.sin_bin_reason}", True, (255, 215, 160)
        )
        screen.blit(offence_surf, (WINDOW_WIDTH // 2 - offence_surf.get_width() // 2, box_rect.top + 95))

        info_surf = self.sin_bin_body_font.render(
            "Switching tabs, windows, or using snipping tools\nduring a question is strictly prohibited.",
            True, (220, 220, 220)
        )
        screen.blit(info_surf, (WINDOW_WIDTH // 2 - info_surf.get_width() // 2, box_rect.top + 135))

        regen_surf = self.sin_bin_body_font.render(
            "The security cipher has scrambled and regenerated the question numbers.",
            True, (140, 220, 255)
        )
        screen.blit(regen_surf, (WINDOW_WIDTH // 2 - regen_surf.get_width() // 2, box_rect.top + 170))

        lock_surf = self.sin_bin_body_font.render(
            "Movement and interactions remain locked until the penalty timer expires.",
            True, (190, 195, 205)
        )
        screen.blit(lock_surf, (WINDOW_WIDTH // 2 - lock_surf.get_width() // 2, box_rect.top + 205))

        remaining = max(0, int(math.ceil(self.sin_bin_end_time - time.time())))
        timer_surf = self.sin_bin_timer_font.render(f"{remaining}s", True, (255, 230, 90))
        screen.blit(timer_surf, (WINDOW_WIDTH // 2 - timer_surf.get_width() // 2, box_rect.top + 270))

    def get_menu_rows_per_col(self):
        total_names = max(1, len(self.all_student_names))
        num_cols = min(4, max(1, (total_names + 8) // 9))
        return (total_names + num_cols - 1) // num_cols

    def draw_name_selection(self):
        screen.fill((14, 18, 26))

        title_surf = self.menu_title_font.render("MATHS HEIST: THE VAULT OF LOLLIES", True, (255, 215, 60))
        screen.blit(title_surf, (WINDOW_WIDTH // 2 - title_surf.get_width() // 2, 35))

        class_name = self.class_config.get("class_name", self.class_config.get("class_id", "Default Class"))
        teacher = self.class_config.get("teacher", "Staff")
        class_info = f"Class: {class_name}  |  Teacher: {teacher}"
        class_surf = self.menu_class_font.render(class_info, True, (130, 205, 255))
        screen.blit(class_surf, (WINDOW_WIDTH // 2 - class_surf.get_width() // 2, 88))

        sub_surf = self.menu_sub_font.render("SELECT YOUR STUDENT AGENT IDENTITY", True, (230, 235, 245))
        screen.blit(sub_surf, (WINDOW_WIDTH // 2 - sub_surf.get_width() // 2, 120))

        total_names = len(self.all_student_names)
        num_cols = min(4, max(1, (total_names + 8) // 9))
        rows_per_col = self.get_menu_rows_per_col()

        card_w = 210
        card_h = 36
        gap_x = 20
        gap_y = 10
        grid_w = num_cols * card_w + (num_cols - 1) * gap_x
        start_x = (WINDOW_WIDTH - grid_w) // 2
        start_y = 165

        for idx, name in enumerate(self.all_student_names):
            col = idx // rows_per_col
            row = idx % rows_per_col
            cx = start_x + col * (card_w + gap_x)
            cy = start_y + row * (card_h + gap_y)
            rect = pygame.Rect(cx, cy, card_w, card_h)

            if idx == self.menu_index:
                pygame.draw.rect(screen, (35, 75, 125), rect, border_radius=6)
                pygame.draw.rect(screen, (255, 215, 60), rect, 2, border_radius=6)
                txt_surf = self.menu_name_font.render(f">> {name}", True, (255, 255, 255))
            else:
                pygame.draw.rect(screen, (22, 28, 38), rect, border_radius=6)
                pygame.draw.rect(screen, (50, 62, 80), rect, 1, border_radius=6)
                txt_surf = self.menu_name_font.render(name, True, (190, 200, 220))

            screen.blit(txt_surf, (cx + 12, cy + (card_h - txt_surf.get_height()) // 2))

        hint_surf = self.menu_hint_font.render(
            "Use Arrow Keys [Up/Down/Left/Right] to Navigate  |  Press ENTER or SPACE to Select Agent",
            True, (170, 185, 205)
        )
        screen.blit(hint_surf, (WINDOW_WIDTH // 2 - hint_surf.get_width() // 2, WINDOW_HEIGHT - 45))

    def draw_ui(self):
        self.ui.draw(screen, self.player, self.sound, self.notification, self.notification_timer)

    def draw_door_popup(self):
        self.ui.draw_door_popup(screen, self.door_popup)

    def draw_question_overlay(self):
        self.ui.draw_question_overlay(screen, self.current_interactable, self.user_text)

    def draw_victory_screen(self):
        self.ui.draw_victory_screen(screen, self.player)

    async def run(self):
        running = True
        FocusLostEvent = getattr(pygame, "WINDOWFOCUSLOST", None)

        while running:
            keys = pygame.key.get_pressed()
            curr_level = self.current_level

            # Focus-loss detection while a question is active
            if self.state == "question":
                if sys.platform == "emscripten":
                    if self.check_browser_focus_lost():
                        self.trigger_sin_bin("Browser tab switched or window lost focus!")
                else:
                    if not pygame.key.get_focused():
                        self.trigger_sin_bin("Game window lost focus during an active question!")

            # Check Sin-Bin penalty expiry
            if self.state == "sin_bin" and time.time() >= self.sin_bin_end_time:
                self.state = "playing"
                self.notification = "Sin-bin lockout expired. Focus must remain inside the game window!"
                self.notification_timer = time.time() + 3.0
                self.send_telemetry()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if self.state == "question":
                    if (FocusLostEvent and event.type == FocusLostEvent) or (
                        event.type == pygame.ACTIVEEVENT and getattr(event, "gain", 1) == 0 and getattr(event, "state", 0) & 2
                    ):
                        self.trigger_sin_bin("Game window lost focus during an active question!")
                        continue

                if self.state == "name_selection":
                    if event.type == pygame.KEYDOWN:
                        rows_step = self.get_menu_rows_per_col()
                        if event.key == pygame.K_UP:
                            self.sound.play("key_type")
                            self.menu_index = (self.menu_index - 1) % len(self.all_student_names)
                        elif event.key == pygame.K_DOWN:
                            self.sound.play("key_type")
                            self.menu_index = (self.menu_index + 1) % len(self.all_student_names)
                        elif event.key == pygame.K_LEFT:
                            self.sound.play("key_type")
                            self.menu_index = (self.menu_index - rows_step) % len(self.all_student_names)
                        elif event.key == pygame.K_RIGHT:
                            self.sound.play("key_type")
                            self.menu_index = (self.menu_index + rows_step) % len(self.all_student_names)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.sound.play("prompt_open")
                            self.player_id = self.menu_index
                            self.hero_name = self.all_student_names[self.menu_index]

                            self.npc_names = [
                                n for i, n in enumerate(self.all_student_names) if i != self.menu_index
                            ]
                            random.shuffle(self.npc_names)

                            self.load_map()
                            self.state = "playing"
                            self.send_telemetry()

                elif self.state == "victory":
                    if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                        running = False

                elif self.state == "playing":
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_m:
                            is_muted = self.sound.toggle_mute()
                            self.notification = "Audio Muted" if is_muted else "Audio Enabled"
                            self.notification_timer = time.time() + 1.5
                        elif event.key == pygame.K_SPACE:
                            if curr_level:
                                for item in list(curr_level.interactables):
                                    if self.player.rect.inflate(12, 12).colliderect(item.rect):
                                        if getattr(item, 'is_door', False) and not item.has_required_item(self.player.inventory):
                                            self.show_door_locked_popup(item)
                                            break
                                        elif item.is_interactable():
                                            self.sound.play("prompt_open")
                                            self.reset_focus_latch()
                                            self.state = "question"
                                            self.current_interactable = item
                                            self.user_text = ""
                                            break

                elif self.state == "question":
                    if event.type == pygame.KEYDOWN or auto_open_for_testing:
                        if event.key == pygame.K_RETURN or auto_open_for_testing:
                            q_data = self.current_interactable.question_data
                            if check_answer(self.user_text, q_data.get("accepted_answers", [])) or auto_open_for_testing:
                                pts = q_data.get("points", 100 if getattr(self.current_interactable, 'is_door', False) else 400)
                                self.player.score = getattr(self.player, "score", 0) + pts

                                if getattr(self.current_interactable, 'is_door', False):
                                    pos_x = self.current_interactable.rect.x
                                    pos_y = self.current_interactable.rect.y
                                    door_char = getattr(self.current_interactable, 'door_char', '')
                                    req_item = getattr(self.current_interactable, 'required_item', None)
                                    self.current_interactable.kill()
                                    new_floor = Floor(pos_x, pos_y)
                                    if curr_level:
                                        curr_level.floors.add(new_floor)
                                        curr_level.walkable_tiles.add((pos_x // TILE_SIZE, pos_y // TILE_SIZE))
                                    if req_item:
                                        if req_item in self.player.inventory:
                                            self.player.inventory.remove(req_item)
                                        elif getattr(self.current_interactable, 'required_chest_id', None):
                                            fallback_tag = f"Chest {self.current_interactable.required_chest_id}"
                                            if fallback_tag in self.player.inventory:
                                                self.player.inventory.remove(fallback_tag)
                                        self.notification = f"Door {door_char} unlocked with {req_item} and opened! (+{pts} pts)"
                                    else:
                                        self.notification = f"Door {door_char} unlocked and opened! (+{pts} pts)"
                                    self.notification_timer = time.time() + 3.0

                                    if door_char == 'Z':
                                        self.sound.play("victory")
                                        self.state = "victory"
                                        self.notification = "Vault Door Z breached! You escaped with the bag of lollies!"
                                        self.current_interactable = None
                                    else:
                                        self.sound.play("door_open")
                                        self.state = "playing"
                                        self.current_interactable = None
                                        for npc in self.npcs:
                                            npc.replan_cooldown = 0.0
                                else:
                                    treasure_name = self.current_interactable.name
                                    self.player.inventory.append(treasure_name)
                                    self.current_interactable.kill()
                                    self.sound.play("chest_open")
                                    self.notification = f"Solved chest! {treasure_name} added to inventory! (+{pts} pts)"
                                    self.notification_timer = time.time() + 3.5

                                    self.state = "playing"
                                    self.current_interactable = None
                                    for npc in self.npcs:
                                        npc.replan_cooldown = 0.0

                                self.send_telemetry()
                            else:
                                self.sound.play("wrong_answer")
                                penalty = self.current_interactable.apply_wrong_answer_penalty()
                                self.notification = f"Incorrect answer! Lockout for {penalty} seconds."
                                self.notification_timer = time.time() + 2.5
                                self.state = "playing"
                                self.current_interactable = None
                        elif event.key == pygame.K_BACKSPACE:
                            self.sound.play("key_type")
                            self.user_text = self.user_text[:-1]
                        elif event.key == pygame.K_ESCAPE:
                            self.sound.play("cancel")
                            self.current_interactable.apply_cooldown(1.2)
                            self.state = "playing"
                            self.current_interactable = None
                        else:
                            if event.unicode and event.unicode.isprintable():
                                self.sound.play("key_type")
                                self.user_text += event.unicode

            if self.state in ("playing", "sin_bin") and curr_level and self.player:
                old_score = getattr(self.player, "score", 0)
                for npc in self.npcs:
                    npc.update_npc_multilevel(self)
                if getattr(self.player, "score", 0) != old_score:
                    self.send_telemetry()

            if self.state == "playing" and curr_level and self.player:
                solid_objects = curr_level.get_solid_objects()
                self.player.update(keys, solid_objects)

                if getattr(self.player, 'arrival_stairway_tile', None):
                    arr_c, arr_r = self.player.arrival_stairway_tile
                    arrival_rect = pygame.Rect(arr_c * TILE_SIZE, arr_r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    if not self.player.rect.colliderect(arrival_rect):
                        self.player.arrival_stairway_tile = None

                player_grid = (self.player.rect.centerx // TILE_SIZE, self.player.rect.centery // TILE_SIZE)
                if player_grid in curr_level.stairway_tiles:
                    if getattr(self.player, 'arrival_stairway_tile', None) is None:
                        dest_info = self.stairway_endpoints.get((self.player.level_id, player_grid[0], player_grid[1]))
                        if dest_info:
                            (dest_lvl, dest_c, dest_r), ch = dest_info
                            self.player.level_id = dest_lvl
                            self.player.rect.centerx = dest_c * TILE_SIZE + TILE_SIZE // 2
                            self.player.rect.centery = dest_r * TILE_SIZE + TILE_SIZE // 2
                            self.player.pos_x = float(self.player.rect.x)
                            self.player.pos_y = float(self.player.rect.y)
                            self.player.last_stairway = ch
                            self.player.arrival_stairway_tile = (dest_c, dest_r)
                            self.sound.play("footstep")
                            self.notification = f"Traversed stairs '{ch}' to Level {dest_lvl}!"
                            self.notification_timer = time.time() + 2.0
                            curr_level = self.current_level

                touch_rect = self.player.rect.inflate(12, 12)
                touching_locked_door = False
                for item in list(curr_level.interactables):
                    if touch_rect.colliderect(item.rect):
                        if getattr(item, 'is_door', False) and not item.has_required_item(self.player.inventory):
                            touching_locked_door = True
                            self.show_door_locked_popup(item)
                        elif item.is_interactable():
                            self.sound.play("prompt_open")
                            self.reset_focus_latch()
                            self.state = "question"
                            self.current_interactable = item
                            self.user_text = ""
                            break

                if not touching_locked_door:
                    self.last_locked_door_char = None

            if self.player:
                self.camera_offset[0] = self.player.rect.centerx - WINDOW_WIDTH // 2
                self.camera_offset[1] = self.player.rect.centery - WINDOW_HEIGHT // 2

            screen.fill((15, 18, 24))

            if self.state == "name_selection":
                self.draw_name_selection()
            elif curr_level:
                cam_x, cam_y = self.camera_offset
                cull_rect = pygame.Rect(
                    cam_x - TILE_SIZE, cam_y - TILE_SIZE,
                    WINDOW_WIDTH + 2 * TILE_SIZE, WINDOW_HEIGHT + 2 * TILE_SIZE
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
                    if npc.level_id == self.player.level_id and cull_rect.colliderect(npc.rect):
                        screen.blit(npc.image, (npc.rect.x - cam_x, npc.rect.y - cam_y))
                        npc.draw_name(screen, self.camera_offset, self.name_font)

                if self.player:
                    screen.blit(self.player.image, (self.player.rect.x - cam_x, self.player.rect.y - cam_y))
                    self.player.draw_name(screen, self.camera_offset, self.name_font)

                for item in curr_level.interactables:
                    if cull_rect.colliderect(item.rect):
                        item.draw_lockout_icon(screen, self.camera_offset)
                        if getattr(item, 'is_door', False) and hasattr(item, 'draw_requirement_badge'):
                            has_item = item.has_required_item(self.player.inventory) if self.player else False
                            item.draw_requirement_badge(
                                screen, self.camera_offset, has_item,
                                self.player.rect.center if self.player else None
                            )

                if self.player:
                    for stair in curr_level.stairways:
                        dist = math.hypot(
                            stair.rect.centerx - self.player.rect.centerx,
                            stair.rect.centery - self.player.rect.centery
                        )
                        if dist < 140:
                            stair.draw_badge(screen, self.camera_offset, stair.dest_level)

                self.draw_ui()
                self.draw_door_popup()

            if self.state == "question":
                self.draw_question_overlay()
            elif self.state == "sin_bin":
                self.draw_sin_bin_overlay()
            elif self.state == "victory":
                self.draw_victory_screen()

            pygame.display.flip()
            clock.tick(FPS)
            await asyncio.sleep(0)

        pygame.quit()
        sys.exit()


async def main():
    game = Game()
    await game.run()


if __name__ == "__main__":
    asyncio.run(main())