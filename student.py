"""
Student Base Sprite and HeroStudent Character
"""

import pygame
import time
import math
import os
from config import COLOUR_WHITE, COLOUR_BLACK


class Student(pygame.sprite.Sprite):
    # Change from a single variable to a dictionary to cache multiple sprite sheets
    _animation_caches = {}

    def __init__(self, x, y, name="Student", sprite_file="hero.png"):
        super().__init__()
        self.name = name
        self.target_w = 40
        self.target_h = 40
        self.last_move_time = time.time()
        self._cached_name_surf = None
        self._cached_name_font = None

        # Check if this specific sprite sheet has been loaded and scaled yet
        if sprite_file not in Student._animation_caches:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            sheet_path = os.path.join(base_dir, "img", sprite_file)
            if not os.path.exists(sheet_path):
                sheet_path = f"img/{sprite_file}"
            
            sheet = pygame.image.load(sheet_path).convert_alpha()
            
            target_sheet_width = self.target_w * 4
            target_sheet_height = self.target_h * 8
            scaled_sheet = pygame.transform.smoothscale(sheet, (target_sheet_width, target_sheet_height))
            
            Student._animation_caches[sprite_file] = {
                'N': self._extract_frames(scaled_sheet, 0, self.target_w, self.target_h),
                'W': self._extract_frames(scaled_sheet, 3, self.target_w, self.target_h),
                'S': self._extract_frames(scaled_sheet, 1, self.target_w, self.target_h),
                'E': self._extract_frames(scaled_sheet, 2, self.target_w, self.target_h),
                'NE': self._extract_frames(scaled_sheet, 4, self.target_w, self.target_h),
                'NW': self._extract_frames(scaled_sheet, 5, self.target_w, self.target_h),
                'SW': self._extract_frames(scaled_sheet, 6, self.target_w, self.target_h),
                'SE': self._extract_frames(scaled_sheet, 7, self.target_w, self.target_h)
            }

        # Point this student's animations to the correct cached dictionary
        self.animations = Student._animation_caches[sprite_file]
        self.direction = 'S'
        self.state = 'idle'
        self.speed = 5
        self.idle_start_time = time.time()

        self.frame_index = 1
        self.animation_speed = 150
        self.last_update = pygame.time.get_ticks()

        self.image = self.animations[self.direction][self.frame_index]
        self.rect = self.image.get_rect(topleft=(x, y))
        
        self.pos_x = float(self.rect.x)
        self.pos_y = float(self.rect.y)

    def _extract_frames(self, sheet, row, frame_w, frame_h):
        frames = []
        for col in range(4):
            # Create a natively transparent surface for the frame
            frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
            frame.blit(sheet, (0, 0), (col * frame_w, row * frame_h, frame_w, frame_h))
            frames.append(frame)
        return frames

    def update(self, keys, solid_objects):
        move_x = 0
        move_y = 0
        if keys[pygame.K_LEFT]:  move_x -= 1
        if keys[pygame.K_RIGHT]: move_x += 1
        if keys[pygame.K_UP]:    move_y -= 1
        if keys[pygame.K_DOWN]:  move_y += 1
        self.move_and_animate(move_x, move_y, solid_objects)

    def move_and_animate(self, move_x, move_y, solid_objects):
        if move_x != 0 or move_y != 0:
            if self.state != 'moving':
                self.state = 'moving'
            self.idle_start_time = time.time()

            length = math.hypot(move_x, move_y)
            dx = (move_x / length) * self.speed
            dy = (move_y / length) * self.speed

            if abs(move_x) >= abs(move_y):
                self.direction = 'W' if move_x < 0 else 'E'
            else:
                self.direction = 'N' if move_y < 0 else 'S'
        else:
            self.state = 'idle'
            dx, dy = 0.0, 0.0

        # Move and collide X
        self.pos_x += dx
        self.rect.x = int(self.pos_x)
        px, py = self.rect.x, self.rect.y
        nearby_walls = [w for w in solid_objects if abs(w.rect.x - px) < 96 and abs(w.rect.y - py) < 96]
        for wall in nearby_walls:
            if self.rect.colliderect(wall.rect):
                if dx > 0: self.rect.right = wall.rect.left
                if dx < 0: self.rect.left = wall.rect.right
                self.pos_x = float(self.rect.x)

        # Move and collide Y
        self.pos_y += dy
        self.rect.y = int(self.pos_y)
        for wall in nearby_walls:
            if self.rect.colliderect(wall.rect):
                if dy > 0: self.rect.bottom = wall.rect.top
                if dy < 0: self.rect.top = wall.rect.bottom
                self.pos_y = float(self.rect.y)

        # Update sprite frame
        now = pygame.time.get_ticks()
        if self.state == 'moving':
            if now - self.last_update > self.animation_speed:
                self.last_update = now
                self.frame_index = (self.frame_index + 1) % 4
                self.image = self.animations[self.direction][self.frame_index]
        else:
            self.image = self.animations[self.direction][1]

    def should_show_name(self):
        return True

    def draw_name(self, surface, camera_offset, label_font):
        if not self.should_show_name() or not self.name:
            return
        if self._cached_name_surf is None or self._cached_name_font is not label_font:
            self._cached_name_font = label_font
            txt = label_font.render(self.name, True, COLOUR_WHITE)
            w, h = txt.get_width() + 8, txt.get_height() + 4
            self._cached_name_surf = pygame.Surface((w, h), pygame.SRCALPHA)
            self._cached_name_surf.fill((15, 18, 26, 220))
            pygame.draw.rect(self._cached_name_surf, (50, 60, 80), (0, 0, w, h), 1, border_radius=4)
            self._cached_name_surf.blit(txt, (4, 2))

        bg_rect = self._cached_name_surf.get_rect(
            center=(self.rect.centerx - camera_offset[0], self.rect.top - camera_offset[1] - 10)
        )
        surface.blit(self._cached_name_surf, bg_rect)


class HeroStudent(Student):
    def __init__(self, x, y, name="John", level_id=0):
        # Explicitly ask for the hero sprite sheet
        super().__init__(x, y, name, sprite_file="hero.png")
        self.idle_name_delay = 3.0
        self.level_id = level_id
        self.last_stairway = None
        self.stairway_cooldown = 0.0
        self.arrival_stairway_tile = None
        self.inventory = []
        self.score = 0

    def should_show_name(self):
        return (time.time() - self.last_move_time) >= self.idle_name_delay

    def update(self, keys, solid_objects):
        old_x, old_y = self.rect.x, self.rect.y
        super().update(keys, solid_objects)
        if self.rect.x != old_x or self.rect.y != old_y:
            self.last_move_time = time.time()