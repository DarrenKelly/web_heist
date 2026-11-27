"""
Maths Heist: The Vault of Lollies
Main Entry Point and Game State Coordinator
"""

import asyncio
import random
import sys
import time
import pygame

from audio import SoundManager
from browser_bridge import (
    check_browser_focus_lost,
    detect_class_id,
    init_focus_tracker,
    reset_focus_latch,
    send_telemetry,
)
from config import (
    FPS,
    SIN_BIN_TIERS,
    TILE_SIZE,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    get_class_config,
    load_students_json,
    log_diag,
)
from door import Door
from environment import World
from questions import check_answer, load_questions_for_class, parameterise_question
from ui import UIManager

auto_open_for_testing = False


class Game:
    def __init__(self, class_id="DEFAULT"):
        self.class_id = class_id

        # Pre-initialise mixer for crisp low-latency 1990s retro audio
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        pygame.mixer.init()

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Maths Heist: The MCE Lolly Vault")
        self.clock = pygame.time.Clock()

        self.class_config = get_class_config(self.class_id)
        print(f"[INIT] Active Class Config: {self.class_config}")

        self.sound = SoundManager()
        self.ui = UIManager()
        self.world = World()
        self.questions = load_questions_for_class(self.class_config)
        self.all_student_names = load_students_json(
            self.class_config.get("students_file", "students.json")
        )

        self.camera_offset = [0, 0]
        self.player_id = 0
        self.hero_name = ""
        self.npc_names = []

        self.notification = ""
        self.notification_timer = 0.0
        self.door_popup = None
        self.last_locked_door_char = None

        # Sin-Bin / Focus-Loss Anti-AI State
        self.sin_bin_offences = 0
        self.sin_bin_end_time = 0.0
        self.sin_bin_duration = 0
        self.sin_bin_reason = ""

        # State Machine
        self.state = "name_selection"
        self.current_interactable = None
        self.user_text = ""
        self.menu_index = 0

        init_focus_tracker()

    def set_notification(self, message, duration=3.0):
        self.notification = message
        self.notification_timer = time.time() + duration

    def _send_telemetry(self):
        send_telemetry(self.class_id, self.player_id, self.world.player, self.state)

    def _show_door_locked_popup(self, door_item):
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
            "expires_at": time.time() + 2.5,
        }

    def _try_interact_with_item(self, item):
        """
        Attempts to open a question prompt for an adjacent Door or Chest.
        Returns ("locked" | "opened" | "none").
        """
        player = self.world.player
        if isinstance(item, Door) and not item.has_required_item(player.inventory):
            self._show_door_locked_popup(item)
            return "locked"
        if item.is_interactable():
            self.sound.play("prompt_open")
            reset_focus_latch()
            self.state = "question"
            self.current_interactable = item
            self.user_text = ""
            return "opened"
        return "none"

    def _trigger_sin_bin(self, reason="Focus lost while viewing a question!"):
        tier_idx = min(self.sin_bin_offences, len(SIN_BIN_TIERS) - 1)
        penalty = SIN_BIN_TIERS[tier_idx]
        self.sin_bin_offences += 1
        self.sin_bin_duration = penalty
        self.sin_bin_end_time = time.time() + penalty
        self.sin_bin_reason = reason

        if self.current_interactable and getattr(self.current_interactable, "question_data", None):
            self.current_interactable.question_data = parameterise_question(
                self.current_interactable.question_data,
                force_regenerate=True,
            )

        self.sound.play("wrong_answer")
        self.user_text = ""
        self.current_interactable = None
        self.state = "sin_bin"
        self._send_telemetry()

    def _handle_name_selection_key(self, key):
        rows_step = self.ui.get_menu_rows_per_col(self.all_student_names)
        count = len(self.all_student_names)
        if key == pygame.K_UP:
            self.sound.play("key_type")
            self.menu_index = (self.menu_index - 1) % count
        elif key == pygame.K_DOWN:
            self.sound.play("key_type")
            self.menu_index = (self.menu_index + 1) % count
        elif key == pygame.K_LEFT:
            self.sound.play("key_type")
            self.menu_index = (self.menu_index - rows_step) % count
        elif key == pygame.K_RIGHT:
            self.sound.play("key_type")
            self.menu_index = (self.menu_index + rows_step) % count
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.sound.play("prompt_open")
            self.player_id = self.menu_index
            self.hero_name = self.all_student_names[self.menu_index]
            self.npc_names = [
                n for i, n in enumerate(self.all_student_names) if i != self.menu_index
            ]
            random.shuffle(self.npc_names)

            audit_warning = self.world.load(self.hero_name, self.npc_names, self.questions)
            if audit_warning:
                self.set_notification(audit_warning, duration=4.0)
            self.state = "playing"
            self._send_telemetry()

    def _handle_playing_key(self, key):
        if key == pygame.K_m:
            is_muted = self.sound.toggle_mute()
            self.set_notification("Audio Muted" if is_muted else "Audio Enabled", duration=1.5)
        elif key == pygame.K_SPACE:
            curr_level = self.world.current_level
            player = self.world.player
            if curr_level and player:
                touch_rect = player.rect.inflate(12, 12)
                for item in list(curr_level.interactables):
                    if touch_rect.colliderect(item.rect):
                        if self._try_interact_with_item(item) != "none":
                            break

    def _resolve_correct_answer(self, q_data):
        item = self.current_interactable
        player = self.world.player
        curr_level = self.world.current_level
        is_door = isinstance(item, Door)

        pts = q_data.get("points", 100 if is_door else 400)
        player.score = getattr(player, "score", 0) + pts

        if is_door:
            door_char = item.door_char
            req_item = item.required_item
            self.world.open_door(item, curr_level)

            if req_item:
                if req_item in player.inventory:
                    player.inventory.remove(req_item)
                elif item.required_chest_id:
                    fallback_tag = f"Chest {item.required_chest_id}"
                    if fallback_tag in player.inventory:
                        player.inventory.remove(fallback_tag)
                self.set_notification(
                    f"Door {door_char} unlocked with {req_item} and opened! (+{pts} pts)", 3.0
                )
            else:
                self.set_notification(f"Door {door_char} unlocked and opened! (+{pts} pts)", 3.0)

            if door_char == "Z":
                self.sound.play("victory")
                self.state = "victory"
                self.notification = "Vault Door Z breached! You escaped with the bag of lollies!"
            else:
                self.sound.play("door_open")
                self.state = "playing"
        else:
            treasure_name = item.name
            player.inventory.append(treasure_name)
            item.kill()
            self.sound.play("chest_open")
            self.set_notification(
                f"Solved chest! {treasure_name} added to inventory! (+{pts} pts)", 3.5
            )
            self.state = "playing"
            self.world.reset_npc_replan_cooldowns()

        self.current_interactable = None
        self._send_telemetry()

    def _handle_question_key(self, event):
        if event.key == pygame.K_RETURN or auto_open_for_testing:
            q_data = self.current_interactable.question_data
            if check_answer(self.user_text, q_data.get("accepted_answers", [])) or auto_open_for_testing:
                self._resolve_correct_answer(q_data)
            else:
                self.sound.play("wrong_answer")
                penalty = self.current_interactable.apply_wrong_answer_penalty()
                self.set_notification(f"Incorrect answer! Lockout for {penalty} seconds.", 2.5)
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
        elif event.unicode and event.unicode.isprintable():
            self.sound.play("key_type")
            self.user_text += event.unicode

    def _check_focus_and_sin_bin(self):
        if self.state == "question":
            if sys.platform == "emscripten":
                if check_browser_focus_lost():
                    self._trigger_sin_bin("Browser tab switched or window lost focus!")
            elif not pygame.key.get_focused():
                self._trigger_sin_bin("Game window lost focus during an active question!")

        if self.state == "sin_bin" and time.time() >= self.sin_bin_end_time:
            self.state = "playing"
            self.set_notification(
                "Sin-bin lockout expired. Focus must remain inside the game window!", 3.0
            )
            self._send_telemetry()

    def _update_npcs(self):
        player = self.world.player
        if not (self.state in ("playing", "sin_bin") and self.world.current_level and player):
            return
        score_changed = False
        for npc in self.world.npcs:
            if npc.update_npc_multilevel(self.world):
                player.score += 100
                self.set_notification(f"{npc.name} reached the school gate! (+100 pts)", 3.0)
                score_changed = True
        if score_changed:
            self._send_telemetry()

    def _update_playing(self, keys):
        curr_level = self.world.current_level
        player = self.world.player
        if not (self.state == "playing" and curr_level and player):
            return

        player.update(keys, curr_level.get_solid_objects())
        player.clear_arrival_stairway_if_left()

        player_grid = (player.rect.centerx // TILE_SIZE, player.rect.centery // TILE_SIZE)
        if player_grid in curr_level.stairway_tiles and player.arrival_stairway_tile is None:
            dest_info = self.world.stairway_endpoints.get(
                (player.level_id, player_grid[0], player_grid[1])
            )
            if dest_info:
                (dest_lvl, dest_c, dest_r), ch = dest_info
                player.teleport_to_stairway(dest_lvl, dest_c, dest_r, ch)
                self.sound.play("footstep")
                self.set_notification(f"Traversed stairs '{ch}' to Level {dest_lvl}!", 2.0)
                curr_level = self.world.current_level

        touch_rect = player.rect.inflate(12, 12)
        touching_locked_door = False
        for item in list(curr_level.interactables):
            if touch_rect.colliderect(item.rect):
                outcome = self._try_interact_with_item(item)
                if outcome == "locked":
                    touching_locked_door = True
                elif outcome == "opened":
                    break

        if not touching_locked_door:
            self.last_locked_door_char = None

    def _render(self):
        if self.world.player:
            self.camera_offset[0] = self.world.player.rect.centerx - WINDOW_WIDTH // 2
            self.camera_offset[1] = self.world.player.rect.centery - WINDOW_HEIGHT // 2

        self.screen.fill((15, 18, 24))

        if self.state == "name_selection":
            self.ui.draw_name_selection(
                self.screen, self.class_config, self.all_student_names, self.menu_index
            )
        elif self.world.current_level:
            self.world.draw(self.screen, self.camera_offset)
            self.ui.draw(
                self.screen, self.world.player, self.sound,
                self.notification, self.notification_timer,
            )
            self.ui.draw_door_popup(self.screen, self.door_popup)

        if self.state == "question":
            self.ui.draw_question_overlay(self.screen, self.current_interactable, self.user_text)
        elif self.state == "sin_bin":
            self.ui.draw_sin_bin_overlay(
                self.screen, self.sin_bin_offences, self.sin_bin_reason, self.sin_bin_end_time
            )
        elif self.state == "victory":
            self.ui.draw_victory_screen(self.screen, self.world.player)

        pygame.display.flip()

    async def run(self):
        running = True
        focus_lost_event = getattr(pygame, "WINDOWFOCUSLOST", None)

        while running:
            keys = pygame.key.get_pressed()
            self._check_focus_and_sin_bin()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    continue

                if self.state == "question":
                    if (focus_lost_event and event.type == focus_lost_event) or (
                        event.type == pygame.ACTIVEEVENT
                        and getattr(event, "gain", 1) == 0
                        and getattr(event, "state", 0) & 2
                    ):
                        self._trigger_sin_bin("Game window lost focus during an active question!")
                        continue

                if self.state == "name_selection":
                    if event.type == pygame.KEYDOWN:
                        self._handle_name_selection_key(event.key)
                elif self.state == "victory":
                    # Keep the victory screen displayed indefinitely
                    pass
                elif self.state == "playing":
                    if event.type == pygame.KEYDOWN:
                        self._handle_playing_key(event.key)
                elif self.state == "question":
                    if event.type == pygame.KEYDOWN or auto_open_for_testing:
                        self._handle_question_key(event)

            self._update_npcs()
            self._update_playing(keys)
            self._render()

            self.clock.tick(FPS)
            await asyncio.sleep(0)

        pygame.quit()
        sys.exit()


async def main():
    try:
        active_class_id = detect_class_id()
        game = Game(class_id=active_class_id)
        await game.run()
    except Exception as e:
        import traceback
        log_diag("CRITICAL", f"Unhandled crash in main(): {e}\n{traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
