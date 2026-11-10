import pygame
import time
import os

TILE_SIZE = 64
LOCKOUT_TIERS = [5, 10, 30, 60]

_CHEST_IMAGES = None
_lockout_font = None

def get_lockout_font():
    global _lockout_font
    if _lockout_font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _lockout_font = pygame.font.SysFont(None, 36)
    return _lockout_font

def load_chest_sheet(filename="img/TreasureChests.png"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        filename,
        "img/TreasureChests.png",
        "TreasureChests.png",
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "img", "TreasureChests.png"),
    ]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if not path:
        print(f"CRITICAL [chest.py]: TreasureChests.png not found! Checked: {candidates}")
        print(f"CRITICAL [chest.py]: Current working dir: {os.getcwd()}, img/ contents: {os.listdir('img') if os.path.exists('img') else 'NO IMG DIR'}")
        return []

    try:
        raw_sheet = pygame.image.load(path)
        w, h = raw_sheet.get_size()
        print(f"SUCCESS [chest.py]: Loaded {path} ({w}x{h})")
        
        # Blit onto a clean 32-bit SRCALPHA surface to guarantee scale/subsurface compatibility
        sheet = pygame.Surface((w, h), pygame.SRCALPHA)
        sheet.blit(raw_sheet, (0, 0))
        if raw_sheet.get_alpha() is None:
            # Fallback if GIMP exported a solid black background without alpha
            sheet.set_colorkey((0, 0, 0))

        slices = []
        for row in range(3):
            for col in range(3):
                x1, x2 = int(col * w / 3), int((col + 1) * w / 3)
                y1, y2 = int(row * h / 3), int((row + 1) * h / 3)
                
                cell_surf = pygame.Surface((x2 - x1, y2 - y1), pygame.SRCALPHA)
                cell_surf.blit(sheet, (0, 0), (x1, y1, x2 - x1, y2 - y1))
                scaled = pygame.transform.scale(cell_surf, (48, 48))
                slices.append(scaled)
        return slices
    except Exception as e:
        print(f"CRITICAL [chest.py]: Error slicing chest sheet {path}: {e}")
        return []

def get_chest_images():
    global _CHEST_IMAGES
    if _CHEST_IMAGES is None:
        _CHEST_IMAGES = load_chest_sheet("img/TreasureChests.png")
    return _CHEST_IMAGES


_KEY_IMAGES = None
_KEY_ICONS_BY_NAME = {}

