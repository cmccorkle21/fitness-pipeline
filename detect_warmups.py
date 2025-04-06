def detect_warmups(df, work_threshold=0.6):
    df["is_warmup"] = False  # use snake_case to match the DB field style
    grouped = df.groupby(["date", "exercise_name"])

    for (date, exercise), group in grouped:
        group = group.copy()
        group["work"] = group["weight"] * group["reps"]

        if group["work"].max() == 0:
            continue

        top_work = group["work"].max()
        top_index = group["work"].idxmax()

        for i in group.index:
            if i == top_index:
                break
            if group.loc[i, "work"] < top_work * work_threshold:
                df.at[i, "is_warmup"] = True

    return df
