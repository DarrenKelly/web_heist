import pygame
import time
import math
import os

TILE_SIZE = 64
LOCKOUT_TIERS = [5, 10, 30, 60]
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
COLOUR_BLACK = (0, 0, 0)
COLOUR_WHITE = (255, 255, 255)

_lockout_font = None
_badge_font = None
_DOOR_IMAGE_CACHE = {}

def get_lockout_font():
    global _lockout_font
    if _lockout_font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _lockout_font = pygame.font.SysFont(None, 36)
    return _lockout_font

def get_badge_font():
    global _badge_font
    if _badge_font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _badge_font = pygame.font.SysFont(None, 18, bold=True)
    return _badge_font

def get_door_custom_image(door_char):
    if door_char in _DOOR_IMAGE_CACHE:
        return _DOOR_IMAGE_CACHE[door_char]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "img", f"DOOR_{door_char}.png"),
        os.path.join(base_dir, "img", f"DOOR_{str(door_char).lower()}.png"),
        os.path.join(base_dir, "img", f"door_{str(door_char).lower()}.png"),
        os.path.join(base_dir, "img", f"door_{door_char}.png"),
        os.path.join(base_dir, f"DOOR_{door_char}.png"),
        os.path.join(base_dir, f"door_{door_char}.png"),
        os.path.join(base_dir, "img", f"DOOR_{door_char}.jpg"),
        os.path.join(base_dir, "img", f"DOOR_{str(door_char).lower()}.jpg"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                raw = pygame.image.load(p)
                if pygame.display.get_surface():
                    if raw.get_alpha():
                        raw = raw.convert_alpha()
                    else:
                        raw = raw.convert()
                scaled = pygame.transform.smoothscale(raw, (TILE_SIZE, TILE_SIZE))
                _DOOR_IMAGE_CACHE[door_char] = scaled
                return scaled
            except Exception as e:
                print(f"Error loading custom door image {p}: {e}")

    _DOOR_IMAGE_CACHE[door_char] = None
    return None

class Door(pygame.sprite.Sprite):
    def __init__(self, x, y, door_char, question_data, required_item=None, required_chest_id=None):
        super().__init__()
        self.is_door = True
        self.door_char = door_char
        self.question_data = question_data
        self.required_item = required_item
        self.required_chest_id = required_chest_id
        self.is_locked = True
        self.lockout_end_time = 0
        self.wrong_attempts = 0
        self._badge_ready_surf = None
        self._badge_need_surf = None
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.rect = self.image.get_rect(topleft=(x, y))
        self.render_door()

    def render_door(self):
        custom_img = get_door_custom_image(self.door_char)
        if custom_img is not None:
            self.image = custom_img.copy()
            return

        self.image.fill((20, 22, 28))
        if self.door_char in ('V', 'Z'):
            base_color = (205, 155, 29)
            border_color = (255, 215, 0)
            text_color = COLOUR_BLACK
        else:
            base_color = (180, 50, 50)
            border_color = (230, 90, 90)
            text_color = COLOUR_WHITE
        
        pygame.draw.rect(self.image, border_color, (3, 3, TILE_SIZE - 6, TILE_SIZE - 6), 3)
        pygame.draw.rect(self.image, base_color, (7, 7, TILE_SIZE - 14, TILE_SIZE - 14))
        for rx, ry in [(12, 12), (TILE_SIZE - 12, 12), (12, TILE_SIZE - 12), (TILE_SIZE - 12, TILE_SIZE - 12)]:
            pygame.draw.circle(self.image, border_color, (rx, ry), 2)
        
        if not pygame.font.get_init():
            pygame.font.init()
        char_font = pygame.font.SysFont(None, 34, bold=True)
        txt = char_font.render(self.door_char, True, text_color)

        if self.required_item:
            # Shift door letter slightly up to accommodate key tag
            self.image.blit(txt, (TILE_SIZE // 2 - txt.get_width() // 2, TILE_SIZE // 2 - txt.get_height() // 2 - 8))
            req_font = pygame.font.SysFont(None, 18, bold=True)
            key_tag = req_font.render(f"Key #{self.required_chest_id}", True, (255, 225, 120))
            tag_bg = pygame.Surface((key_tag.get_width() + 6, key_tag.get_height() + 2))
            tag_bg.fill((30, 20, 20))
            self.image.blit(tag_bg, (TILE_SIZE // 2 - tag_bg.get_width() // 2, TILE_SIZE - 20))
            self.image.blit(key_tag, (TILE_SIZE // 2 - key_tag.get_width() // 2, TILE_SIZE - 19))
        else:
            self.image.blit(txt, (TILE_SIZE // 2 - txt.get_width() // 2, TILE_SIZE // 2 - txt.get_height() // 2))

    def has_required_item(self, inventory):
        if not self.required_item:
            return True
        return (self.required_item in inventory or 
                (self.required_chest_id is not None and f"Chest {self.required_chest_id}" in inventory))

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

    def _get_badge_surf(self, has_item):
        if has_item:
            if self._badge_ready_surf is None:
                font = get_badge_font()
                txt = font.render(f"READY: {self.required_item}", True, (130, 255, 160))
                bw, bh = txt.get_width() + 10, txt.get_height() + 4
                surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
                surf.fill((15, 38, 22, 220))
                pygame.draw.rect(surf, (55, 185, 95), (0, 0, bw, bh), 1, border_radius=4)
                surf.blit(txt, (5, 2))
                self._badge_ready_surf = surf
            return self._badge_ready_surf
        else:
            if self._badge_need_surf is None:
                font = get_badge_font()
                txt = font.render(f"NEED: {self.required_item}", True, (255, 210, 110))
                bw, bh = txt.get_width() + 10, txt.get_height() + 4
                surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
                surf.fill((38, 16, 16, 220))
                pygame.draw.rect(surf, (210, 65, 65), (0, 0, bw, bh), 1, border_radius=4)
                surf.blit(txt, (5, 2))
                self._badge_need_surf = surf
            return self._badge_need_surf

    def draw_requirement_badge(self, surface, camera_offset, has_item, player_pos=None):
        if not self.required_item or time.time() < self.lockout_end_time:
            return

        if player_pos:
            dist = math.hypot(self.rect.centerx - player_pos[0], self.rect.centery - player_pos[1])
            if dist > 220:
                return

        draw_x = self.rect.centerx - camera_offset[0]
        draw_y = self.rect.top - camera_offset[1] - 18

        if not (-60 <= draw_x <= WINDOW_WIDTH + 60 and -60 <= draw_y <= WINDOW_HEIGHT + 60):
            return

        badge_surf = self._get_badge_surf(has_item)
        surface.blit(badge_surf, (draw_x - badge_surf.get_width() // 2, draw_y))
