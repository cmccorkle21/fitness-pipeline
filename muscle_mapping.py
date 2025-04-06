def map_exercise_to_muscle_groups(exercise_name: str):
    import re
    from notify import send_push
    original = exercise_name
    name = re.sub(r"[^a-z ]", "", exercise_name.lower())  # remove non-alpha
    name = re.sub(r"\s+", " ", name).strip()              # clean spaces

    groups = set()

    if any(term in name for term in ["bench", "press", "dip", "bulgarian pushup", "pushup", "push up", "rto", "ring hold", "pec deck"]) and "leg" not in name and "row" not in name and "overhead" not in name and "shoulder" not in name and "calf" not in name:
        groups.add("Chest")
        groups.add("Triceps")
    
    if any(term in name for term in ["fly", "pec"]) and "rear delt" not in name:
        groups.add("Chest")

    if any(term in name for term in ["row", "pulldown", "pull up", "pullup", "chinup", "chin up"]):
        groups.add("Back")
        groups.add("Biceps")

    if "curl" in name and "hamstring" not in name and "leg" not in name and "tricep" not in name:
        groups.add("Biceps")
    if any(term in name for term in ["bicep", "biceps"]):
        groups.add("Biceps")

    if any(term in name for term in ["triceps", "tricep", "extension", "katana", "cross cable extension", "skullcrusher", "skull crusher", "dumbbell kickback", "kickback", "press"]) and "leg" not in name and "calf" not in name and "overhead" not in name and "shoulder" not in name and not ("back" in name and "kickback" not in name):
        groups.add("Triceps")

    if any(term in name for term in ["lateral", "overhead", "raise", "face pull", "rear delt", "shoulder"]) and "leg" not in name and "row" not in name and "chest" not in name and "calf" not in name and "unilateral cable fly" not in name:
        groups.add("Delts")

    if any(term in name for term in ["squat", "lunge", "leg press", "rdl", "deadlift", "hamstring" "leg curl", "leg extension", "hip adductor", "seated leg curl", "lying leg curl", "back extension", "calf"]) and "forearm leg raise" not in name:
        groups.add("Legs")

    if any(term in name for term in ["crunch", "plank", "rollout", "gar hammer", "l sit", "leg raise"]) or re.search(r"\babs\b", name):  # catches " abs ", avoids "cable abs"
        groups.add("Abs")
 
    if any(term in name for term in ["rotator cuff", "band pull", "external rotation", "ytw", "physio", "serratus walks", "pec stretch", "timeout", "trx", "foam", "thoracic", "mobilization"]):
        groups.add("Rehab")
        #if in any other group, remove it
        if "Chest" in groups:
            groups.remove("Chest")
        if "Back" in groups:
            groups.remove("Back")
        if "Delts" in groups:
            groups.remove("Delts")
        if "Legs" in groups:
            groups.remove("Legs")
        if "Triceps" in groups:
            groups.remove("Triceps")
        if "Biceps" in groups:
            groups.remove("Biceps")
        if "Forearms" in groups:
            groups.remove("Forearms")
        if "Abs" in groups:
            groups.remove("Abs")

    if any(term in name for term in ["dead hang", "forearm", "false grip hang"]) and "leg" not in name:
        groups.add("Forearms")


    if not groups:
        print(f"❌ No match for: '{original}' → cleaned: '{name}'")
        send_push(f"❌ No muscle group mapping for: '{original}' → cleaned: '{name}'")

    else:
        print(f"✅ Mapped: '{original}' → {list(groups)}")

    return list(groups)
