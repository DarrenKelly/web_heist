"""
Questions, Dynamic Parameterisation, and Progression Data Management
"""

import os
import json
import math
import random
from chest import OBJECT_DEFINITIONS
from config import log_diag

DEFAULT_CHEST_TO_DOORS_MAP = {
    '0': ['Z'],       # Chest 0 (Bag of Jelly Snakes) is required for Door Z
    '1': ['B'],       # Chest 1 (Gold Coin) is required for Door B
    '2': ['D'],       # Chest 2 (Emerald) is required for Door D
    '3': ['F'],       # Chest 3 (Laser Pass) is required for Door F
    '4': ['E'],       # Chest 4 (Magic Mushroom) is required for Door E
    '5': ['A'],       # Chest 5 (Ruby Gem) is required for Door A
    '6': ['M'],       # Chest 6 (Gargoyle Relic) is required for Door M
    '7': ['C'],       # Chest 7 (Demon Token) is required for Door C
    '8': ['N'],       # Chest 8 (Sapphire) is required for Door N
    '9': ['I'],       # Chest 9 (Silver Key) is required for Door I
}


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

    # Graceful fallback if none of the requested banks could be loaded
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

    # Apply per-class filters
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


def parameterise_question(q_data, force_regenerate=False):
    """
    Returns a fresh copy of q_data with dynamically generated numbers and
    recomputed answers.
    - If a question has a static diagram (`q.get("image")`) and `force_regenerate` is False,
      it preserves the original JSON values so the text matches the diagram.
    - If `force_regenerate` is True (e.g. after a Sin-Bin focus-loss offence),
      it randomises the numbers and clears `q["image"]` so any screenshot is invalidated.
    """
    q = dict(q_data)
    qid = q.get("id", "")
    has_diagram = bool(q.get("image"))

    if has_diagram and not force_regenerate:
        return q

    if force_regenerate and has_diagram and qid != "alg_350":
        q["image"] = None
        for cache_key in ("_cached_surface", "_cached_scaled_img", "_cached_scaled_src"):
            q.pop(cache_key, None)

    # --- 1. Data Analysis & Visualisation ---
    if qid == "data_200":
        s1 = random.randint(8, 12)
        s2 = random.randint(13, 15)
        s3 = random.randint(16, 21)
        s4 = s3 + random.choice([2, 4, 6])
        s5 = random.randint(s4 + 2, s4 + 5)
        s6 = random.randint(s5 + 1, s5 + 5)
        med = (s3 + s4) // 2
        scrambled = [s4, s1, s5, s2, s6, s3]
        q["question"] = (
            f"Find the median of the following 6 test scores:\n"
            f"{', '.join(map(str, scrambled))}"
        )
        q["accepted_answers"] = [str(med), f"{med}.0"]
        q["worked_solution"] = (
            f"Ordered scores: {s1}, {s2}, {s3}, {s4}, {s5}, {s6}. "
            f"Middle two are {s3} and {s4}. Median = ({s3} + {s4}) ÷ 2 = {med}."
        )

    elif qid == "data_350":
        combos = [
            (2, 4, 3, 5, "1.5"),
            (3, 3, 3, 5, "1.4"),
            (1, 5, 3, 5, "1.6"),
            (2, 3, 4, 5, "1.6"),
            (1, 4, 4, 6, "1.8"),
            (3, 4, 2, 4, "1.2"),
        ]
        c0, c1, c2, k, ans = random.choice(combos)
        total = c1 + 2 * c2 + k
        q["question"] = (
            f"A dot plot records the number of pets for 10 families:\n"
            f"0 pets ({c0} dots), 1 pet ({c1} dots),\n"
            f"2 pets ({c2} dots), and {k} pets (1 dot).\n"
            f"Calculate the mean number of pets per family."
        )
        q["accepted_answers"] = [ans, f"{ans}0"]
        q["worked_solution"] = (
            f"Total pets = (0 × {c0}) + (1 × {c1}) + (2 × {c2}) + ({k} × 1) = {total}. "
            f"Mean = {total} ÷ 10 = {ans}."
        )

    elif qid == "data_450":
        base = random.randint(14, 22)
        n1, n2, n3, n4 = base - 4, base - 1, base + 2, base + 5
        mean_val = base + random.choice([1, 2, 3])
        total = 5 * mean_val
        known_sum = n1 + n2 + n3 + n4
        n5 = total - known_sum
        q["question"] = (
            f"A dataset containing 5 numbers has a mean of {mean_val}.\n"
            f"Four of the numbers are {n1}, {n2}, {n3}, and {n4}.\n"
            f"What is the 5th number?"
        )
        q["accepted_answers"] = [str(n5)]
        q["worked_solution"] = (
            f"Total of all 5 numbers = 5 × {mean_val} = {total}. "
            f"Sum of known 4 = {known_sum}. Missing number = {total} − {known_sum} = {n5}."
        )

    elif qid == "data_500":
        n = random.choice([5, 6, 7])
        w1 = random.choice([180, 200, 220, 240])
        w2 = w1 + random.choice([10, 15, 20])
        old_tot = n * w1
        new_tot = (n + 1) * w2
        ans = new_tot - old_tot
        q["question"] = (
            f"{n} tradies have a mean daily wage of ${w1}.\n"
            f"A {n + 1}th tradie joins the crew, and the new mean daily wage\n"
            f"for all {n + 1} tradies becomes ${w2}.\n"
            f"How much does the {n + 1}th tradie earn?"
        )
        q["accepted_answers"] = [str(ans), f"${ans}", f"{ans}.00", f"${ans}.00"]
        q["worked_solution"] = (
            f"Old Total = {n} × ${w1} = ${old_tot}. New Total = {n + 1} × ${w2} = ${new_tot}. "
            f"New Tradie = ${new_tot} − ${old_tot} = ${ans}."
        )

    elif qid == "data_550":
        n = random.choice([6, 8, 9])
        new_mean = random.randint(74, 85)
        diff = random.choice([4, 5, 6, 7])
        old_mean = new_mean - diff
        orig_sum = n * old_mean
        new_sum = (n - 1) * new_mean
        outlier = orig_sum - new_sum
        q["question"] = (
            f"{n} students score a mean of {old_mean} on a mathematics test.\n"
            f"When an outlier score of {outlier} is removed from the dataset,\n"
            f"what is the new mean of the remaining {n - 1} students?"
        )
        q["accepted_answers"] = [str(new_mean), f"{new_mean}.0"]
        q["worked_solution"] = (
            f"Original sum = {n} × {old_mean} = {orig_sum}. "
            f"New sum = {orig_sum} − {outlier} = {new_sum}. "
            f"New mean = {new_sum} ÷ {n - 1} = {new_mean}."
        )

    elif qid == "data_600":
        a = random.randint(4, 7)
        b = random.randint(a + 1, 9)
        med = random.randint(b + 2, 13)
        d = random.randint(med + 2, 16)
        mean_val = random.randint(med + 1, med + 3)
        y = 5 * mean_val - (a + b + med + d)
        if y <= d:
            mean_val += 2
            y = 5 * mean_val - (a + b + med + d)
        q["question"] = (
            f"Five positive integers in ascending order are: {a}, {b}, x, {d}, y.\n"
            f"The median of the dataset is {med} and the mean is {mean_val}.\n"
            f"Find the value of y."
        )
        q["accepted_answers"] = [str(y)]
        q["worked_solution"] = (
            f"3rd score is median so x = {med}. Total sum = 5 × {mean_val} = {5 * mean_val}. "
            f"y = {5 * mean_val} − ({a} + {b} + {med} + {d}) = {y}."
        )

    # --- 2. Geometric Reasoning & Shapes ---
    elif qid == "geo_150":
        ang = random.randint(52, 128)
        ans = 180 - ang
        q["question"] = (
            f"Two parallel lines are cut by a transversal.\n"
            f"One of the co-interior angles measures {ang}°.\n"
            f"What is the size of the other co-interior angle?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"Co-interior angles on parallel lines add to 180°. 180° − {ang}° = {ans}°."

    elif qid == "geo_200":
        a = random.randrange(46, 84, 2)
        b = random.randrange(40, 76, 2)
        ans = (360 - (a + b)) // 2
        q["question"] = (
            f"In a kite ABCD, the two unequal vertex angles\n"
            f"measure {a}° and {b}°.\n"
            f"What is the size of each of the two equal opposite angles?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = (
            f"Angle sum of a quadrilateral is 360°. Remaining sum = 360° − ({a}° + {b}°) = {360 - a - b}°. "
            f"Each equal angle = {360 - a - b}° ÷ 2 = {ans}°."
        )

    elif qid == "geo_250":
        a = random.randint(28, 42)
        b = random.randint(35, 50)
        c = random.randint(40, 55)
        ans = 360 - (a + b + c)
        q["question"] = (
            f"A non-convex (arrowhead) quadrilateral has three acute\n"
            f"interior angles measuring {a}°, {b}°, and {c}°.\n"
            f"What is the size of the fourth (reflex) interior angle?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"Reflex angle = 360° − ({a}° + {b}° + {c}°) = {ans}°."

    elif qid == "geo_300":
        ext = random.randint(115, 150)
        interior = random.randint(45, ext - 35)
        ans = ext - interior
        q["question"] = (
            f"An exterior angle of a triangle measures {ext}°.\n"
            f"One of the opposite interior angles is {interior}°.\n"
            f"What is the size of the other opposite interior angle?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"By the exterior angle theorem, {ext}° − {interior}° = {ans}°."

    elif qid == "geo_350":
        apex = random.randrange(32, 88, 2)
        ans = (180 - apex) // 2
        q["question"] = (
            f"Triangle ABC is isosceles with AB = AC.\n"
            f"The apex angle BAC measures {apex}°.\n"
            f"What is the size of the base angle ABC?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"Base angles are equal: (180° − {apex}°) ÷ 2 = {ans}°."

    elif qid == "geo_400":
        x_val = random.randint(36, 52)
        a = random.randint(6, 18)
        b = 180 - 3 * x_val - a
        q["question"] = (
            f"Two co-interior angles between parallel lines\n"
            f"measure (2x + {a})° and (x + {b})°.\n"
            f"Solve for x."
        )
        q["accepted_answers"] = [str(x_val), f"{x_val}°", f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = (
            f"(2x + {a}) + (x + {b}) = 180 → 3x + {a + b} = 180 → 3x = {3 * x_val} → x = {x_val}."
        )

    elif qid == "geo_450":
        top_ang = random.randint(32, 46)
        bot_ang = random.randint(48, 62)
        tot_ang = top_ang + bot_ang
        q["question"] = (
            f"Two parallel horizontal lines are joined by a V-shaped\n"
            f"bend pointing to the right. The top acute angle with the\n"
            f"parallel line is {top_ang}° and the bottom acute angle is {bot_ang}°.\n"
            f"What is the size of the angle at the tip of the bend?"
        )
        q["accepted_answers"] = [str(tot_ang), f"{tot_ang}°", f"{tot_ang} degrees", f"{tot_ang} deg"]
        q["worked_solution"] = f"By alternate angles on parallel lines, tip angle = {top_ang}° + {bot_ang}° = {tot_ang}°."

    elif qid == "geo_475":
        scenarios = [
            (
                "Two triangles both have side lengths of 6 cm, 8 cm, and 10 cm.\n"
                "Which congruence test proves they are congruent\n"
                "('SSS', 'SAS', 'AAS', or 'RHS')?",
                "sss",
                "All three pairs of corresponding sides are equal (Side-Side-Side, SSS)."
            ),
            (
                "Two triangles both have side lengths of 6 cm and 9 cm,\n"
                "with the included angle between those sides equal to 50°.\n"
                "Which congruence test proves they are congruent\n"
                "('SSS', 'SAS', 'AAS', or 'RHS')?",
                "sas",
                "Two pairs of matching sides and the included angle satisfy SAS."
            ),
            (
                "Two triangles both have angles of 45° and 70°,\n"
                "and a matching side of 8 cm opposite the 70° angle.\n"
                "Which congruence test proves they are congruent\n"
                "('SSS', 'SAS', 'AAS', or 'RHS')?",
                "aas",
                "Two matching angles and a corresponding side satisfy AAS."
            ),
            (
                "Two right-angled triangles both have a hypotenuse of 13 cm\n"
                "and one matching shorter side of 5 cm.\n"
                "Which congruence test proves they are congruent\n"
                "('SSS', 'SAS', 'AAS', or 'RHS')?",
                "rhs",
                "Right angle, matching hypotenuse, and one other matching side satisfy RHS."
            ),
        ]
        prompt, ans, sol = random.choice(scenarios)
        q["question"] = prompt
        q["accepted_answers"] = [ans]
        q["worked_solution"] = sol

    elif qid == "geo_500":
        x_val = random.randint(42, 54)
        a = random.randint(12, 24)
        b = random.randint(8, 18)
        c = 360 - 6 * x_val - a + b
        q["question"] = (
            f"The four interior angles of a quadrilateral are\n"
            f"x°, (x + {a})°, (2x − {b})°, and (2x + {c})°.\n"
            f"Find the value of x."
        )
        q["accepted_answers"] = [str(x_val), f"{x_val}°", f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = (
            f"6x + {a - b + c} = 360 → 6x = {6 * x_val} → x = {x_val}."
        )

    elif qid == "geo_550":
        scale = random.choice([2, 3, 4])
        ae = random.randint(4, 7)
        ab = ae * scale
        ad = random.randint(5, 9)
        ac = ad * scale
        q["question"] = (
            f"Triangle ABC is similar to Triangle AED (with DE parallel to BC).\n"
            f"If AE = {ae} cm, AB = {ab} cm, and AD = {ad} cm,\n"
            f"how long is the full side AC (in cm)?"
        )
        q["accepted_answers"] = [str(ac), f"{ac}cm", f"{ac} cm"]
        q["worked_solution"] = f"Scale factor = {ab} ÷ {ae} = {scale}. Side AC = {ad} × {scale} = {ac} cm."

    elif qid == "geo_600":
        triples = [(6, 8, 10), (8, 15, 17), (5, 12, 13), (9, 12, 15)]
        leg1, leg2, hyp = random.choice(triples)
        d1 = leg1 * 2
        d2 = leg2 * 2
        perim = 4 * hyp
        q["question"] = (
            f"The diagonals of a rhombus measure {d1} cm and {d2} cm.\n"
            f"Since the diagonals bisect each other at 90°, they form\n"
            f"four right-angled triangles with legs {leg1} cm and {leg2} cm.\n"
            f"Find the PERIMETER of the rhombus."
        )
        q["accepted_answers"] = [str(perim), f"{perim}cm", f"{perim} cm"]
        q["worked_solution"] = f"Side = √({leg1}² + {leg2}²) = {hyp} cm. Perimeter = 4 × {hyp} = {perim} cm."

    # --- 3. Area, Volume & Surface Area ---
    elif qid == "meas_100":
        b = random.randrange(6, 16, 2)
        h = random.randint(5, 11)
        ans = (b * h) // 2
        q["question"] = (
            f"In a right-angled triangle, perpendicular height AB = {h} cm\n"
            f"and base BC = {b} cm.\n"
            f"Calculate the area of the triangle (in cm²)."
        )
        q["accepted_answers"] = [str(ans), f"{ans}cm2", f"{ans} cm2", f"{ans}cm²"]
        q["worked_solution"] = f"Area = ½ × {b} × {h} = {ans} cm²."

    elif qid == "meas_150":
        s = random.randint(3, 7)
        k = random.choice([2, 3, 4])
        ans = (s * k) ** 2
        q["question"] = (
            f"A square has a side length of {s} m.\n"
            f"A second square has a perimeter {k} times as large.\n"
            f"What is the AREA of the second square (in m²)?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}m2", f"{ans} m2", f"{ans}m²"]
        q["worked_solution"] = f"Second square side = {k} × {s} = {k * s} m. Area = {k * s}² = {ans} m²."

    elif qid == "meas_200":
        d1 = random.randrange(8, 18, 2)
        d2 = random.randint(5, 13)
        ans = (d1 * d2) // 2
        q["question"] = (
            f"A kite has diagonals of length {d1} cm and {d2} cm.\n"
            f"Calculate the area of the kite (in cm²)."
        )
        q["accepted_answers"] = [str(ans), f"{ans}cm2", f"{ans} cm2", f"{ans}cm²"]
        q["worked_solution"] = f"Area = ½ × {d1} × {d2} = {ans} cm²."

    elif qid == "meas_250":
        length = random.randint(6, 12)
        width = random.randint(3, 6)
        depth = random.randint(2, 3)
        ans = length * width * depth
        q["question"] = (
            f"A rectangular swimming pool is {length} m long, {width} m wide,\n"
            f"and {depth} m deep. Given that 1 m³ = 1 kilolitre (1000 L),\n"
            f"how many kilolitres (kL) of water does the full pool hold?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}kl", f"{ans} kl", f"{ans}m3", f"{ans}m³"]
        q["worked_solution"] = f"Volume = {length} × {width} × {depth} = {ans} m³ = {ans} kL."

    elif qid == "meas_300":
        length = random.randint(7, 12)
        width = random.randint(4, 6)
        height = random.randint(2, 4)
        ans = 2 * (length * width + length * height + width * height)
        q["question"] = (
            f"A rectangular shipping crate is {length} m long, {width} m wide, and {height} m high.\n"
            f"What is the total surface area of the prism (in m²)?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}m2", f"{ans} m2", f"{ans}m²"]
        q["worked_solution"] = (
            f"Surface Area = 2 × ({length}×{width} + {length}×{height} + {width}×{height}) = {ans} m²."
        )

    elif qid == "meas_350":
        w = random.randint(3, 5)
        l = random.randint(6, 9)
        k = random.choice([2, 3, 4])
        ans = (w * k) * (l * k)
        q["question"] = (
            f"Two similar rectangles have a scale factor of k={k}.\n"
            f"The small rectangle has a width of w={w} cm and length of l={l} cm.\n"
            f"What is the AREA of the large rectangle (in cm²)?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}cm2", f"{ans} cm2", f"{ans}cm²"]
        q["worked_solution"] = f"Large width = {w * k} cm, Large length = {l * k} cm. Area = {ans} cm²."

    elif qid == "meas_400":
        gl = random.randint(10, 14)
        gw = random.randint(6, 9)
        pw = random.choice([1, 2])
        out_l = gl + 2 * pw
        out_w = gw + 2 * pw
        ans = (out_l * out_w) - (gl * gw)
        q["question"] = (
            f"A rectangular garden measures l={gl} m by w={gw} m.\n"
            f"A uniform path {pw} m wide is built all the way around\n"
            f"the OUTSIDE of the garden.\n"
            f"What is the area of the path alone (in m²)?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}m2", f"{ans} m2", f"{ans}m²"]
        q["worked_solution"] = f"Outer = {out_l} × {out_w} = {out_l * out_w} m². Garden = {gl * gw} m². Path = {ans} m²."

    elif qid == "meas_500":
        h = random.choice([4, 6, 8, 10])
        a = random.randint(5, 10)
        b = random.randint(a + 2, 16)
        area = (h * (a + b)) // 2
        q["question"] = (
            f"A trapezium has an area of {area} cm² and a perpendicular\n"
            f"height of {h} cm. One of its parallel sides is {a} cm long.\n"
            f"Find the length of the other parallel side (in cm)."
        )
        q["accepted_answers"] = [str(b), f"{b}cm", f"{b} cm"]
        q["worked_solution"] = (
            f"A = ½ × h × (a + b) → {area} = ½ × {h} × ({a} + b) → b = {b} cm."
        )

    elif qid == "meas_550":
        area = random.randint(10, 18)
        depth = random.randint(6, 14)
        ans = area * depth
        q["question"] = (
            f"A triangular prism has a front triangular face with an area of\n"
            f"A={area} m², and a total length (depth) of d={depth} m.\n"
            f"What is the volume of the prism (in m³)?\n"
            f"(Use the formula V = A × h)"
        )
        q["accepted_answers"] = [str(ans), f"{ans}m3", f"{ans} m3", f"{ans}m³"]
        q["worked_solution"] = f"Volume = {area} × {depth} = {ans} m³."

    # --- 4. Algebra & Equations ---
    elif qid == "alg_100":
        a = random.randint(3, 7)
        x_val = random.randint(5, 12)
        b = random.randint(4, 15)
        c = a * x_val - b
        q["question"] = f"Solve for x:\n{a}x − {b} = {c}"
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = f"{a}x − {b} = {c} → {a}x = {a * x_val} → x = {x_val}."

    elif qid == "alg_150":
        div = random.randint(3, 6)
        quot = random.randint(5, 11)
        b = random.randint(4, 12)
        c = quot + b
        m_val = div * quot
        q["question"] = f"Solve for m:\n(m ÷ {div}) + {b} = {c}"
        q["accepted_answers"] = [str(m_val), f"m={m_val}", f"m = {m_val}"]
        q["worked_solution"] = f"(m ÷ {div}) + {b} = {c} → m ÷ {div} = {quot} → m = {m_val}."

    elif qid == "alg_200":
        x_sub = random.randint(4, 9)
        c_coeff = random.randint(3, 5)
        d_const = random.randint(2, 9)
        rhs = c_coeff * x_sub + d_const
        q["question"] = (
            f"To check if x = {x_sub} is the correct solution to\n"
            f"5(x − 2) = {c_coeff}x + {d_const}, you substitute x = {x_sub} into both sides.\n"
            f"What is the numerical value of the Right-Hand Side (RHS)?"
        )
        q["accepted_answers"] = [str(rhs), f"rhs={rhs}"]
        q["worked_solution"] = f"RHS = {c_coeff}({x_sub}) + {d_const} = {rhs}."

    elif qid == "alg_250":
        a = random.randint(2, 4)
        b = random.randint(2, 3)
        x_val = random.randint(5, 11)
        c = random.randint(3, 9)
        d = a * (b * x_val - c)
        q["question"] = f"Solve for x:\n{a}({b}x − {c}) = {d}"
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = f"{b}x − {c} = {d // a} → {b}x = {b * x_val} → x = {x_val}."

    elif qid == "alg_300":
        c = random.randint(2, 4)
        diff = random.randint(3, 5)
        a = c + diff
        x_val = random.randint(5, 12)
        b = random.randint(3, 12)
        d = diff * x_val - b
        q["question"] = f"Solve for x:\n{a}x − {b} = {c}x + {d}"
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = f"{diff}x − {b} = {d} → {diff}x = {diff * x_val} → x = {x_val}."

    elif qid == "alg_350":
        x_val = random.randint(11, 24)
        y_val = 2 * x_val + 2
        q["question"] = (
            f"The straight line on the grid passes through (0, 2) and (3, 8),\n"
            f"following the linear rule y = 2x + 2.\n"
            f"Use this equation to find the value of x when y = {y_val}."
        )
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = f"Substitute y = {y_val}: 2x + 2 = {y_val} → 2x = {2 * x_val} → x = {x_val}."

    elif qid == "alg_400":
        x_val = random.randint(12, 24)
        a = random.randint(7, 17)
        b = 2 * x_val - a
        q["question"] = (
            f"Let x be an unknown number.\n"
            f"When x is tripled and then decreased by {a},\n"
            f"the result is equal to x increased by {b}.\n"
            f"Find the value of x."
        )
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = f"3x − {a} = x + {b} → 2x = {a + b} → x = {x_val}."

    elif qid == "alg_450":
        a = random.randint(2, 5)
        x_val = random.randint(5, 12)
        b = random.randint(3, 11)
        c = random.randint(3, 6)
        prod = a * x_val + b
        rem = prod % c
        if rem != 0:
            b += (c - rem)
            prod = a * x_val + b
        d = prod // c
        q["question"] = f"Solve for x:\n({a}x + {b}) ÷ {c} = {d}"
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = f"Multiply by {c}: {a}x + {b} = {prod} → {a}x = {a * x_val} → x = {x_val}."

    elif qid == "alg_500":
        a = random.choice([4, 5, 6])
        x_val = random.randint(4, 11)
        b = random.randint(2, 6)
        rhs = a * (x_val + b) - 2 * (x_val - 1)
        q["question"] = f"Expand and simplify to solve for x:\n{a}(x + {b}) − 2(x − 1) = {rhs}"
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}"]
        q["worked_solution"] = (
            f"{a}x + {a * b} − 2x + 2 = {rhs} → {a - 2}x + {a * b + 2} = {rhs} → x = {x_val}."
        )

    elif qid == "alg_550":
        x_val = random.randrange(15, 35, 2)
        total = 3 * x_val + 6
        largest = x_val + 4
        q["question"] = (
            f"The sum of three consecutive odd numbers is {total}.\n"
            f"Let the smallest number be x, so the next two are\n"
            f"(x + 2) and (x + 4).\n"
            f"What is the LARGEST of the three numbers?"
        )
        q["accepted_answers"] = [str(largest)]
        q["worked_solution"] = (
            f"3x + 6 = {total} → 3x = {3 * x_val} → x = {x_val}. Largest = {x_val} + 4 = {largest}."
        )

    # --- 5. Extended NSW Stage 4 Dynamic Parameterisation ---
    elif qid == "data_125":
        mode_val = random.randint(2, 9)
        others = [v for v in range(2, 11) if v != mode_val]
        d1, d2, d3, d4 = random.sample(others, 4)
        vals = [mode_val, mode_val, mode_val, d1, d1, d2, d3, d4]
        random.shuffle(vals)
        q["question"] = f"Find the mode of the following dataset:\n{', '.join(map(str, vals))}"
        q["accepted_answers"] = [str(mode_val)]
        q["worked_solution"] = f"The number {mode_val} appears 3 times, more frequently than any other value."

    elif qid == "data_175":
        lo = random.randint(8, 15)
        hi = random.randint(28, 39)
        mids = random.sample(range(lo + 2, hi - 1), 4)
        vals = [lo, hi] + mids
        random.shuffle(vals)
        ans = hi - lo
        q["question"] = (
            f"Find the range of the following daily maximum\n"
            f"temperatures (in °C):\n"
            f"{', '.join(map(str, vals))}"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans}°c"]
        q["worked_solution"] = f"Range = {hi} − {lo} = {ans}."

    elif qid == "data_225":
        s1 = random.randint(8, 13)
        s2 = s1 + random.randint(2, 4)
        s3 = s2 + random.randint(2, 4)
        s4 = s3 + random.randint(2, 5)
        s5 = s4 + random.randint(2, 4)
        s6 = s5 + random.randint(2, 4)
        s7 = s6 + random.randint(2, 5)
        vals = [s1, s2, s3, s4, s5, s6, s7]
        random.shuffle(vals)
        q["question"] = f"Find the median of the following 7 scores:\n{', '.join(map(str, vals))}"
        q["accepted_answers"] = [str(s4)]
        q["worked_solution"] = f"Ordered: {', '.join(map(str, [s1, s2, s3, s4, s5, s6, s7]))}. Middle (4th) score = {s4}."

    elif qid == "data_275":
        mean_val = random.randint(64, 84)
        step = random.choice([3, 4, 5])
        vals = [mean_val - 2 * step, mean_val - step, mean_val, mean_val + step, mean_val + 2 * step]
        random.shuffle(vals)
        q["question"] = f"Calculate the mean of these 5 test scores:\n{', '.join(map(str, vals))}"
        q["accepted_answers"] = [str(mean_val), f"{mean_val}.0"]
        q["worked_solution"] = f"Sum = {5 * mean_val}. Mean = {5 * mean_val} ÷ 5 = {mean_val}."

    elif qid == "data_325":
        s1, f1, s2, f2, s3, f3, ans_s = random.choice([
            (1, 2, 2, 4, 5, 4, "3"),
            (1, 2, 2, 2, 4, 6, "3"),
            (1, 4, 2, 2, 4, 4, "2.4"),
            (1, 2, 3, 4, 5, 4, "3.4"),
            (2, 2, 3, 4, 5, 4, "3.6"),
            (1, 3, 2, 2, 5, 5, "3.2"),
        ])
        tot_s = s1 * f1 + s2 * f2 + s3 * f3
        q["question"] = (
            f"A frequency table shows quiz scores out of 5:\n"
            f"Score {s1} (freq {f1}), Score {s2} (freq {f2}), Score {s3} (freq {f3}).\n"
            f"Calculate the mean score."
        )
        q["accepted_answers"] = [ans_s, f"{ans_s}.0" if "." not in ans_s else f"{ans_s}0"]
        q["worked_solution"] = f"Total score = {tot_s}, total frequency = 10. Mean = {tot_s} ÷ 10 = {ans_s}."

    elif qid == "data_425":
        m1 = random.randint(64, 78)
        diff = random.choice([5, 10, 15])
        m2 = m1 + diff
        comb = m1 + (8 * diff) // 20
        q["question"] = (
            f"Class A (12 students) has a mean test score of {m1}.\n"
            f"Class B (8 students) has a mean test score of {m2}.\n"
            f"What is the combined mean for all 20 students?"
        )
        q["accepted_answers"] = [str(comb), f"{comb}.0"]
        q["worked_solution"] = f"Total = (12 × {m1}) + (8 × {m2}) = {12 * m1 + 8 * m2}. Mean = {12 * m1 + 8 * m2} ÷ 20 = {comb}."

    elif qid == "geo_125":
        ang = random.randint(18, 72)
        ans = 90 - ang
        q["question"] = (
            f"Two angles are complementary (they add to 90°).\n"
            f"If one angle measures {ang}°,\n"
            f"what is the size of the other angle?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"90° − {ang}° = {ans}°."

    elif qid == "geo_175":
        a = random.randint(32, 62)
        b = random.randint(45, 78)
        ans = 180 - a - b
        q["question"] = (
            f"Three angles lie along a straight line (180°).\n"
            f"They measure {a}°, x°, and {b}°.\n"
            f"Find the value of x."
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"x={ans}"]
        q["worked_solution"] = f"x = 180 − ({a} + {b}) = {ans}°."

    elif qid == "geo_225":
        a = random.randint(75, 120)
        b = random.randint(65, 105)
        c = random.randint(60, 95)
        ans = 360 - a - b - c
        q["question"] = (
            f"Four angles meet at a single point (a full revolution).\n"
            f"Three of the angles measure {a}°, {b}°, and {c}°.\n"
            f"What is the size of the fourth angle?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"360° − ({a}° + {b}° + {c}°) = {ans}°."

    elif qid == "geo_275":
        a = random.randint(36, 74)
        b = random.randint(40, 74)
        ans = 180 - a - b
        q["question"] = (
            f"Two interior angles of a triangle measure {a}° and {b}°.\n"
            f"What is the size of the third interior angle?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"180° − ({a}° + {b}°) = {ans}°."

    elif qid == "geo_325":
        ang = random.randint(38, 82)
        ans = 180 - ang
        q["question"] = (
            f"Two parallel lines are cut by a transversal.\n"
            f"One of the acute angles formed measures {ang}°.\n"
            f"What is the size of each obtuse angle formed?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"180° − {ang}° = {ans}°."

    elif qid == "geo_375":
        name, n = random.choice([
            ("pentagon", 5), ("hexagon", 6), ("heptagon", 7), ("octagon", 8), ("decagon", 10)
        ])
        ans = (n - 2) * 180
        q["question"] = (
            f"Using the formula S = 180 × (n − 2),\n"
            f"calculate the interior angle sum of a {name} ({n} sides)."
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"S = 180 × ({n} − 2) = {ans}°."

    elif qid == "geo_425":
        name, n, ans = random.choice([
            ("pentagon", 5, 108), ("hexagon", 6, 120), ("octagon", 8, 135),
            ("nonagon", 9, 140), ("decagon", 10, 144), ("dodecagon", 12, 150)
        ])
        q["question"] = (
            f"Calculate the size of ONE interior angle\n"
            f"of a regular {name} ({n} equal sides and angles)."
        )
        q["accepted_answers"] = [str(ans), f"{ans}°", f"{ans} degrees", f"{ans} deg"]
        q["worked_solution"] = f"Angle sum = {(n - 2) * 180}°. Each angle = {(n - 2) * 180}° ÷ {n} = {ans}°."

    elif qid == "meas_125":
        km_tenths = random.randint(12, 88)
        km_val = km_tenths / 10.0
        ans = km_tenths * 100
        q["question"] = f"Convert {km_val:.1f} kilometres (km) into metres (m)."
        q["accepted_answers"] = [str(ans), f"{ans}m", f"{ans} m"]
        q["worked_solution"] = f"{km_val:.1f} × 1000 = {ans} m."

    elif qid == "meas_175":
        b = random.randint(7, 15)
        h = random.randint(4, 10)
        slanted = h + random.randint(2, 4)
        ans = b * h
        q["question"] = (
            f"A parallelogram has a base of {b} cm, a slanted side\n"
            f"of {slanted} cm, and a perpendicular height of {h} cm.\n"
            f"Calculate its area (in cm²)."
        )
        q["accepted_answers"] = [str(ans), f"{ans}cm2", f"{ans} cm2", f"{ans}cm²"]
        q["worked_solution"] = f"Area = base × perpendicular height = {b} × {h} = {ans} cm²."

    elif qid == "meas_225":
        w = random.randint(5, 12)
        l = w + random.randint(4, 10)
        p = 2 * (l + w)
        q["question"] = (
            f"A rectangle has a perimeter of {p} cm\n"
            f"and a length of {l} cm.\n"
            f"What is the width of the rectangle (in cm)?"
        )
        q["accepted_answers"] = [str(w), f"{w}cm", f"{w} cm"]
        q["worked_solution"] = f"2w = {p} − {2 * l} = {2 * w} → w = {w} cm."

    elif qid == "meas_275":
        a = random.randint(5, 11)
        b = a + random.randrange(4, 12, 2)
        h = random.choice([4, 6, 8, 10])
        ans = ((a + b) * h) // 2
        q["question"] = (
            f"A trapezium has parallel sides of {a} cm and {b} cm,\n"
            f"and a perpendicular height of {h} cm.\n"
            f"Calculate the area of the trapezium (in cm²)."
        )
        q["accepted_answers"] = [str(ans), f"{ans}cm2", f"{ans} cm2", f"{ans}cm²"]
        q["worked_solution"] = f"Area = ½ × ({a} + {b}) × {h} = {ans} cm²."

    elif qid == "meas_325":
        d = random.randint(8, 24)
        ans = int(round(math.pi * d))
        q["question"] = (
            f"Calculate the circumference of a circle with a diameter\n"
            f"of {d} cm, rounded to the nearest whole number (in cm).\n"
            f"(Use C = π × d)"
        )
        q["accepted_answers"] = [str(ans), f"{ans}cm", f"{ans} cm"]
        q["worked_solution"] = f"C = π × {d} ≈ {math.pi * d:.2f} cm → {ans} cm."

    elif qid == "meas_375":
        start_h = random.randint(9, 15)
        start_m = random.choice([10, 15, 20, 25, 35, 40, 45])
        dur = random.choice([95, 115, 135, 145, 165, 175, 195])
        end_h, end_m = divmod(start_h * 60 + start_m + dur, 60)
        q["question"] = (
            f"A train departs Central Station at {start_h:02d}:{start_m:02d}\n"
            f"and arrives at its destination at {end_h:02d}:{end_m:02d}.\n"
            f"How many minutes did the journey take?"
        )
        q["accepted_answers"] = [str(dur), f"{dur} mins", f"{dur} min", f"{dur} minutes"]
        q["worked_solution"] = f"Elapsed time from {start_h:02d}:{start_m:02d} to {end_h:02d}:{end_m:02d} is {dur} minutes."

    elif qid == "meas_475":
        r = random.randint(3, 7)
        h = random.randint(6, 14)
        vol = math.pi * r * r * h
        ans = int(round(vol))
        ans_314 = int(round(3.14 * r * r * h))
        q["question"] = (
            f"A cylinder has a radius of {r} cm and a height of {h} cm.\n"
            f"Calculate its volume (in cm³), rounded to the nearest\n"
            f"whole number. (Use V = π × r² × h and the π button)"
        )
        accepted = [str(ans), f"{ans}cm3", f"{ans} cm3", f"{ans}cm³"]
        if ans_314 != ans:
            accepted.extend([str(ans_314), f"{ans_314}cm3", f"{ans_314} cm3", f"{ans_314}cm³"])
        q["accepted_answers"] = accepted
        q["worked_solution"] = f"V = π × {r}² × {h} ≈ {vol:.2f} cm³ → {ans} cm³."

    elif qid == "meas_525":
        m2_tenths = random.randint(15, 75)
        m2_val = m2_tenths / 10.0
        ans = m2_tenths * 1000
        q["question"] = (
            f"Convert an area of {m2_val:.1f} m² into square centimetres (cm²).\n"
            f"(Remember: 1 m = 100 cm)"
        )
        q["accepted_answers"] = [str(ans), f"{ans}cm2", f"{ans} cm2"]
        q["worked_solution"] = f"1 m² = 10 000 cm². {m2_val:.1f} × 10 000 = {ans} cm²."

    elif qid == "alg_125":
        a = random.randint(2, 5)
        b = random.randint(2, 5)
        x_val = random.randint(2, 7)
        y_abs = random.randint(2, 7)
        ans = a * x_val + b * y_abs
        q["question"] = f"Evaluate {a}x − {b}y when x = {x_val} and y = −{y_abs}."
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{a}({x_val}) − {b}(−{y_abs}) = {a * x_val} + {b * y_abs} = {ans}."

    elif qid == "alg_175":
        a1 = random.randint(5, 11)
        a2 = random.randint(2, a1 - 2)
        b1 = random.randint(2, 7)
        b2 = random.randint(2, 7)
        ca = a1 - a2
        cb = b1 + b2
        q["question"] = f"Simplify by collecting like terms:\n{a1}a + {b1}b − {a2}a + {b2}b"
        q["accepted_answers"] = [f"{ca}a+{cb}b", f"{ca}a + {cb}b", f"{cb}b+{ca}a", f"{cb}b + {ca}a"]
        q["worked_solution"] = f"({a1}a − {a2}a) + ({b1}b + {b2}b) = {ca}a + {cb}b."

    elif qid == "alg_225":
        k = random.randint(2, 6)
        a = random.randint(2, 5)
        b = random.randint(2, 7)
        ka, kb = k * a, k * b
        q["question"] = f"Expand the brackets:\n{k}({a}x − {b})"
        q["accepted_answers"] = [f"{ka}x-{kb}", f"{ka}x - {kb}"]
        q["worked_solution"] = f"{k} × {a}x − {k} × {b} = {ka}x − {kb}."

    elif qid == "alg_275":
        hcf = random.randint(3, 7)
        a, b = random.choice([(2, 3), (2, 5), (3, 4), (3, 5), (4, 5)])
        c1, c2 = hcf * a, hcf * b
        q["question"] = f"Factorise completely using the highest common factor:\n{c1}x + {c2}"
        q["accepted_answers"] = [
            f"{hcf}({a}x+{b})", f"{hcf}({a}x + {b})",
            f"{hcf}({b}+{a}x)", f"{hcf}({b} + {a}x)"
        ]
        q["worked_solution"] = f"HCF of {c1} and {c2} is {hcf}. Factorised: {hcf}({a}x + {b})."

    elif qid == "alg_325":
        q_num = random.choice([1, 2, 3, 4])
        xr = random.randint(2, 9)
        yr = random.randint(2, 9)
        if q_num == 1:
            pt = f"({xr}, {yr})"
            roman = "i"
            word = "first"
        elif q_num == 2:
            pt = f"(−{xr}, {yr})"
            roman = "ii"
            word = "second"
        elif q_num == 3:
            pt = f"(−{xr}, −{yr})"
            roman = "iii"
            word = "third"
        else:
            pt = f"({xr}, −{yr})"
            roman = "iv"
            word = "fourth"
        q["question"] = (
            f"On the Cartesian plane, in which quadrant\n"
            f"(1, 2, 3, or 4) does the point {pt} lie?"
        )
        q["accepted_answers"] = [str(q_num), roman, word, f"quadrant {q_num}", f"q{q_num}"]
        q["worked_solution"] = f"The signs of {pt} place it in Quadrant {q_num}."

    elif qid == "alg_375":
        x1 = random.randrange(-8, 4, 2)
        x2 = random.randrange(6, 16, 2)
        y1 = random.randint(1, 7)
        y2 = random.randint(3, 11)
        mx = (x1 + x2) // 2
        x1_s = f"−{abs(x1)}" if x1 < 0 else str(x1)
        q["question"] = (
            f"Find the x-coordinate of the midpoint\n"
            f"of the interval joining ({x1_s}, {y1}) and ({x2}, {y2})."
        )
        q["accepted_answers"] = [str(mx), f"x={mx}", f"x = {mx}"]
        q["worked_solution"] = f"Midpoint x = ({x1_s} + {x2}) ÷ 2 = {mx}."

    elif qid == "alg_425":
        x1 = random.randint(1, 4)
        run = random.randint(2, 5)
        m = random.randint(2, 5)
        y1 = random.randint(1, 6)
        x2 = x1 + run
        y2 = y1 + m * run
        q["question"] = (
            f"A straight line passes through ({x1}, {y1}) and ({x2}, {y2}).\n"
            f"Calculate the gradient (m = rise ÷ run) of this line."
        )
        q["accepted_answers"] = [str(m), f"m={m}", f"m = {m}"]
        q["worked_solution"] = f"Rise = {y2} − {y1} = {m * run}. Run = {x2} − {x1} = {run}. m = {m}."

    elif qid == "alg_525":
        x_val = random.randint(4, 11)
        b = random.randint(2, 6)
        perim = 2 * (3 * x_val + b)
        q["question"] = (
            f"A rectangle has length (2x + {b}) cm and width x cm.\n"
            f"If its total perimeter is {perim} cm,\n"
            f"find the value of x."
        )
        q["accepted_answers"] = [str(x_val), f"x={x_val}", f"x = {x_val}", f"{x_val}cm"]
        q["worked_solution"] = f"2(3x + {b}) = {perim} → 6x + {2 * b} = {perim} → x = {x_val}."

    elif qid == "int_100":
        a = random.randint(4, 12)
        b = random.randint(10, 18)
        c = random.randint(6, 15)
        ans = -a + b - c
        q["question"] = f"Evaluate:\n−{a} + {b} − {c}"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"−{a} + {b} = {-a + b}, then {-a + b} − {c} = {ans}."

    elif qid == "int_150":
        a = random.randint(4, 15)
        b = random.randint(6, 19)
        ans = a + b
        q["question"] = f"Evaluate:\n{a} − (−{b})"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{a} − (−{b}) = {a} + {b} = {ans}."

    elif qid == "int_200":
        d = random.randint(2, 5)
        a = random.randint(2, 5) * d
        b = random.randint(3, 9)
        ans = -(a * b // d)
        q["question"] = f"Evaluate:\n(−{a}) × (−{b}) ÷ (−{d})"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"(−{a}) × (−{b}) = {a * b}. {a * b} ÷ (−{d}) = {ans}."

    elif qid == "int_250":
        a = random.randint(3, 10)
        b = random.randint(2, 5)
        c = random.randint(4, 9)
        d = random.choice([2, 3, 4])
        e = d * random.randint(2, 5)
        ans = a + b * c - (e // d)
        q["question"] = f"Using the order of operations (BIDMAS), evaluate:\n{a} + {b} × {c} − {e} ÷ {d}"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{a} + {b * c} − {e // d} = {ans}."

    elif qid == "int_300":
        start = random.randint(2, 7)
        rise = random.randint(9, 16)
        drop = random.randint(10, 18)
        ans = -start + rise - drop
        q["question"] = (
            f"At midnight in Thredbo the temperature was −{start}°C.\n"
            f"By midday it rose by {rise}°C, then dropped {drop}°C by evening.\n"
            f"What was the evening temperature (in °C)?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}°c", f"{ans}°"]
        q["worked_solution"] = f"−{start} + {rise} − {drop} = {ans}°C."

    elif qid == "int_350":
        a = random.randint(2, 5)
        diff = random.randint(3, 5)
        y = random.randint(2, 6)
        x = y + diff
        c = random.randint(5, 16)
        ans = a * (diff ** 2) - c
        q["question"] = f"Evaluate using the order of operations:\n{a} × ({x} − {y})² − {c}"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{a} × {diff}² − {c} = {a * diff * diff} − {c} = {ans}."

    elif qid == "int_400":
        a = random.randint(3, 6)
        b = random.randint(2, 3)
        ans = (a ** 2) + ((-b) ** 3)
        q["question"] = f"Evaluate:\n(−{a})² + (−{b})³"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"(−{a})² = {a * a} and (−{b})³ = {-b ** 3}. Total = {ans}."

    elif qid == "int_450":
        start = random.randint(90, 160)
        rate = random.choice([20, 25, 30, 35])
        mins = random.randint(3, 5)
        rise = random.randint(50, 110)
        ans = -start - rate * mins + rise
        q["question"] = (
            f"A submarine is at an elevation of −{start} m.\n"
            f"It dives {rate} m per minute for {mins} minutes,\n"
            f"then rises {rise} m. What is its new elevation\n"
            f"(in m, include the − sign)?"
        )
        q["accepted_answers"] = [str(ans), f"{ans}m", f"{ans} m"]
        q["worked_solution"] = f"−{start} − ({rate} × {mins}) + {rise} = {ans} m."

    elif qid == "int_500":
        q_val = random.randint(3, 7)
        diff = random.randint(2, 4)
        x = random.randint(4, 9)
        y = x + diff
        num = q_val * diff
        a = random.randint(2, 5)
        b = random.randint(3, 7)
        ans = (q_val ** 2) + a * b
        q["question"] = f"Evaluate:\n[−{num} ÷ ({x} − {y})]² − {a} × (−{b})"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"[−{num} ÷ (−{diff})]² + {a * b} = {q_val}² + {a * b} = {ans}."

    elif qid == "int_550":
        c_pts = random.choice([4, 5])
        w_pts = random.choice([2, 3])
        corr = random.randint(10, 18)
        wrong = random.randint(3, 8)
        ans = corr * c_pts - wrong * w_pts
        q["question"] = (
            f"In a maths quiz, a correct answer scores +{c_pts} points\n"
            f"and a wrong answer scores −{w_pts} points.\n"
            f"If Sam gets {corr} correct and {wrong} wrong, what is Sam's total score?"
        )
        q["accepted_answers"] = [str(ans), f"{ans} pts", f"{ans} points"]
        q["worked_solution"] = f"{corr} × {c_pts} − {wrong} × {w_pts} = {ans}."

    elif qid == "int_600":
        big = random.randint(3, 7)
        small = -(big + random.randint(2, 6))
        prod = big * small
        s = big + small
        q["question"] = (
            f"Two integers have a product of −{abs(prod)} and a sum of −{abs(s)}.\n"
            f"What is the SMALLER (more negative) of the two integers?"
        )
        q["accepted_answers"] = [str(small)]
        q["worked_solution"] = f"The integers are {small} and {big}. The smaller is {small}."

    elif qid == "fdp_100":
        n, d = random.choice([(2, 3), (3, 4), (2, 5), (3, 5), (4, 5), (5, 6), (3, 7), (5, 8)])
        k = random.randint(3, 7)
        q["question"] = f"Write the fraction {n * k}/{d * k} in its simplest form."
        q["accepted_answers"] = [f"{n}/{d}"]
        q["worked_solution"] = f"Divide top and bottom by {k} → {n}/{d}."

    elif qid == "fdp_150":
        n, d = random.choice([(2, 3), (3, 4), (2, 5), (3, 5), (4, 5), (5, 6), (3, 8), (5, 8)])
        mult = random.randint(7, 19)
        qty = d * mult
        ans = n * mult
        q["question"] = f"Calculate {n}/{d} of {qty}."
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{qty} ÷ {d} = {mult}, then {mult} × {n} = {ans}."

    elif qid == "fdp_200":
        pct = random.choice([10, 15, 20, 25, 30, 35, 40])
        amt = random.choice([120, 160, 200, 240, 300, 400])
        ans = (pct * amt) // 100
        q["question"] = f"Calculate {pct}% of ${amt}."
        q["accepted_answers"] = [str(ans), f"${ans}", f"{ans}.00", f"${ans}.00"]
        q["worked_solution"] = f"({pct} ÷ 100) × ${amt} = ${ans}."

    elif qid == "fdp_250":
        n, d = random.choice([
            (3, 20), (7, 20), (9, 20), (11, 20), (13, 20), (17, 20),
            (7, 25), (9, 25), (12, 25), (16, 25), (19, 25), (3, 10), (7, 10)
        ])
        ans = (n * 100) // d
        q["question"] = f"Convert the fraction {n}/{d} into a percentage."
        q["accepted_answers"] = [f"{ans}%", str(ans)]
        q["worked_solution"] = f"({n}/{d}) × 100% = {ans}%."

    elif qid == "fdp_300":
        n1, d1, n2, d2 = random.choice([
            (2, 3, 1, 4), (1, 3, 1, 4), (2, 5, 1, 3),
            (3, 5, 1, 4), (1, 2, 2, 5), (1, 3, 2, 5), (3, 4, 1, 5)
        ])
        num = n1 * d2 + n2 * d1
        den = d1 * d2
        g = math.gcd(num, den)
        rn, rd = num // g, den // g
        q["question"] = f"Calculate {n1}/{d1} + {n2}/{d2}.\nWrite your answer as a simplified fraction."
        q["accepted_answers"] = [f"{rn}/{rd}"]
        q["worked_solution"] = f"{n1 * d2}/{den} + {n2 * d1}/{den} = {rn}/{rd}."

    elif qid == "fdp_350":
        pct = random.choice([15, 20, 25, 30])
        orig = random.choice([80, 120, 160, 200, 240])
        disc = (orig * pct) // 100
        sale = orig - disc
        q["question"] = f"A ${orig} pair of sneakers is discounted by {pct}%.\nWhat is the sale price?"
        q["accepted_answers"] = [str(sale), f"${sale}", f"{sale}.00", f"${sale}.00"]
        q["worked_solution"] = f"Discount = ${disc}. Sale price = ${orig} − ${disc} = ${sale}."

    elif qid == "fdp_400":
        orig = random.choice([45, 55, 65, 75, 85, 95, 115, 125])
        gst = orig * 0.1
        final = orig + gst
        q["question"] = f"A skateboard costs ${orig} before GST.\nIf 10% GST is added, what is the final price?"
        q["accepted_answers"] = [f"{final:.1f}", f"{final:.2f}", f"${final:.1f}", f"${final:.2f}"]
        q["worked_solution"] = f"10% of ${orig} = ${gst:.2f}. Final price = ${final:.2f}."

    elif qid == "fdp_450":
        cost = random.choice([100, 150, 200, 250, 400])
        pct = random.choice([10, 20, 25, 30, 40])
        sell = cost + (cost * pct) // 100
        q["question"] = f"A bicycle is bought for ${cost} and sold for ${sell}.\nCalculate the percentage profit."
        q["accepted_answers"] = [f"{pct}%", str(pct)]
        q["worked_solution"] = f"Profit = ${sell - cost}. ({sell - cost} ÷ {cost}) × 100% = {pct}%."

    elif qid == "fdp_500":
        a, b, c, d = random.choice([
            (3, 4, 9, 8), (2, 3, 4, 9), (5, 6, 5, 3),
            (4, 5, 8, 15), (3, 5, 9, 10), (5, 8, 15, 16)
        ])
        num, den = a * d, b * c
        g = math.gcd(num, den)
        rn, rd = num // g, den // g
        accepted = [f"{rn}/{rd}"]
        if rn > rd:
            accepted.append(f"{rn // rd} {rn % rd}/{rd}")
            if rd in (2, 4, 5, 8, 10):
                accepted.append(f"{rn / rd:g}")
        q["question"] = f"Evaluate ({a}/{b}) ÷ ({c}/{d}).\nWrite your answer as a simplified fraction."
        q["accepted_answers"] = accepted
        q["worked_solution"] = f"({a}/{b}) × ({d}/{c}) = {num}/{den} = {rn}/{rd}."

    elif qid == "fdp_550":
        pct = random.choice([20, 25, 30])
        orig = random.choice([80, 100, 120, 160, 200])
        sale = (orig * (100 - pct)) // 100
        q["question"] = f"After a {pct}% discount, a hoodie costs ${sale}.\nWhat was the ORIGINAL price before the discount?"
        q["accepted_answers"] = [str(orig), f"${orig}", f"{orig}.00", f"${orig}.00"]
        q["worked_solution"] = f"{100 - pct}% = ${sale} → 100% = ${orig}."

    elif qid == "fdp_600":
        orig = random.choice([100, 200, 300, 400, 500])
        pct = random.choice([10, 20])
        after_mon = (orig * (100 + pct)) // 100
        after_tue = (after_mon * (100 - pct)) // 100
        q["question"] = (
            f"A ${orig} share rises in value by {pct}% on Monday,\n"
            f"then falls by {pct}% on Tuesday.\n"
            f"What is the share worth at the end of Tuesday?"
        )
        q["accepted_answers"] = [str(after_tue), f"${after_tue}", f"{after_tue}.00", f"${after_tue}.00"]
        q["worked_solution"] = f"Monday: ${after_mon}. Tuesday: ${after_tue}."

    elif qid == "rat_100":
        a, b = random.choice([(2, 3), (3, 4), (2, 5), (3, 5), (4, 5), (3, 7), (5, 6)])
        k = random.randint(4, 12)
        q["question"] = f"Write the ratio {a * k} : {b * k} in its simplest form."
        q["accepted_answers"] = [f"{a}:{b}", f"{a} : {b}", f"{a} to {b}"]
        q["worked_solution"] = f"Divide both terms by {k} → {a} : {b}."

    elif qid == "rat_150":
        a, b = random.choice([(2, 5), (3, 4), (3, 5), (4, 7), (5, 6)])
        k = random.randint(4, 9)
        ans = b * k
        q["question"] = f"Find the missing value x in this equivalent ratio:\n{a} : {b} = {a * k} : x"
        q["accepted_answers"] = [str(ans), f"x={ans}", f"x = {ans}"]
        q["worked_solution"] = f"Multiply by {k}: x = {b} × {k} = {ans}."

    elif qid == "rat_200":
        rate = random.choice([10, 12, 12.5, 14, 15])
        litres = random.choice([20, 24, 32, 36, 40])
        dist = int(rate * litres)
        rate_s = str(int(rate)) if rate == int(rate) else f"{rate:.1f}"
        q["question"] = (
            f"A car uses {litres} litres of petrol to travel {dist} km.\n"
            f"Calculate the car's fuel rate in km per litre."
        )
        q["accepted_answers"] = [rate_s, f"{rate_s} km/l", f"{rate_s}km/l"]
        q["worked_solution"] = f"{dist} ÷ {litres} = {rate_s} km per litre."

    elif qid == "rat_250":
        cm_val, m_val = random.choice([(40, 2), (50, 2), (25, 1), (60, 3), (50, 3), (75, 3), (20, 1)])
        m_cm = m_val * 100
        g = math.gcd(cm_val, m_cm)
        ra, rb = cm_val // g, m_cm // g
        q["question"] = f"Simplify the ratio {cm_val} cm : {m_val} m\nby converting to the same units first."
        q["accepted_answers"] = [f"{ra}:{rb}", f"{ra} : {rb}", f"{ra} to {rb}"]
        q["worked_solution"] = f"{m_val} m = {m_cm} cm. {cm_val} : {m_cm} simplifies to {ra} : {rb}."

    elif qid == "rat_300":
        a, b = random.choice([(2, 3), (3, 5), (2, 5), (3, 7), (4, 5)])
        part = random.choice([10, 12, 15, 20, 25])
        total = (a + b) * part
        larger = max(a, b) * part
        q["question"] = f"Divide ${total} in the ratio {a} : {b}.\nWhat is the value of the LARGER share?"
        q["accepted_answers"] = [str(larger), f"${larger}", f"{larger}.00", f"${larger}.00"]
        q["worked_solution"] = f"Total parts = {a + b}. 1 part = ${part}. Larger share = ${larger}."

    elif qid == "rat_350":
        speed = random.choice([70, 80, 90, 100, 110])
        t1 = random.choice([2, 3, 4])
        t2 = t1 + random.choice([2, 3])
        d1, d2 = speed * t1, speed * t2
        q["question"] = (
            f"A train travels {d1} km in {t1} hours at a constant speed.\n"
            f"At this same speed, how far does it travel in {t2} hours (in km)?"
        )
        q["accepted_answers"] = [str(d2), f"{d2}km", f"{d2} km"]
        q["worked_solution"] = f"Speed = {speed} km/h. Distance in {t2} h = {d2} km."

    elif qid == "rat_400":
        low_p = random.choice([1.15, 1.20, 1.25, 1.30, 1.35])
        high_p = round(low_p + random.choice([0.15, 0.20, 0.25]), 2)
        if random.choice([True, False]):
            p_a, p_b = low_p, high_p
            best_pack = "Pack A"
        else:
            p_a, p_b = high_p, low_p
            best_pack = "Pack B"
        cost_a = 6 * p_a
        cost_b = 8 * p_b
        best_p = min(p_a, p_b)
        best_p_short = f"{best_p:.2f}".rstrip("0").rstrip(".")
        q["question"] = (
            f"Pack A has 6 muffins for ${cost_a:.2f}.\n"
            f"Pack B has 8 muffins for ${cost_b:.2f}.\n"
            f"What is the unit price (in dollars) of the BETTER VALUE pack?"
        )
        q["accepted_answers"] = [f"{best_p:.2f}", best_p_short, f"${best_p:.2f}", f"${best_p_short}"]
        q["worked_solution"] = (
            f"Pack A = ${p_a:.2f} each; Pack B = ${p_b:.2f} each. "
            f"Better value is {best_pack} at ${best_p:.2f} each."
        )

    elif qid == "rat_450":
        a, b = random.choice([(3, 5), (4, 7), (2, 5), (3, 4), (5, 6)])
        part = random.randint(3, 7)
        girls = b * part
        tot = (a + b) * part
        q["question"] = (
            f"The ratio of boys to girls in a club is {a} : {b}.\n"
            f"If there are {girls} girls in the club,\n"
            f"how many students are in the club IN TOTAL?"
        )
        q["accepted_answers"] = [str(tot), f"{tot} students"]
        q["worked_solution"] = f"{b} parts = {girls} → 1 part = {part}. Total = {a + b} × {part} = {tot}."

    elif qid == "rat_500":
        a, b, c = random.choice([(2, 3, 4), (1, 3, 5), (2, 3, 5), (1, 4, 5)])
        part = random.choice([15, 20, 25, 30])
        total = (a + b + c) * part
        mid = b * part
        q["question"] = (
            f"A prize of ${total} is shared in the ratio {a} : {b} : {c}.\n"
            f"What is the value of the MIDDLE share?"
        )
        q["accepted_answers"] = [str(mid), f"${mid}", f"{mid}.00", f"${mid}.00"]
        q["worked_solution"] = f"Total parts = {a + b + c}. 1 part = ${part}. Middle share = {b} × ${part} = ${mid}."

    elif qid == "rat_550":
        scale_k, cm_val = random.choice([
            (50000, 4), (50000, 6), (50000, 8), (50000, 10),
            (25000, 8), (25000, 12), (100000, 3), (100000, 7)
        ])
        km_val = (cm_val * scale_k) // 100000
        scale_str = f"{scale_k:,}".replace(",", " ")
        q["question"] = (
            f"On a map with a scale of 1 : {scale_str},\n"
            f"two towns are {cm_val} cm apart.\n"
            f"What is the actual distance between them (in km)?"
        )
        q["accepted_answers"] = [str(km_val), f"{km_val}km", f"{km_val} km"]
        q["worked_solution"] = f"{cm_val} × {scale_k} cm = {km_val} km."

    elif qid == "rat_600":
        d1, d2, avg = random.choice([
            (15, 60, 25), (18, 54, 24), (21, 60, 27),
            (20, 70, 30), (36, 48, 28), (40, 50, 30)
        ])
        tot_d = d1 + d2
        q["question"] = (
            f"A cyclist rides {d1} km in 1 hour,\n"
            f"then rides another {d2} km in 2 hours.\n"
            f"What is the cyclist's average speed (in km/h)?"
        )
        q["accepted_answers"] = [str(avg), f"{avg}km/h", f"{avg} km/h"]
        q["worked_solution"] = f"Total distance = {tot_d} km in 3 hours → {tot_d} ÷ 3 = {avg} km/h."

    elif qid == "ind_100":
        a = random.randint(3, 9)
        r = random.randint(4, 12)
        sq = r * r
        ans = a * a + r
        q["question"] = f"Evaluate:\n{a}² + √{sq}"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{a}² + √{sq} = {a * a} + {r} = {ans}."

    elif qid == "ind_150":
        hcf = random.choice([6, 8, 9, 12, 14, 15])
        m1, m2 = random.choice([(2, 3), (3, 4), (3, 5), (4, 5)])
        n1, n2 = hcf * m1, hcf * m2
        q["question"] = f"Find the Highest Common Factor (HCF)\nof {n1} and {n2}."
        q["accepted_answers"] = [str(hcf)]
        q["worked_solution"] = f"HCF({n1}, {n2}) = {hcf}."

    elif qid == "ind_200":
        a, b = random.choice([(8, 12), (12, 18), (10, 15), (12, 16), (9, 12), (14, 21), (15, 20)])
        ans = (a * b) // math.gcd(a, b)
        q["question"] = f"Find the Lowest Common Multiple (LCM)\nof {a} and {b}."
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"LCM({a}, {b}) = {ans}."

    elif qid == "ind_250":
        k = random.randint(4, 12)
        b1 = random.randint(3, 9)
        b2 = random.randint(2, 9)
        ans = k + 1
        q["question"] = f"Using the zero index law, evaluate:\n{k} × {b1}^0 + {b2}^0"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{k} × 1 + 1 = {ans}."

    elif qid == "ind_300":
        base = random.choice([2, 3])
        e1 = random.randint(4, 7)
        e2 = random.randint(3, 5)
        res_e = random.choice([2, 3])
        e3 = e1 + e2 - res_e
        ans = base ** res_e
        q["question"] = f"Using index laws, simplify and evaluate:\n({base}^{e1} × {base}^{e2}) ÷ {base}^{e3}"
        q["accepted_answers"] = [str(ans), f"{base}^{res_e}"]
        q["worked_solution"] = f"{base}^({e1}+{e2}−{e3}) = {base}^{res_e} = {ans}."

    elif qid == "ind_350":
        cr = random.choice([2, 3, 4])
        cube = cr ** 3
        b = random.choice([3, 4, 5])
        ans = cr + (b ** 3)
        q["question"] = f"Evaluate:\n(cube root of {cube}) + {b}³"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"Cube root of {cube} is {cr}, and {b}³ = {b ** 3}. {cr} + {b ** 3} = {ans}."

    elif qid == "pyt_400":
        a, b, c = random.choice([(3, 4, 5), (6, 8, 10), (5, 12, 13), (9, 12, 15), (8, 15, 17), (12, 16, 20)])
        q["question"] = (
            f"A right-angled triangle has shorter sides of\n"
            f"{a} cm and {b} cm.\n"
            f"Use Pythagoras' theorem to find the hypotenuse (in cm)."
        )
        q["accepted_answers"] = [str(c), f"{c}cm", f"{c} cm"]
        q["worked_solution"] = f"c = √({a}² + {b}²) = √{c * c} = {c} cm."

    elif qid == "pyt_450":
        a, b, c = random.choice([(5, 12, 13), (6, 8, 10), (8, 15, 17), (9, 12, 15), (7, 24, 25)])
        q["question"] = (
            f"A right-angled triangle has a hypotenuse of {c} cm\n"
            f"and one shorter side of {a} cm.\n"
            f"Find the length of the other shorter side (in cm)."
        )
        q["accepted_answers"] = [str(b), f"{b}cm", f"{b} cm"]
        q["worked_solution"] = f"b = √({c}² − {a}²) = √{b * b} = {b} cm."

    elif qid == "pyt_500":
        a, b, c = random.choice([(6, 8, 10), (5, 12, 13), (3, 4, 5), (9, 12, 15), (8, 15, 17)])
        q["question"] = (
            f"A {c} m ladder leans against a vertical wall\n"
            f"with its foot {a} m away from the base of the wall.\n"
            f"How high up the wall does the ladder reach (in m)?"
        )
        q["accepted_answers"] = [str(b), f"{b}m", f"{b} m"]
        q["worked_solution"] = f"h = √({c}² − {a}²) = {b} m."

    elif qid == "pyt_550":
        a, b, c = random.choice([(7, 24, 25), (8, 15, 17), (9, 12, 15), (12, 16, 20), (5, 12, 13)])
        q["question"] = (
            f"A rectangular paddock is {b} m long and {a} m wide.\n"
            f"A straight fence is built diagonally from one corner\n"
            f"to the opposite corner. How long is the fence (in m)?"
        )
        q["accepted_answers"] = [str(c), f"{c}m", f"{c} m"]
        q["worked_solution"] = f"d = √({b}² + {a}²) = {c} m."

    elif qid == "pyt_600":
        a, b, c = random.choice([(8, 15, 17), (5, 12, 13), (6, 8, 10), (9, 12, 15), (7, 24, 25)])
        area = (a * b) // 2
        q["question"] = (
            f"A right-angled triangle has a hypotenuse of {c} cm\n"
            f"and a base of {b} cm.\n"
            f"Calculate the AREA of the triangle (in cm²)."
        )
        q["accepted_answers"] = [str(area), f"{area}cm2", f"{area} cm2", f"{area}cm²"]
        q["worked_solution"] = f"Height = √({c}² − {b}²) = {a} cm. Area = ½ × {b} × {a} = {area} cm²."

    elif qid == "prob_100":
        cond, fav = random.choice([
            ("a number greater than 4", 2), ("a number less than 3", 2),
            ("a number greater than 3", 3), ("an even number", 3), ("a number less than 5", 4)
        ])
        g = math.gcd(fav, 6)
        rn, rd = fav // g, 6 // g
        q["question"] = (
            f"A fair 6-sided die is rolled once.\n"
            f"What is the probability of rolling {cond}?\n"
            f"Give your answer as a simplified fraction."
        )
        q["accepted_answers"] = [f"{rn}/{rd}"]
        q["worked_solution"] = f"{fav}/6 simplifies to {rn}/{rd}."

    elif qid == "prob_150":
        p = random.choice([0.15, 0.25, 0.35, 0.45, 0.65, 0.75, 0.85])
        comp = round(1.0 - p, 2)
        pct = int(round(comp * 100))
        g = math.gcd(pct, 100)
        q["question"] = (
            f"The probability that it rains in Sydney tomorrow is {p:.2f}.\n"
            f"What is the probability that it does NOT rain\n"
            f"(as a decimal)?"
        )
        q["accepted_answers"] = [f"{comp:.2f}", f"{comp:.2f}".lstrip("0"), f"{pct}%", f"{pct // g}/{100 // g}"]
        q["worked_solution"] = f"P(not rain) = 1 − {p:.2f} = {comp:.2f}."

    elif qid == "prob_200":
        r, g_c, y = random.choice([(5, 7, 8), (4, 9, 7), (6, 8, 6), (8, 5, 7), (10, 4, 6), (2, 11, 7)])
        gcd_v = math.gcd(r, 20)
        rn, rd = r // gcd_v, 20 // gcd_v
        dec = r / 20.0
        dec_s = f"{dec:.2f}".rstrip("0").rstrip(".")
        q["question"] = (
            f"A bag of lollies holds {r} red, {g_c} green, and {y} yellow snakes.\n"
            f"What is the probability of picking a red snake?\n"
            f"(Give as a simplified fraction or decimal)"
        )
        q["accepted_answers"] = [f"{rn}/{rd}", dec_s, f"{dec:.2f}", f"{r * 5}%"]
        q["worked_solution"] = f"Total = 20. P(red) = {r}/20 = {rn}/{rd} = {dec_s}."

    elif qid == "prob_250":
        p = random.choice([0.2, 0.25, 0.3, 0.4, 0.6, 0.7])
        n = random.choice([100, 200, 300, 400])
        ans = int(round(p * n))
        q["question"] = (
            f"A spinner lands on blue with a probability of {p}.\n"
            f"If you spin it {n} times, how many times\n"
            f"would you expect it to land on blue?"
        )
        q["accepted_answers"] = [str(ans), f"{ans} times"]
        q["worked_solution"] = f"Expected frequency = {p} × {n} = {ans}."

    elif qid == "prob_300":
        label, fav = random.choice([
            ("a Heart", 13), ("a Red card", 26), ("an Ace", 4), ("a King or Queen", 8)
        ])
        g = math.gcd(fav, 52)
        rn, rd = fav // g, 52 // g
        ans_list = [f"{rn}/{rd}"]
        if fav in (13, 26):
            dec = fav / 52.0
            ans_list.extend([f"{dec:g}", f"{int(dec * 100)}%"])
        q["question"] = (
            f"One card is drawn at random from a standard 52-card deck.\n"
            f"What is the probability of drawing {label}?\n"
            f"(Give as a simplified fraction)"
        )
        q["accepted_answers"] = ans_list
        q["worked_solution"] = f"{fav}/52 simplifies to {rn}/{rd}."

    elif qid == "prob_350":
        b, r, w = random.choice([(6, 9, 5), (4, 10, 6), (8, 7, 5), (5, 8, 7), (2, 11, 7)])
        non_b = 20 - b
        g = math.gcd(non_b, 20)
        rn, rd = non_b // g, 20 // g
        dec = non_b / 20.0
        dec_s = f"{dec:.2f}".rstrip("0").rstrip(".")
        q["question"] = (
            f"A jar contains {b} blue, {r} red, and {w} white marbles.\n"
            f"What is the probability of NOT picking a blue marble?\n"
            f"(Give as a simplified fraction or decimal)"
        )
        q["accepted_answers"] = [f"{rn}/{rd}", dec_s, f"{dec:.2f}", f"{non_b * 5}%"]
        q["worked_solution"] = f"Non-blue = {non_b}/20 = {rn}/{rd} = {dec_s}."

    elif qid == "prob_450":
        tot = random.choice([28, 30, 32, 35])
        both = random.randint(5, 8)
        a = random.randint(14, 18)
        b = random.randint(12, 16)
        neither = tot - (a + b - both)
        if neither < 2:
            tot = a + b - both + random.randint(3, 6)
            neither = tot - (a + b - both)
        q["question"] = (
            f"In a class of {tot} students, {a} play soccer,\n"
            f"{b} play basketball, and {both} play BOTH sports.\n"
            f"How many students play NEITHER sport?"
        )
        q["accepted_answers"] = [str(neither), f"{neither} students"]
        q["worked_solution"] = f"At least one = {a} + {b} − {both} = {a + b - both}. Neither = {tot} − {a + b - both} = {neither}."

    elif qid == "prob_500":
        tot = random.choice([35, 40, 45])
        neither = random.randint(4, 8)
        at_least = tot - neither
        both = random.randint(5, 10)
        a = random.randint(at_least // 2, at_least - 5)
        b = at_least + both - a
        q["question"] = (
            f"In a survey of {tot} students, {a} like maths,\n"
            f"{b} like science, and {neither} like neither subject.\n"
            f"How many students like BOTH maths and science?"
        )
        q["accepted_answers"] = [str(both), f"{both} students"]
        q["worked_solution"] = f"At least one = {tot} − {neither} = {at_least}. Both = {a} + {b} − {at_least} = {both}."

    elif qid == "prob_550":
        bp = random.randint(6, 10)
        bn = random.randint(3, 5)
        gp = random.randint(5, 8)
        gn = 25 - (bp + bn + gp)
        g = math.gcd(gp, 25)
        rn, rd = gp // g, 25 // g
        dec = gp / 25.0
        dec_s = f"{dec:.2f}".rstrip("0").rstrip(".")
        q["question"] = (
            f"In a class of 25 students: {bp} boys play sport,\n"
            f"{bn} boys do not, {gp} girls play sport, and {gn} girls do not.\n"
            f"What is the probability a random student is a girl\n"
            f"who plays sport? (Give as a simplified fraction or decimal)"
        )
        q["accepted_answers"] = [f"{rn}/{rd}", f"{gp}/25", dec_s, f"{dec:.2f}", f"{gp * 4}%"]
        q["worked_solution"] = f"{gp} out of 25 students → {rn}/{rd} = {dec_s}."

    elif qid == "prob_600":
        num, den = random.choice([(3, 5), (2, 5), (3, 4), (2, 3), (5, 8), (3, 8)])
        k = random.randint(3, 7)
        blue = num * k
        red = (den - num) * k
        q["question"] = (
            f"A bag contains {blue} blue marbles and some red marbles.\n"
            f"If the probability of randomly picking a blue marble\n"
            f"is {num}/{den}, how many RED marbles are in the bag?"
        )
        q["accepted_answers"] = [str(red), f"{red} marbles"]
        q["worked_solution"] = f"{num} parts = {blue} → 1 part = {k}. Red = {den - num} × {k} = {red}."

    # --- 6. Fallback Arithmetic & Template Problems ---
    elif qid == "fallback_1":
        f1 = random.randint(7, 14)
        f2 = random.randint(6, 12)
        ans = f1 * f2
        q["question"] = f"What is {f1} × {f2}?"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"{f1} × {f2} = {ans}."

    elif qid == "fallback_2":
        a = random.choice([2, 3, 4])
        ans = random.randint(3, 9)
        c = random.randint(2, 10)
        b = a * ans + c
        q["question"] = f"Solve for x:\n{a}x + {c} = {b}"
        q["accepted_answers"] = [str(ans), f"x={ans}", f"x = {ans}"]
        q["worked_solution"] = f"{a}x = {b - c} → x = {ans}."

    elif qid == "fallback_3":
        pct = random.choice([10, 15, 20, 25, 30])
        val = random.choice([100, 200, 300, 400, 500])
        ans = (pct * val) // 100
        q["question"] = f"Calculate {pct}% of {val}"
        q["accepted_answers"] = [str(ans)]
        q["worked_solution"] = f"({pct} ÷ 100) × {val} = {ans}."

    elif qid == "fallback_4":
        root = random.randint(7, 16)
        sq = root * root
        q["question"] = f"What is the square root of {sq}?"
        q["accepted_answers"] = [str(root)]
        q["worked_solution"] = f"√{sq} = {root}."

    return q


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
            "degrees", "deg", "units", "cans", "cans of paint"
        ]
        for suffix in suffixes:
            if u_clean.endswith(suffix):
                u_clean = u_clean[:-len(suffix)].strip()
            if a_clean.endswith(suffix):
                a_clean = a_clean[:-len(suffix)].strip()
        if u_clean and (u_clean == a_clean or u_clean.replace(",", "").replace(" ", "") == a_clean.replace(",", "").replace(" ", "")):
            return True
    return False


def load_chest_to_doors_map(filename="chest_to_doors.json"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        filename,
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "data", filename),
        "chest_to_doors.json",
        os.path.join(base_dir, "chest_to_doors.json"),
        os.path.join(base_dir, "data", "chest_to_doors.json"),
        os.path.join("data", "chest_to_doors.json"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                mapping = {}
                for k, v in raw_data.items():
                    k_str = str(k).strip()
                    if isinstance(v, list):
                        mapping[k_str] = [str(d).strip().upper() for d in v if str(d).strip()]
                    elif isinstance(v, str):
                        doors = [d.strip().upper() for d in v.split(",") if d.strip()]
                        mapping[k_str] = doors
                    elif v is not None:
                        mapping[k_str] = [str(v).strip().upper()]
                if mapping:
                    return mapping
            except Exception as e:
                print(f"Error loading chest to doors map from {candidate}: {e}")
    return dict(DEFAULT_CHEST_TO_DOORS_MAP)


CHEST_TO_DOORS_MAP = load_chest_to_doors_map()


def get_door_requirement(door_char, mapping=None):
    active_map = mapping if mapping is not None else CHEST_TO_DOORS_MAP
    for chest_id, doors in active_map.items():
        door_list = [doors] if isinstance(doors, str) else list(doors)
        if door_char in door_list:
            item_info = OBJECT_DEFINITIONS.get(str(chest_id), {})
            item_name = item_info.get("name", f"Chest {chest_id} Item")
            return item_name, str(chest_id)
    return None, None