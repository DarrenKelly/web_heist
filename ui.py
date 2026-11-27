"""
UI and Overlay Rendering Subsystem
"""

import math
import os
import time
import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT, COLOUR_BLACK, COLOUR_WHITE, COLOUR_GREEN
from chest import get_key_icon_for_item


def load_custom_font(size, is_bold=False):
    if not pygame.font.get_init():
        pygame.font.init()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(base_dir, "Inter-Regular.ttf")

    try:
        font = pygame.font.Font(font_path if os.path.exists(font_path) else "Inter-Regular.ttf", size)
    except Exception as e:
        print(f"Warning: Could not load Inter-Regular.ttf, falling back to SysFont. Error: {e}")
        font = pygame.font.SysFont(None, size)

    if is_bold:
        font.set_bold(True)

    return font


class UIManager:
    def __init__(self):
        # Load fonts on instantiation (after pygame.init) rather than at module import time
        self.font_default = load_custom_font(36)
        self.font_lvl = load_custom_font(28, is_bold=True)
        self.font_score = load_custom_font(28, is_bold=True)
        self.font_hint = load_custom_font(24)
        self.font_popup_badge = load_custom_font(20, is_bold=True)
        self.font_popup_title = load_custom_font(28, is_bold=True)
        self.font_popup_desc = load_custom_font(24)
        self.font_popup_hint = load_custom_font(20)

        self.font_victory_title = load_custom_font(40, is_bold=True)
        self.font_victory_msg = load_custom_font(34, is_bold=True)
        self.font_victory_desc = load_custom_font(24)
        self.font_victory_score = load_custom_font(44, is_bold=True)

        self.font_menu_title = load_custom_font(44, is_bold=True)
        self.font_menu_sub = load_custom_font(24)
        self.font_menu_class = load_custom_font(22, is_bold=True)
        self.font_menu_name = load_custom_font(22)
        self.font_menu_hint = load_custom_font(20)

        self.font_sin_bin_title = load_custom_font(46, is_bold=True)
        self.font_sin_bin_timer = load_custom_font(68, is_bold=True)
        self.font_sin_bin_body = load_custom_font(24)

        self._hud_bg_surf = pygame.Surface((WINDOW_WIDTH, 72), pygame.SRCALPHA)
        self._hud_bg_surf.fill((0, 0, 0, 160))

        self._cached_lvl_id = None
        self._cached_lvl_bg = None
        self._cached_score_val = None
        self._cached_score_surf = None
        self._cached_hint_muted = None
        self._cached_hint_surf = None
        self._cached_door_popup_key = None
        self._cached_door_popup_surf = None
        self._cached_dark_overlay = None
        self._cached_sin_bin_overlay = None
        self._cached_victory_overlay = None
        self._cached_victory_lolly = False  # False = not loaded yet; None = missing
        self._cached_inv_tuple = None
        self._cached_inv_surf = None

    @staticmethod
    def get_menu_rows_per_col(all_student_names):
        total_names = max(1, len(all_student_names))
        num_cols = min(4, max(1, (total_names + 8) // 9))
        return (total_names + num_cols - 1) // num_cols

    def draw_name_selection(self, screen, class_config, all_student_names, menu_index):
        screen.fill((14, 18, 26))

        title_surf = self.font_menu_title.render("MATHS HEIST: THE VAULT OF LOLLIES", True, (255, 215, 60))
        screen.blit(title_surf, (WINDOW_WIDTH // 2 - title_surf.get_width() // 2, 35))

        class_name = class_config.get("class_name", class_config.get("class_id", "Default Class"))
        teacher = class_config.get("teacher", "Staff")
        class_info = f"Class: {class_name}  |  Teacher: {teacher}"
        class_surf = self.font_menu_class.render(class_info, True, (130, 205, 255))
        screen.blit(class_surf, (WINDOW_WIDTH // 2 - class_surf.get_width() // 2, 88))

        sub_surf = self.font_menu_sub.render("SELECT YOUR STUDENT AGENT IDENTITY", True, (230, 235, 245))
        screen.blit(sub_surf, (WINDOW_WIDTH // 2 - sub_surf.get_width() // 2, 120))

        total_names = len(all_student_names)
        num_cols = min(4, max(1, (total_names + 8) // 9))
        rows_per_col = self.get_menu_rows_per_col(all_student_names)

        card_w = 210
        card_h = 36
        gap_x = 20
        gap_y = 10
        grid_w = num_cols * card_w + (num_cols - 1) * gap_x
        start_x = (WINDOW_WIDTH - grid_w) // 2
        start_y = 165

        for idx, name in enumerate(all_student_names):
            col = idx // rows_per_col
            row = idx % rows_per_col
            cx = start_x + col * (card_w + gap_x)
            cy = start_y + row * (card_h + gap_y)
            rect = pygame.Rect(cx, cy, card_w, card_h)

            if idx == menu_index:
                pygame.draw.rect(screen, (35, 75, 125), rect, border_radius=6)
                pygame.draw.rect(screen, (255, 215, 60), rect, 2, border_radius=6)
                txt_surf = self.font_menu_name.render(f">> {name}", True, (255, 255, 255))
            else:
                pygame.draw.rect(screen, (22, 28, 38), rect, border_radius=6)
                pygame.draw.rect(screen, (50, 62, 80), rect, 1, border_radius=6)
                txt_surf = self.font_menu_name.render(name, True, (190, 200, 220))

            screen.blit(txt_surf, (cx + 12, cy + (card_h - txt_surf.get_height()) // 2))

        hint_surf = self.font_menu_hint.render(
            "Use Arrow Keys [Up/Down/Left/Right] to Navigate  |  Press ENTER or SPACE to Select Agent",
            True, (170, 185, 205)
        )
        screen.blit(hint_surf, (WINDOW_WIDTH // 2 - hint_surf.get_width() // 2, WINDOW_HEIGHT - 45))

    def draw_sin_bin_overlay(self, screen, offences, reason, end_time):
        if self._cached_sin_bin_overlay is None:
            self._cached_sin_bin_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            self._cached_sin_bin_overlay.fill((25, 8, 12, 230))
        screen.blit(self._cached_sin_bin_overlay, (0, 0))

        box_w, box_h = 780, 400
        box_rect = pygame.Rect((WINDOW_WIDTH - box_w) // 2, (WINDOW_HEIGHT - box_h) // 2, box_w, box_h)
        pygame.draw.rect(screen, (45, 14, 20), box_rect, border_radius=12)
        pygame.draw.rect(screen, (235, 70, 70), box_rect, 4, border_radius=12)

        title_surf = self.font_sin_bin_title.render("SECURITY LOCKOUT: SIN-BINNED!", True, (255, 95, 95))
        screen.blit(title_surf, (WINDOW_WIDTH // 2 - title_surf.get_width() // 2, box_rect.top + 28))

        offence_surf = self.font_sin_bin_body.render(
            f"Offence #{offences} — {reason}", True, (255, 215, 160)
        )
        screen.blit(offence_surf, (WINDOW_WIDTH // 2 - offence_surf.get_width() // 2, box_rect.top + 96))

        info_lines = [
            "Switching tabs, windows, or using snipping tools",
            "during a question is strictly prohibited.",
        ]
        y_curr = box_rect.top + 136
        for line in info_lines:
            info_surf = self.font_sin_bin_body.render(line, True, (220, 220, 220))
            screen.blit(info_surf, (WINDOW_WIDTH // 2 - info_surf.get_width() // 2, y_curr))
            y_curr += 30

        regen_surf = self.font_sin_bin_body.render(
            "The security cipher has scrambled and regenerated the question numbers.",
            True, (140, 220, 255)
        )
        screen.blit(regen_surf, (WINDOW_WIDTH // 2 - regen_surf.get_width() // 2, y_curr + 8))

        lock_surf = self.font_sin_bin_body.render(
            "Movement and interactions remain locked until the penalty timer expires.",
            True, (190, 195, 205)
        )
        screen.blit(lock_surf, (WINDOW_WIDTH // 2 - lock_surf.get_width() // 2, y_curr + 42))

        remaining = max(0, int(math.ceil(end_time - time.time())))
        timer_surf = self.font_sin_bin_timer.render(f"{remaining}s", True, (255, 230, 90))
        screen.blit(timer_surf, (WINDOW_WIDTH // 2 - timer_surf.get_width() // 2, box_rect.bottom - 105))

    def _render_inventory_surface(self, inventory):
        max_w = WINDOW_WIDTH - 150 - 20
        inv_surf = pygame.Surface((max_w, 32), pygame.SRCALPHA)

        lbl_surf = self.font_lvl.render("Inventory:", True, (230, 235, 250))
        inv_surf.blit(lbl_surf, (0, 6))
        cur_x = lbl_surf.get_width() + 10

        if not inventory:
            empty_surf = self.font_hint.render("Empty", True, (150, 160, 180))
            inv_surf.blit(empty_surf, (cur_x, 9))
            return inv_surf

        for idx, item in enumerate(inventory):
            icon = get_key_icon_for_item(item, (22, 22))
            txt_surf = self.font_hint.render(str(item), True, (255, 235, 140))
            icon_w = icon.get_width() if icon else 0
            pill_w = (icon_w + 6 if icon else 0) + txt_surf.get_width() + 12
            pill_h = 28
            pill_y = 2

            if cur_x + pill_w > max_w:
                more_count = len(inventory) - idx
                more_surf = self.font_hint.render(f"+{more_count} more", True, (200, 210, 230))
                inv_surf.blit(more_surf, (cur_x, 9))
                break

            pill_bg = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
            pill_bg.fill((22, 27, 38, 220))
            pygame.draw.rect(pill_bg, (70, 85, 110), (0, 0, pill_w, pill_h), 1, border_radius=6)

            offset_x = 6
            if icon:
                pill_bg.blit(icon, (offset_x, (pill_h - icon.get_height()) // 2))
                offset_x += icon.get_width() + 6
            pill_bg.blit(txt_surf, (offset_x, (pill_h - txt_surf.get_height()) // 2))

            inv_surf.blit(pill_bg, (cur_x, pill_y))
            cur_x += pill_w + 8

        return inv_surf

    def draw_ui(self, screen, player, sound, notification="", notification_timer=0.0):
        screen.blit(self._hud_bg_surf, (0, 0))

        inv_tuple = tuple(player.inventory) if (player and player.inventory) else ()
        if self._cached_inv_tuple != inv_tuple or self._cached_inv_surf is None:
            self._cached_inv_tuple = inv_tuple
            self._cached_inv_surf = self._render_inventory_surface(inv_tuple)
        screen.blit(self._cached_inv_surf, (20, 8))

        lvl_num = player.level_id if player else 0
        if self._cached_lvl_id != lvl_num:
            self._cached_lvl_id = lvl_num
            lvl_surf = self.font_lvl.render(f"Level: {lvl_num}", True, (255, 220, 80))
            lvl_bg = pygame.Surface((lvl_surf.get_width() + 18, lvl_surf.get_height() + 8), pygame.SRCALPHA)
            lvl_bg.fill((25, 30, 42, 220))
            pygame.draw.rect(lvl_bg, (255, 200, 60), (0, 0, lvl_bg.get_width(), lvl_bg.get_height()), 2, border_radius=6)
            lvl_bg.blit(lvl_surf, (9, 4))
            self._cached_lvl_bg = lvl_bg
        screen.blit(self._cached_lvl_bg, (WINDOW_WIDTH - self._cached_lvl_bg.get_width() - 20, 10))

        if player:
            score_val = getattr(player, "score", 0)
            if self._cached_score_val != score_val or self._cached_score_surf is None:
                self._cached_score_val = score_val
                score_txt = self.font_score.render(f"Score: {score_val} pts", True, (255, 215, 60))
                pad_x, pad_y = 12, 6
                box_w = score_txt.get_width() + pad_x * 2
                box_h = score_txt.get_height() + pad_y * 2
                box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
                box_surf.fill((20, 26, 38, 220))
                pygame.draw.rect(box_surf, (255, 215, 60), (0, 0, box_w, box_h), 2, border_radius=6)
                box_surf.blit(score_txt, (pad_x, pad_y))
                self._cached_score_surf = box_surf

            screen.blit(
                self._cached_score_surf,
                (WINDOW_WIDTH - self._cached_score_surf.get_width() - 190, 12)
            )

        mute_status = " [M: Muted]" if sound.muted else " [M: Audio On]"
        if notification and time.time() < notification_timer:
            notif_surf = self.font_default.render(notification, True, (255, 235, 100))
            screen.blit(notif_surf, (20, 42))
        else:
            if self._cached_hint_muted != sound.muted:
                self._cached_hint_muted = sound.muted
                self._cached_hint_surf = self.font_hint.render(
                    f"Touch a Door (easier), Chest (harder), or Stairs [a-z]!{mute_status}",
                    True,
                    (160, 170, 190)
                )
            screen.blit(self._cached_hint_surf, (20, 44))

    def draw(self, screen, player, sound, notification="", notification_timer=0.0):
        """
        Unified draw function for the main HUD overlay.
        """
        self.draw_ui(screen, player, sound, notification, notification_timer)

    def draw_door_popup(self, screen, door_popup):
        if not door_popup or time.time() > door_popup.get("expires_at", 0):
            return

        door_char = door_popup["door_char"]
        item_name = door_popup["item_name"]
        chest_id = door_popup["chest_id"]
        popup_key = (door_char, item_name, chest_id)

        if self._cached_door_popup_key != popup_key:
            self._cached_door_popup_key = popup_key
            popup_w = 640
            popup_h = 100

            popup_surf = pygame.Surface((popup_w, popup_h), pygame.SRCALPHA)
            popup_surf.fill((20, 24, 34, 240))
            pygame.draw.rect(popup_surf, (240, 160, 40), (0, 0, popup_w, popup_h), 2, border_radius=10)

            badge_rect = pygame.Rect(14, 14, 72, 72)
            pygame.draw.rect(popup_surf, (185, 45, 45), badge_rect, border_radius=8)
            pygame.draw.rect(popup_surf, (240, 100, 100), badge_rect, 2, border_radius=8)

            txt1 = self.font_popup_badge.render("LOCKED", True, COLOUR_WHITE)
            txt2 = self.font_popup_badge.render(f"DOOR {door_char}", True, (255, 235, 120))
            popup_surf.blit(txt1, (badge_rect.centerx - txt1.get_width() // 2, 26))
            popup_surf.blit(txt2, (badge_rect.centerx - txt2.get_width() // 2, 48))

            title_surf = self.font_popup_title.render(f"Door '{door_char}' is Locked! Item Required", True, (255, 240, 220))
            popup_surf.blit(title_surf, (100, 18))

            desc_surf = self.font_popup_desc.render(f"Required Item: {item_name}", True, (255, 215, 60))
            popup_surf.blit(desc_surf, (100, 48))

            hint_surf = self.font_popup_hint.render(f"Hint: Solve Chest #{chest_id} to collect this item first.", True, (170, 185, 205))
            popup_surf.blit(hint_surf, (100, 72))
            self._cached_door_popup_surf = popup_surf

        popup_x = (WINDOW_WIDTH - 640) // 2
        popup_y = 86
        screen.blit(self._cached_door_popup_surf, (popup_x, popup_y))

    def draw_question_overlay(self, screen, current_interactable, user_text=""):
        if not current_interactable:
            return

        if self._cached_dark_overlay is None:
            self._cached_dark_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
            self._cached_dark_overlay.set_alpha(200)
            self._cached_dark_overlay.fill(COLOUR_BLACK)
        screen.blit(self._cached_dark_overlay, (0, 0))

        question = current_interactable.question_data
        y_offset = WINDOW_HEIGHT // 2 - 50

        img_data = (question.get("image") or question.get("img") or
                    question.get("image_path") or question.get("file") or
                    question.get("pic") or question.get("diagram"))

        raw_img = None
        if isinstance(img_data, pygame.Surface):
            raw_img = img_data
        elif isinstance(img_data, str) and img_data.strip() != "":
            if "_cached_surface" not in question:
                question["_cached_surface"] = None
                base_dir = os.path.dirname(os.path.abspath(__file__))
                candidates = [
                    os.path.join(base_dir, img_data),
                    os.path.join(base_dir, "img", os.path.basename(img_data)),
                    img_data,
                ]
                for path in candidates:
                    if os.path.exists(path):
                        try:
                            question["_cached_surface"] = pygame.image.load(path).convert_alpha()
                            break
                        except Exception as e:
                            print(f"Error loading image '{path}': {e}")
            raw_img = question["_cached_surface"]

        if raw_img:
            max_img_w = int(WINDOW_WIDTH * 0.75)
            max_img_h = int(WINDOW_HEIGHT * 0.50)
            img_w, img_h = raw_img.get_size()

            if img_w > 0 and img_h > 0:
                if "_cached_scaled_img" not in question or question.get("_cached_scaled_src") is not raw_img:
                    scale = min(max_img_w / img_w, max_img_h / img_h)
                    new_w = int(img_w * scale)
                    new_h = int(img_h * scale)
                    question["_cached_scaled_img"] = pygame.transform.smoothscale(raw_img, (new_w, new_h))
                    question["_cached_scaled_src"] = raw_img

                scaled_img = question["_cached_scaled_img"]
                img_x = WINDOW_WIDTH // 2 - scaled_img.get_width() // 2
                img_y = int(WINDOW_HEIGHT * 0.08)
                screen.blit(scaled_img, (img_x, img_y))
                y_offset = img_y + scaled_img.get_height() + 25

        question_text = (question.get("q") or question.get("question") or
                         question.get("text") or question.get("prompt") or "")

        if not question_text and not raw_img:
            question_text = f"Debug - Dict keys found: {list(question.keys())}"

        if question_text:
            lines = str(question_text).replace("\\n", "\n").split("\n")
            for line in lines:
                line_surf = self.font_default.render(line.strip(), True, COLOUR_WHITE)
                screen.blit(line_surf, (WINDOW_WIDTH // 2 - line_surf.get_width() // 2, y_offset))
                y_offset += self.font_default.get_linesize() + 6

        y_offset += 15

        input_text = self.font_default.render(f"Answer: {user_text}_", True, COLOUR_GREEN)
        screen.blit(input_text, (WINDOW_WIDTH // 2 - input_text.get_width() // 2, y_offset))

    def _get_victory_lolly_surface(self):
        if self._cached_victory_lolly is False:
            self._cached_victory_lolly = None
            base_dir = os.path.dirname(os.path.abspath(__file__))
            lolly_path = os.path.join(base_dir, "img", "treasure6.png")
            if not os.path.exists(lolly_path):
                lolly_path = "img/treasure6.png"
            if os.path.exists(lolly_path):
                try:
                    raw = pygame.image.load(lolly_path).convert_alpha()
                    self._cached_victory_lolly = pygame.transform.smoothscale(raw, (80, 80))
                except Exception as e:
                    print(f"UI Error: Failed to render victory lolly image: {e}")
        return self._cached_victory_lolly

    def draw_victory_screen(self, screen, player=None):
        if self._cached_victory_overlay is None:
            self._cached_victory_overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
            self._cached_victory_overlay.fill((0, 0, 0, 220))
        screen.blit(self._cached_victory_overlay, (0, 0))

        box_w = 780
        box_h = 550
        box_x = (WINDOW_WIDTH - box_w) // 2
        box_y = (WINDOW_HEIGHT - box_h) // 2

        dialog_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        dialog_surf.fill((18, 22, 32, 250))
        pygame.draw.rect(dialog_surf, (255, 215, 0), (0, 0, box_w, box_h), 4, border_radius=16)
        pygame.draw.rect(dialog_surf, (255, 185, 30), (6, 6, box_w - 12, box_h - 12), 1, border_radius=12)
        screen.blit(dialog_surf, (box_x, box_y))

        title_surf = self.font_victory_title.render("--> HEIST COMPLETE! <--", True, (255, 220, 60))
        screen.blit(title_surf, (box_x + (box_w - title_surf.get_width()) // 2, box_y + 24))

        pygame.draw.line(screen, (65, 75, 95), (box_x + 40, box_y + 70), (box_x + box_w - 40, box_y + 70), 2)

        msg_surf = self.font_victory_msg.render("Congratulations! You escaped with a bag of lollies!", True, (120, 255, 170))
        screen.blit(msg_surf, (box_x + (box_w - msg_surf.get_width()) // 2, box_y + 88))

        center_x = box_x + box_w // 2
        img_center_y = box_y + 195
        pygame.draw.circle(screen, (255, 215, 0, 50), (center_x, img_center_y), 54)
        pygame.draw.circle(screen, (255, 215, 0), (center_x, img_center_y), 54, 2)

        lolly_surf = self._get_victory_lolly_surface()
        if lolly_surf:
            screen.blit(lolly_surf, (center_x - 40, img_center_y - 40))

        detail_lines = [
            "You unlocked the School Gates and made your grand getaway!",
            "All maths obstacles were conquered and the sweet prize is yours.",
            "The Vault of Lollies Heist was a triumphant success!",
        ]
        curr_y = box_y + 270
        for line in detail_lines:
            line_surf = self.font_victory_desc.render(line, True, (230, 235, 245))
            screen.blit(line_surf, (box_x + (box_w - line_surf.get_width()) // 2, curr_y))
            curr_y += 30

        if player is not None:
            score_val = getattr(player, "score", 0) if not isinstance(player, (int, float)) else int(player)
            final_surf = self.font_victory_score.render(
                f"Final Score: {score_val} Points", True, (255, 230, 80)
            )
            bg_w = final_surf.get_width() + 40
            bg_h = final_surf.get_height() + 20
            bg_rect = pygame.Rect((WINDOW_WIDTH - bg_w) // 2, WINDOW_HEIGHT // 2 + 100, bg_w, bg_h)
            pygame.draw.rect(screen, (18, 24, 34), bg_rect, border_radius=8)
            pygame.draw.rect(screen, (255, 215, 60), bg_rect, 2, border_radius=8)
            screen.blit(final_surf, (bg_rect.x + 20, bg_rect.y + 15))