def load_key_sheet(filename="img/Keys.png", target_size=(24, 24)):
    """
    Loads Keys.png and slices it into a 3x3 grid of key images,
    corresponding to the 3x3 grid of chests in TreasureChests.png.
    Each key slice is cropped to its visible bounding box and scaled.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        filename,
        "img/Keys.png",
        "Keys.png",
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "img", "Keys.png"),
        os.path.join(base_dir, "Keys.png"),
    ]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if not path:
        return []

    try:
        sheet = pygame.image.load(path)
        try:
            sheet = sheet.convert_alpha()
        except pygame.error:
            print(f"Warning: Alpha conversion failed - {e}")
        w, h = sheet.get_size()
        slices = []
        for row in range(3):
            for col in range(3):
                x1 = int(col * w / 3)
                x2 = int((col + 1) * w / 3)
                y1 = int(row * h / 3)
                y2 = int((row + 1) * h / 3)
                cell_surf = sheet.subsurface((x1, y1, x2 - x1, y2 - y1))
                bbox = cell_surf.get_bounding_rect()
                sub = cell_surf.subsurface(bbox) if (bbox.width > 0 and bbox.height > 0) else cell_surf
                
                sw, sh = sub.get_size()
                scale = min(target_size[0] / sw, target_size[1] / sh)
                nw = max(1, int(sw * scale))
                nh = max(1, int(sh * scale))
                scaled = pygame.transform.smoothscale(sub, (nw, nh))

                icon_surf = pygame.Surface(target_size, pygame.SRCALPHA)
                icon_surf.blit(scaled, ((target_size[0] - nw) // 2, (target_size[1] - nh) // 2))
                slices.append(icon_surf)
        return slices
    except Exception as e:
        print(f"Error slicing key sheet {path}: {e}")
        return []

def load_single_key_icon(filename="img/key6.png", target_size=(24, 24)):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        filename,
        "img/key6.png",
        "key6.png",
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "img", "key6.png"),
        os.path.join(base_dir, "key6.png"),
    ]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if not path:
        return None

    try:
        surf = pygame.image.load(path)
        try:
            surf = surf.convert_alpha()
        except pygame.error:
            print(f"Warning: Alpha conversion failed - {e}")
        bbox = surf.get_bounding_rect()
        sub = surf.subsurface(bbox) if (bbox.width > 0 and bbox.height > 0) else surf
        sw, sh = sub.get_size()
        scale = min(target_size[0] / sw, target_size[1] / sh)
        nw = max(1, int(sw * scale))
        nh = max(1, int(sh * scale))
        scaled = pygame.transform.smoothscale(sub, (nw, nh))

        icon_surf = pygame.Surface(target_size, pygame.SRCALPHA)
        icon_surf.blit(scaled, ((target_size[0] - nw) // 2, (target_size[1] - nh) // 2))
        return icon_surf
    except Exception as e:
        print(f"Error loading single key icon {path}: {e}")
        return None

def get_key_images(target_size=(24, 24)):
    global _KEY_IMAGES
    if _KEY_IMAGES is None:
        _KEY_IMAGES = load_key_sheet("img/Keys.png", target_size)
    return _KEY_IMAGES

def get_key_icon_for_item(item_name, target_size=(24, 24)):
    """
    Returns the key Surface icon corresponding to the given item name or chest ID.
    """
    global _KEY_ICONS_BY_NAME
    if not _KEY_ICONS_BY_NAME:
        key_slices = get_key_images(target_size)
        key6_icon = load_single_key_icon("img/key6.png", target_size)

        for obj_id, defn in OBJECT_DEFINITIONS.items():
            icon = None
            if defn.get("key_image"):
                icon = load_single_key_icon(defn["key_image"], target_size)
            elif defn.get("key_slice_index") is not None and key_slices:
                idx = defn["key_slice_index"]
                if 0 <= idx < len(key_slices):
                    icon = key_slices[idx]

            if icon is None and defn.get("image") == "img/treasure6.png":
                icon = key6_icon

            if icon:
                _KEY_ICONS_BY_NAME[defn["name"]] = icon
                _KEY_ICONS_BY_NAME[defn["name"].lower()] = icon
                _KEY_ICONS_BY_NAME[f"Chest {obj_id}"] = icon
                _KEY_ICONS_BY_NAME[f"Chest {obj_id}".lower()] = icon
                _KEY_ICONS_BY_NAME[str(obj_id)] = icon

    if not item_name:
        return None
    name_str = str(item_name).strip()
    return _KEY_ICONS_BY_NAME.get(name_str) or _KEY_ICONS_BY_NAME.get(name_str.lower())

# Objects: 0-9 (using 3x3 grid slices from TreasureChests.png / Keys.png, with special-case overrides)
OBJECT_DEFINITIONS = {
    '0': {"name": "Bag of Jelly Snakes", "image": "img/treasure6.png", "key_image": "img/key6.png", "color": (255, 215, 0)},
    '1': {"name": "Gold Key", "slice_index": 0, "key_slice_index": 0, "color": (220, 20, 60)},
    '2': {"name": "Emerald Key", "slice_index": 1, "key_slice_index": 1, "color": (46, 204, 113)},
    '3': {"name": "Saphire Key", "slice_index": 2, "key_slice_index": 2, "color": (52, 152, 219)},
    '4': {"name": "Lock picks", "slice_index": 3, "key_slice_index": 3, "color": (155, 89, 182)},
    '5': {"name": "Ruby Key", "slice_index": 4, "key_slice_index": 4, "color": (241, 196, 15)},
    '6': {"name": "Battering Ram", "slice_index": 5, "key_slice_index": 5, "color": (230, 126, 34)},
    '7': {"name": "Skeleton Key", "slice_index": 6, "key_slice_index": 6, "color": (231, 76, 60)},
    '8': {"name": "Key Card", "slice_index": 7, "key_slice_index": 7, "color": (26, 188, 156)},
    '9': {"name": "Silver Key", "slice_index": 8, "key_slice_index": 8, "color": (255, 105, 180)},
}

class Chest(pygame.sprite.Sprite):
    def __init__(self, x, y, obj_char="0", question_data=None, chest_char=None):
        super().__init__()
        self.is_door = False
        actual_char = obj_char if (obj_char is not None and str(obj_char) != "None") else chest_char
        if actual_char is None or str(actual_char) == "None":
            actual_char = "0"
        self.obj_char = str(actual_char)
        self.chest_id = self.obj_char
        self.question_data = question_data
        self.is_locked = True
        self.lockout_end_time = 0
        self.wrong_attempts = 0
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        
        info = OBJECT_DEFINITIONS.get(self.obj_char, {"name": f"Treasure #{self.obj_char}", "color": (255, 215, 0)})
        self.name = info["name"]
        
        # Check for image override (e.g. treasure6.png for Iron Key / Bag of Jelly Snakes)
        loaded = None
        if info.get("image"):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            p = os.path.join(base_dir, info["image"])
            if not os.path.exists(p):
                p = info["image"]
            if os.path.exists(p):
                try:
                    loaded = pygame.image.load(p)
                    try:
                        loaded = loaded.convert_alpha()
                    except pygame.error:
                        print(f"Warning: Alpha conversion failed - {e}")
                    loaded = pygame.transform.smoothscale(loaded, (48, 48))
                except Exception as e:
                    print(f"Error loading chest image {p}: {e}")
                    loaded = None

        chest_images = get_chest_images()
        if loaded is None:
            # Pick sliced chest image from the 3x3 grid
            slice_idx = info.get("slice_index")
            if slice_idx is None:
                try:
                    slice_idx = int(self.obj_char) % len(chest_images) if chest_images else None
                except (ValueError, TypeError):
                    slice_idx = 0

            if chest_images and slice_idx is not None and 0 <= slice_idx < len(chest_images):
                loaded = chest_images[slice_idx]

        center = (TILE_SIZE // 2, TILE_SIZE // 2)
        color = info.get("color", (255, 215, 0))
        if loaded:
            pygame.draw.circle(self.image, (*color[:3], 80), center, 24)
            img_x = (TILE_SIZE - loaded.get_width()) // 2
            img_y = (TILE_SIZE - loaded.get_height()) // 2
            self.image.blit(loaded, (img_x, img_y))
            if not pygame.font.get_init():
                pygame.font.init()
            badge_font = pygame.font.SysFont(None, 16, bold=True)
            badge_surf = badge_font.render(f"#{self.obj_char}", True, (255, 240, 200))
            bg_w = badge_surf.get_width() + 4
            bg_h = badge_surf.get_height() + 2
            badge_bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
            badge_bg.fill((15, 20, 30, 210))
            pygame.draw.rect(badge_bg, (*color[:3], 200), (0, 0, bg_w, bg_h), 1, border_radius=3)
            self.image.blit(badge_bg, (TILE_SIZE - bg_w - 4, TILE_SIZE - bg_h - 4))
            self.image.blit(badge_surf, (TILE_SIZE - bg_w - 2, TILE_SIZE - bg_h - 3))
        else:
            pygame.draw.rect(self.image, (139, 69, 19), (12, 18, 40, 30), border_radius=4)
            pygame.draw.rect(self.image, (255, 215, 0), (12, 18, 40, 30), 2, border_radius=4)
            pygame.draw.rect(self.image, (255, 215, 0), (12, 28, 40, 5))
            pygame.draw.circle(self.image, (255, 255, 255), center, 4)
            if not pygame.font.get_init():
                pygame.font.init()
            obj_font = pygame.font.SysFont(None, 20, bold=True)
            txt = obj_font.render(self.obj_char, True, (255, 255, 200))
            self.image.blit(txt, (center[0] - txt.get_width() // 2, 42))

    def is_interactable(self):
        return self.is_locked and time.time() > self.lockout_end_time

    def apply_wrong_answer_penalty(self):
        penalty = LOCKOUT_TIERS[min(self.wrong_attempts, len(LOCKOUT_TIERS) - 1)]
        self.wrong_attempts += 1
        self.lockout_end_time = time.time() + penalty
        return penalty

    def apply_cooldown(self, seconds=1.2):
        self.lockout_end_time = time.time() + seconds

    def draw_lockout_icon(self, surface, camera_offset):
        if time.time() < self.lockout_end_time:
            remaining = int(self.lockout_end_time - time.time()) + 1
            if remaining > 1:
                text = get_lockout_font().render(str(remaining), True, (255, 100, 100))
                draw_x = self.rect.centerx - camera_offset[0] - text.get_width() // 2
                draw_y = self.rect.top - camera_offset[1] - 30
                surface.blit(text, (draw_x, draw_y))

def __getattr__(name):
    if name == "CHEST_IMAGES":
        return get_chest_images()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
