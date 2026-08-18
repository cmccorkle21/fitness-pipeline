from __future__ import annotations

import re

# Matches the retired Strong mapper's ordering, so a seeded primary/secondary mapping
# retains the previous dashboard semantics while becoming editable thereafter.
GROUP_PRIORITY = {
    "Chest": 1, "Back": 1, "Shoulders": 2, "Legs": 2,
    "Biceps": 3, "Triceps": 3, "Abs": 4, "Forearms": 4,
}


def legacy_groups(title: str) -> list[str]:
    """Return the retired Strong title-rule mapping in its deterministic display order."""
    name = re.sub(r"[^a-z ]", "", title.lower())
    name = re.sub(r"\s+", " ", name).strip()
    groups: set[str] = set()

    if (any(term in name for term in ["bench", "press", "dip", "bulgarian pushup", "pushup", "push up", "rto", "ring hold", "pec deck"])
            and "leg" not in name and "row" not in name and "overhead" not in name
            and "shoulder" not in name and "calf" not in name):
        groups.update(["Chest", "Triceps"])
    if any(term in name for term in ["fly", "pec"]) and "rear delt" not in name:
        groups.add("Chest")
    if any(term in name for term in ["row", "pulldown", "pull up", "pullup", "chinup", "chin up"]):
        groups.update(["Back", "Biceps"])
    if "curl" in name and "hamstring" not in name and "leg" not in name and "tricep" not in name:
        groups.add("Biceps")
    if any(term in name for term in ["bicep", "biceps"]):
        groups.add("Biceps")
    if (any(term in name for term in ["triceps", "tricep", "extension", "katana", "cross cable extension", "skullcrusher", "skull crusher", "dumbbell kickback", "kickback", "press"])
            and "leg" not in name and "calf" not in name and "overhead" not in name
            and "shoulder" not in name and not ("back" in name and "kickback" not in name)):
        groups.add("Triceps")
    if (any(term in name for term in ["lateral", "overhead", "raise", "face pull", "rear delt", "shoulder"])
            and "leg" not in name and "row" not in name and "chest" not in name
            and "calf" not in name and "unilateral cable fly" not in name):
        groups.add("Shoulders")
    # Preserve the original literal term list (including its concatenated typo) for
    # an exact historical seed; editable mappings can correct any undesired result.
    if (any(term in name for term in ["squat", "lunge", "leg press", "rdl", "deadlift", "hamstringleg curl", "leg extension", "hip adductor", "seated leg curl", "lying leg curl", "back extension", "calf"])
            and "forearm leg raise" not in name):
        groups.add("Legs")
    if any(term in name for term in ["crunch", "plank", "rollout", "gar hammer", "l sit", "leg raise"]) or re.search(r"\babs\b", name):
        groups.add("Abs")
    if any(term in name for term in ["rotator cuff", "band pull", "external rotation", "ytw", "physio", "serratus walks", "pec stretch", "timeout", "trx", "foam", "thoracic", "mobilization"]):
        groups = {"Rehab"}
    if any(term in name for term in ["dead hang", "forearm", "false grip hang"]) and "leg" not in name:
        groups.add("Forearms")
    return sorted(groups, key=lambda group: GROUP_PRIORITY.get(group, 99))


def seed_mappings(conn) -> int:
    rows = conn.execute("SELECT DISTINCT template_id,title FROM exercises WHERE template_id IS NOT NULL").fetchall()
    added = 0
    for row in rows:
        groups = legacy_groups(row["title"])
        if groups:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO exercise_mappings
                (template_id,exercise_title,primary_muscle,secondary_muscle) VALUES(?,?,?,?)""",
                (row["template_id"], row["title"], groups[0], groups[1] if len(groups) > 1 else None),
            )
            added += cursor.rowcount
    conn.commit()
    return added
