"""
Shared Base Class for Interactive Map Objects (Doors & Chests)
"""

import time
import pygame
from config import LOCKOUT_TIERS

_lockout_font = None


def get_lockout_font():
    global _lockout_font
    if _lockout_font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _lockout_font = pygame.font.SysFont(None, 36)
    return _lockout_font


class Interactable(pygame.sprite.Sprite):
    is_door = False

    def __init__(self, question_data=None):
        super().__init__()
        self.question_data = question_data
        self.is_locked = True
        self.lockout_end_time = 0
        self.wrong_attempts = 0

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
