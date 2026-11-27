"""
Global Configuration and Constants for Maths Heist
"""
import os
import sys
import json
import platform

def log_diag(level, message):
    """
    Logs diagnostic messages to both standard output (local terminal)
    and the browser's DevTools console (when running under Pygbag/Emscripten).
    """
    formatted = f"[{level.upper()}] {message}"
    print(formatted, flush=True)
    if sys.platform == "emscripten":
        try:
            if level.upper() in ("ERROR", "CRITICAL"):
                platform.window.console.error(formatted)
            elif level.upper() in ("WARN", "WARNING"):
                platform.window.console.warn(formatted)
            else:
                platform.window.console.log(formatted)
        except Exception:
            pass


WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
FPS = 60
TILE_SIZE = 64

FIREBASE_URL = "https://maths-heist-telemetry-default-rtdb.asia-southeast1.firebasedatabase.app"

# Wrong answer lockouts on individual doors/chests (in seconds)
LOCKOUT_TIERS = [5, 10, 30, 60]

# Sin-bin lockouts for focus loss / AI detection (in seconds, escalating to 300s cap)
SIN_BIN_TIERS = [30, 60, 120, 240, 300]

# --- Colours ---
COLOUR_BLACK = (0, 0, 0)
COLOUR_WHITE = (255, 255, 255)
COLOUR_GREY = (100, 100, 100)
COLOUR_RED = (200, 50, 50)
COLOUR_GREEN = (50, 200, 50)

# --- Map Characters & Definitions ---
WALL_CHARS = set("|│┐└┴┬├┤─┼┘┌#")
UP_CHARS = set("│|└┴├┤┼┘")
DOWN_CHARS = set("│|┌┬├┤┼┐")
LEFT_CHARS = set("─┐┘┤┬┴┼")
RIGHT_CHARS = set("─┌└├┬┴┼")


def get_class_config(class_id="DEFAULT", config_filename="classes.json"):
    """
    Loads classes.json and returns the configuration dictionary for the given class_id.
    Logs explicit warnings whenever it falls back to DEFAULT or default_cfg.
    """
    default_cfg = {
        "class_id": class_id,
        "teacher": "Staff",
        "class_name": class_id,
        "students_file": "students.json",
        "questions_file": "questions.json"
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    fname = os.path.basename(config_filename)
    candidates = [
        os.path.join(base_dir, "data", fname),
        os.path.join(base_dir, "data", config_filename),
        os.path.join("data", fname),
        os.path.join("data", config_filename),
        os.path.join(base_dir, config_filename),
        os.path.join(base_dir, fname),
        config_filename,
        fname
    ]
    seen = set()
    unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    for candidate in unique_candidates:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)

                upper_map = {str(k).upper(): v for k, v in data.items()}
                query_key = str(class_id).strip().upper()
                
                if query_key in upper_map:
                    matched = upper_map[query_key]
                    log_diag("INFO", f"Class '{class_id}' matched in '{candidate}'.")
                else:
                    matched = upper_map.get("DEFAULT")
                    log_diag(
                        "WARN",
                        f"Class ID '{class_id}' (normalised: '{query_key}') NOT FOUND in '{candidate}'. "
                        f"Available keys: {list(data.keys())}. Falling back to 'DEFAULT' config!"
                    )

                if matched:
                    cfg = dict(default_cfg)
                    cfg.update(matched)
                    cfg["class_id"] = class_id
                    return cfg
            except Exception as e:
                log_diag("ERROR", f"Failed parsing class config '{candidate}': {e}")

    log_diag(
        "ERROR",
        f"Could not find or load '{config_filename}' in any candidate path: {unique_candidates}. "
        f"Falling back to hardcoded default_cfg: {default_cfg}"
    )
    return default_cfg