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


def _resolve_config_path(path_or_name, base_dir):
    """
    Resolves a config path relative to the project root, data/, or data/classes/.
    """
    if not path_or_name:
        return None
    fname = os.path.basename(path_or_name)
    candidates = [
        os.path.join(base_dir, path_or_name),
        path_or_name,
        os.path.join(base_dir, "data", path_or_name),
        os.path.join("data", path_or_name),
        os.path.join(base_dir, "data", "classes", fname),
        os.path.join("data", "classes", fname),
        os.path.join(base_dir, "data", fname),
        os.path.join("data", fname),
        os.path.join(base_dir, fname),
        fname,
    ]
    seen = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            if os.path.exists(c):
                return c
    return None


def _load_profile_with_inheritance(raw_cfg, base_dir, visited=None):
    """
    Resolves optional 'config_file' and recursive 'extends'/'inherits' chains
    for a per-class configuration dictionary.
    """
    if visited is None:
        visited = set()

    merged = {}

    # 1. If the registry entry points to a dedicated per-class config_file, load it first
    cfg_file = raw_cfg.get("config_file")
    if cfg_file:
        resolved_cfg_file = _resolve_config_path(cfg_file, base_dir)
        if resolved_cfg_file:
            abs_key = os.path.abspath(resolved_cfg_file)
            if abs_key not in visited:
                visited.add(abs_key)
                try:
                    with open(resolved_cfg_file, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                    log_diag("INFO", f"Loaded per-class config file '{resolved_cfg_file}'.")
                    merged.update(_load_profile_with_inheritance(file_data, base_dir, visited))
                except Exception as e:
                    log_diag("ERROR", f"Failed loading per-class config '{resolved_cfg_file}': {e}")
        else:
            log_diag("WARN", f"Referenced config_file '{cfg_file}' could not be found.")

    # 2. If this profile extends a base profile (e.g. stage4_base.json), resolve the parent first
    parent_ref = raw_cfg.get("extends") or raw_cfg.get("inherits")
    if parent_ref:
        resolved_parent = _resolve_config_path(parent_ref, base_dir)
        if resolved_parent:
            abs_parent = os.path.abspath(resolved_parent)
            if abs_parent not in visited:
                visited.add(abs_parent)
                try:
                    with open(resolved_parent, "r", encoding="utf-8") as f:
                        parent_data = json.load(f)
                    log_diag("INFO", f"Inherited base class profile '{resolved_parent}'.")
                    parent_resolved = _load_profile_with_inheritance(parent_data, base_dir, visited)
                    # Parent sits underneath both config_file and inline overrides
                    parent_resolved.update(merged)
                    merged = parent_resolved
                except Exception as e:
                    log_diag("ERROR", f"Failed loading base profile '{resolved_parent}': {e}")
        else:
            log_diag("WARN", f"Referenced base profile '{parent_ref}' could not be found.")

    # 3. Overlay current dictionary's own keys on top (excluding meta keys once processed)
    for k, v in raw_cfg.items():
        if k not in ("config_file", "extends", "inherits"):
            merged[k] = v

    return merged


def get_class_config(class_id="DEFAULT", config_filename="classes.json"):
    """
    Loads per-class configuration for the given class_id.
    Lookup order:
      1. Matching entry in classes.json (resolving optional 'config_file' and 'extends').
      2. Standalone per-class file at data/classes/<class_id_lower>.json.
      3. 'DEFAULT' entry in classes.json or data/classes/default.json.
      4. Hardcoded fallback configuration.
    """
    default_cfg = {
        "class_id": class_id,
        "teacher": "Staff",
        "class_name": class_id,
        "students_file": "students.json",
        "questions_file": "questions.json",
        "question_banks": None,
        "categories": None,
        "exclude_categories": [],
        "min_points": None,
        "max_points": None,
        "exclude_question_ids": [],
        "stage_3_accessible_only": False,
    }

    base_dir = os.path.dirname(os.path.abspath(__file__))
    query_key = str(class_id).strip().upper()
    query_lower = query_key.lower()

    registry_path = _resolve_config_path(config_filename, base_dir)
    registry_data = {}
    if registry_path:
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry_data = json.load(f)
        except Exception as e:
            log_diag("ERROR", f"Failed parsing class registry '{registry_path}': {e}")

    upper_map = {str(k).upper(): v for k, v in registry_data.items()}
    matched_raw = None

    if query_key in upper_map:
        matched_raw = upper_map[query_key]
        log_diag("INFO", f"Class '{class_id}' matched in '{registry_path}'.")
    else:
        # Check for a standalone per-class JSON at data/classes/<class_id_lower>.json
        standalone = _resolve_config_path(f"data/classes/{query_lower}.json", base_dir)
        if standalone:
            log_diag("INFO", f"Found standalone per-class config '{standalone}' for '{class_id}'.")
            matched_raw = {"config_file": standalone}
        elif "DEFAULT" in upper_map:
            matched_raw = upper_map["DEFAULT"]
            log_diag(
                "WARN",
                f"Class ID '{class_id}' (normalised: '{query_key}') NOT FOUND in '{registry_path}' "
                f"or data/classes/{query_lower}.json. Available keys: {list(registry_data.keys())}. "
                f"Falling back to 'DEFAULT' config!"
            )
        else:
            default_standalone = _resolve_config_path("data/classes/default.json", base_dir)
            if default_standalone:
                log_diag("WARN", f"Falling back to standalone '{default_standalone}' for '{class_id}'.")
                matched_raw = {"config_file": default_standalone}

    if matched_raw:
        resolved = _load_profile_with_inheritance(matched_raw, base_dir)
        cfg = dict(default_cfg)
        cfg.update(resolved)
        cfg["class_id"] = class_id
        # Normalise question_banks if only legacy questions_file was provided
        if not cfg.get("question_banks") and cfg.get("questions_file"):
            cfg["question_banks"] = [cfg["questions_file"]]
        return cfg

    log_diag(
        "ERROR",
        f"Could not find or load class configuration for '{class_id}'. "
        f"Falling back to hardcoded default_cfg: {default_cfg}"
    )
    return default_cfg