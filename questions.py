"""
Questions, Dynamic Parameterisation, and Progression Data Management
"""

import os
import json
import random
from chest import OBJECT_DEFINITIONS

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


def load_questions(filename="questions.json"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        filename,
        os.path.join(base_dir, filename),
        os.path.join(base_dir, "data", filename),
        os.path.join(base_dir, "data", "banks", filename),
        os.path.join("data", "banks", filename),
        os.path.join(base_dir, "questions.json"),
        "questions.json",
        os.path.join(base_dir, "data", "banks", "default_questions.json"),
        os.path.join("data", "banks", "default_questions.json"),
        os.path.join(base_dir, "data", "banks", "yr7_questions.json"),
        os.path.join("data", "banks", "yr7_questions.json"),
    ]

    seen = set()
    unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    for candidate in unique_candidates:
        if os.path.exists(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                all_q = []
                for cat in data.get("categories", []):
                    cat_name = cat.get("category_name", "Maths")
                    for q in cat.get("questions", []):
                        item = dict(q)
                        item["category"] = cat_name
                        all_q.append(item)
                if all_q:
                    print(f"[INFO] Loaded {len(all_q)} questions from '{candidate}'.")
                    return all_q
            except Exception as e:
                print(f"Error loading questions from {candidate}: {e}")

    print("[WARN] Using hardcoded fallback questions pool.")
    return [
        {"id": "fallback_1", "question": "What is 12 × 8?", "accepted_answers": ["96"], "points": 100, "category": "Arithmetic"},
        {"id": "fallback_2", "question": "Solve for x: 2x + 4 = 12", "accepted_answers": ["4"], "points": 200, "category": "Algebra"},
        {"id": "fallback_3", "question": "Calculate 15% of 200", "accepted_answers": ["30"], "points": 300, "category": "Financial"},
        {"id": "fallback_4", "question": "What is the square root of 144?", "accepted_answers": ["12"], "points": 400, "category": "Algebra"},
        {"id": "fallback_5", "question": "Evaluate: sin(90°) + cos(0°)", "accepted_answers": ["2"], "points": 500, "category": "Trigonometry"},
    ]


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
        q["image"] = "img/geo_450.png"
        q["question"] = (
            f"Two parallel horizontal lines are joined by a V-shaped\n"
            f"bend pointing to the right. The top acute angle with the\n"
            f"parallel line is {top_ang}° and the bottom acute angle is {bot_ang}°.\n"
            f"What is the size of the angle at the tip of the bend?"
        )
        q["accepted_answers"] = [str(tot_ang), f"{tot_ang}°", f"{tot_ang} degrees", f"{tot_ang} deg"]
        q["worked_solution"] = f"By alternate angles on parallel lines, tip angle = {top_ang}° + {bot_ang}° = {tot_ang}°."

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
        q["image"] = "img/geo_550.png"
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
        q["image"] = "img/geo_600.png"
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
        q["image"] = "img/trig_200.png"
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
        q["image"] = "img/meas_150.png"
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
        q["image"] = "img/area_350.png"
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
        q["image"] = "img/area_100.png"
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
        q["image"] = "img/area_550.png"
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

    # --- 5. Fallback Arithmetic & Template Problems ---
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
    u = user_input.strip().lower().replace("−", "-")
    for ans in accepted_answers:
        a = str(ans).strip().lower().replace("−", "-")
        if u == a:
            return True
        u_clean = u.replace("$", "").replace("°", "").replace("%", "").strip()
        a_clean = a.replace("$", "").replace("°", "").replace("%", "").strip()
        if u_clean and u_clean == a_clean:
            return True
        suffixes = [
            "years", "yrs", "year", "yr",
            "m2", "m²", "cm2", "cm²", "m3", "m³",
            "kl", "cm", "m", "degrees", "deg", "units", "cans", "cans of paint"
        ]
        for suffix in suffixes:
            if u_clean.endswith(suffix):
                u_clean = u_clean[:-len(suffix)].strip()
            if a_clean.endswith(suffix):
                a_clean = a_clean[:-len(suffix)].strip()
        if u_clean and u_clean == a_clean:
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