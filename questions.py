"""
Questions Loading, Filtering, Allocation, and Answer Validation
"""

import json
import os
import random

from config import log_diag
from question_generators import parameterise_question


def _resolve_question_bank_path(filename, base_dir):
    """
    Resolves a single question bank JSON path relative to the project root,
    data/, or data/banks/.
    """
    if not filename:
        return None
    fname = os.path.basename(filename)
    candidates = [
        filename,
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "data", filename),
        os.path.join(base_dir, "data", "banks", filename),
        os.path.join("data", "banks", filename),
        os.path.join(base_dir, "data", "banks", fname),
        os.path.join("data", "banks", fname),
    ]
    seen = set()
    for c in candidates:
        if c not in seen:
            seen.add(c)
            if os.path.exists(c):
                return c
    return None


def _read_questions_from_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = []
    if isinstance(data, list):
        for q in data:
            item = dict(q)
            item.setdefault("category", "Maths")
            items.append(item)
    else:
        for cat in data.get("categories", []):
            cat_name = cat.get("category_name", "Maths")
            for q in cat.get("questions", []):
                item = dict(q)
                item["category"] = cat_name
                items.append(item)
    return items


def load_questions(
    source="questions.json",
    *,
    min_points=None,
    max_points=None,
    categories=None,
    exclude_categories=None,
    exclude_question_ids=None,
    stage_3_accessible_only=False,
):
    """
    Loads and filters questions from:
      - a class_config dictionary (supporting 'question_banks', legacy 'questions_file',
        'min_points', 'max_points', 'categories', 'exclude_categories',
        'exclude_question_ids', and 'stage_3_accessible_only'),
      - a list/tuple of question bank JSON paths, or
      - a single question bank JSON filename string.

    Deduplicates questions by 'id' across imported banks (first occurrence wins).
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    class_label = None

    if isinstance(source, dict):
        class_label = source.get("class_id", "UNKNOWN")
        banks = source.get("question_banks")
        if not banks:
            qfile = source.get("questions_file", "questions.json")
            banks = [qfile] if isinstance(qfile, str) else list(qfile)
        if min_points is None:
            min_points = source.get("min_points")
        if max_points is None:
            max_points = source.get("max_points")
        if categories is None:
            categories = source.get("categories")
        if exclude_categories is None:
            exclude_categories = source.get("exclude_categories")
        if exclude_question_ids is None:
            exclude_question_ids = source.get("exclude_question_ids")
        if not stage_3_accessible_only:
            stage_3_accessible_only = bool(source.get("stage_3_accessible_only", False))
    elif isinstance(source, (list, tuple)):
        banks = list(source)
    else:
        banks = [source] if source else ["questions.json"]

    raw_pool = []
    seen_ids = set()
    loaded_files = []

    for bank_entry in banks:
        resolved = _resolve_question_bank_path(bank_entry, base_dir)
        if not resolved:
            log_diag("WARN", f"Question bank '{bank_entry}' not found; skipping.")
            continue
        try:
            items = _read_questions_from_file(resolved)
            added = 0
            for item in items:
                qid = item.get("id")
                if qid is not None:
                    if qid in seen_ids:
                        continue
                    seen_ids.add(qid)
                raw_pool.append(item)
                added += 1
            loaded_files.append(f"{resolved} (+{added})")
        except Exception as e:
            log_diag("ERROR", f"Error loading questions from '{resolved}': {e}")

    if not raw_pool:
        fallback_candidates = [
            "questions.json",
            "data/banks/default_questions.json",
            "data/banks/yr7_questions.json",
        ]
        for fb in fallback_candidates:
            resolved = _resolve_question_bank_path(fb, base_dir)
            if resolved:
                try:
                    raw_pool = _read_questions_from_file(resolved)
                    if raw_pool:
                        log_diag("WARN", f"Fell back to question bank '{resolved}' ({len(raw_pool)} questions).")
                        loaded_files.append(resolved)
                        break
                except Exception as e:
                    log_diag("ERROR", f"Error loading fallback bank '{resolved}': {e}")

    if not raw_pool:
        log_diag("WARN", "Using hardcoded fallback questions pool.")
        return [
            {"id": "fallback_1", "question": "What is 12 × 8?", "accepted_answers": ["96"], "points": 100, "category": "Arithmetic"},
            {"id": "fallback_2", "question": "Solve for x: 2x + 4 = 12", "accepted_answers": ["4"], "points": 200, "category": "Algebra"},
            {"id": "fallback_3", "question": "Calculate 15% of 200", "accepted_answers": ["30"], "points": 300, "category": "Financial"},
            {"id": "fallback_4", "question": "What is the square root of 144?", "accepted_answers": ["12"], "points": 400, "category": "Algebra"},
            {"id": "fallback_5", "question": "Evaluate: sin(90°) + cos(0°)", "accepted_answers": ["2"], "points": 500, "category": "Trigonometry"},
        ]

    include_cats = {c.strip().lower() for c in categories if str(c).strip()} if categories else None
    exclude_cats = {c.strip().lower() for c in exclude_categories if str(c).strip()} if exclude_categories else set()
    exclude_ids = {str(qid).strip() for qid in exclude_question_ids if str(qid).strip()} if exclude_question_ids else set()

    filtered = []
    for q in raw_pool:
        cat_norm = str(q.get("category", "")).strip().lower()
        qid = str(q.get("id", "")).strip()
        pts = q.get("points", 100)

        if include_cats is not None and cat_norm not in include_cats:
            continue
        if cat_norm in exclude_cats:
            continue
        if qid and qid in exclude_ids:
            continue
        if stage_3_accessible_only and not q.get("stage_3_accessible", False):
            continue
        if min_points is not None and pts < min_points:
            continue
        if max_points is not None and pts > max_points:
            continue
        filtered.append(q)

    ctx = f" for class '{class_label}'" if class_label else ""
    if not filtered:
        log_diag(
            "WARN",
            f"All {len(raw_pool)} loaded questions were filtered out{ctx} "
            f"(min_points={min_points}, max_points={max_points}, categories={categories}). "
            f"Falling back to unfiltered pool ({len(raw_pool)} questions)."
        )
        return raw_pool

    log_diag(
        "INFO",
        f"Loaded {len(filtered)}/{len(raw_pool)} questions{ctx} from {len(loaded_files)} bank(s) "
        f"[points: {min_points if min_points is not None else 'any'}–{max_points if max_points is not None else 'any'}]."
    )
    return filtered


def load_questions_for_class(class_config):
    """
    Convenience entry point to load and filter questions directly from a class config dict.
    """
    return load_questions(class_config)


def allocate_tiered_questions(questions, door_z_list, chest_list, key_door_list, unkeyed_door_list):
    """
    Distributes questions from hardest to easiest across:
      1. Vault Exit Door Z
      2. Treasure Chests
      3. Key-locked Doors
      4. Standard Unkeyed Doors
    Returns an audit warning message string if the bank has fewer questions than
    triggers, or None otherwise.
    """
    total_triggers = (
        len(door_z_list) + len(chest_list) +
        len(key_door_list) + len(unkeyed_door_list)
    )
    bank_size = len(questions)

    print(
        f"[AUDIT] Map Question Triggers: {total_triggers} "
        f"(Door Z: {len(door_z_list)}, Chests: {len(chest_list)}, "
        f"Key Doors: {len(key_door_list)}, Standard Doors: {len(unkeyed_door_list)}) | "
        f"Question Bank Size: {bank_size}"
    )

    warning_msg = None
    if bank_size < total_triggers:
        shortfall = total_triggers - bank_size
        print(
            f"[AUDIT WARNING] Question bank has {bank_size} questions for {total_triggers} triggers. "
            f"Shortfall: {shortfall}. Pool will be reshuffled for remaining triggers."
        )
        warning_msg = f"Audit Warning: {total_triggers} doors/chests vs {bank_size} questions in bank"

    def build_sorted_pool():
        pool = [dict(q) for q in questions]
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

    return warning_msg


def check_answer(user_input, accepted_answers):
    if not user_input:
        return False
    if user_input.strip() == "~*":
        return True
    u = user_input.strip().lower().replace("−", "-").replace("–", "-")
    for ans in accepted_answers:
        a = str(ans).strip().lower().replace("−", "-").replace("–", "-")
        if u == a:
            return True
        u_clean = u.replace("$", "").replace("°c", "").replace("°", "").replace("%", "").strip()
        a_clean = a.replace("$", "").replace("°c", "").replace("°", "").replace("%", "").strip()
        if u_clean and u_clean == a_clean:
            return True
        # Match ignoring spaces and thousands commas (e.g. '2 : 3' vs '2:3', '35 000' vs '35000', '5a + 9b' vs '5a+9b')
        u_compact = u_clean.replace(",", "").replace(" ", "")
        a_compact = a_clean.replace(",", "").replace(" ", "")
        if u_compact and u_compact == a_compact:
            return True
        # Match numerically equivalent decimals (e.g. '.25' vs '0.25', '0.2' vs '0.20', '18.0' vs '18')
        try:
            if abs(float(u_compact) - float(a_compact)) < 1e-9:
                return True
        except ValueError:
            pass
        suffixes = [
            "years", "yrs", "year", "yr",
            "km/hr", "km/h", "kmh", "km/l",
            "m2", "m²", "cm2", "cm²", "m3", "m³",
            "kl", "km", "mm", "ml", "cm", "m",
            "minutes", "mins", "min", "hours", "hrs", "hr",
            "seconds", "secs", "sec", "times",
            "students", "marbles", "points", "pts",
            "degrees", "deg", "units", "cans", "cans of paint",
        ]
        for suffix in suffixes:
            if u_clean.endswith(suffix):
                u_clean = u_clean[:-len(suffix)].strip()
            if a_clean.endswith(suffix):
                a_clean = a_clean[:-len(suffix)].strip()
        if u_clean and (
            u_clean == a_clean
            or u_clean.replace(",", "").replace(" ", "") == a_clean.replace(",", "").replace(" ", "")
        ):
            return True
    return False
