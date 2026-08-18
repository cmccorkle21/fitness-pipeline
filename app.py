"""Private-network Streamlit dashboard for Hevy training history."""
from __future__ import annotations

from dateutil.relativedelta import relativedelta
import pandas as pd
import plotly.express as px
import streamlit as st

from fitness_pipeline.db import connect, migrate
from fitness_pipeline.mappings import seed_mappings
from fitness_pipeline.sync import sync

st.set_page_config(page_title="Fitness", page_icon="💪", layout="wide")

MUSCLE_GROUPS = [
    "Abs", "Back", "Biceps", "Chest", "Forearms", "Legs", "Rehab", "Shoulders", "Triceps"
]


def database():
    conn = connect()
    migrate(conn)
    return conn


@st.cache_data(ttl=60)
def load_volume() -> pd.DataFrame:
    """Use a short-lived SQLite connection; cached data, not a connection, is retained."""
    conn = database()
    try:
        return pd.read_sql_query(
            """SELECT date(w.start_time) AS day, e.template_id, e.title,
                      m.primary_muscle, m.secondary_muscle
               FROM workouts w
               JOIN exercises e ON e.workout_id=w.id
               JOIN sets s ON s.workout_id=e.workout_id AND s.exercise_index=e.exercise_index
               LEFT JOIN exercise_mappings m ON m.template_id=e.template_id
               WHERE w.deleted_at IS NULL AND s.set_type != 'warmup'
                 AND (m.primary_muscle IS NULL OR m.primary_muscle != 'Rehab')""",
            conn,
        )
    finally:
        conn.close()


def dashboard() -> None:
    st.title("Weekly Training Volume")
    conn = database()
    try:
        state = {row["key"]: row["value"] for row in conn.execute("SELECT key,value FROM sync_state")}
    finally:
        conn.close()
    sync_column, status_column = st.columns([1, 5])
    if sync_column.button("Sync now", type="primary"):
        with st.spinner("Syncing Hevy…"):
            try:
                mode, count = sync()
                load_volume.clear()
                st.success(f"{mode.title()} sync complete — {count} changes.")
                st.rerun()
            except Exception as exc:
                st.error(f"Sync failed: {exc}")
    status_column.caption(f"Last event sync: {state.get('last_event_sync', 'Never')}")

    df = load_volume()
    unmapped = df[df.primary_muscle.isna()][["template_id", "title"]].drop_duplicates()
    if not unmapped.empty:
        st.warning(f"{len(unmapped)} exercise templates are unmapped and excluded from volume. Update them in Settings.")
    df = df.dropna(subset=["primary_muscle"])
    if df.empty:
        st.info("No mapped non-warmup sets yet.")
        return

    days = pd.to_datetime(df["day"])
    df["week_start"] = days - pd.to_timedelta(days.dt.weekday, unit="D")
    include_unfinished = st.toggle("Include unfinished week", value=False)
    if not include_unfinished:
        today = pd.Timestamp.now().normalize()
        current_week_start = today - pd.Timedelta(days=today.weekday())
        df = df[df["week_start"] < current_week_start]
    if df.empty:
        st.info("No completed weeks are available yet.")
        return

    primary = df[["week_start", "primary_muscle"]].rename(columns={"primary_muscle": "muscle_group"}).assign(volume=1.0)
    secondary = df.dropna(subset=["secondary_muscle"])[["week_start", "secondary_muscle"]].rename(columns={"secondary_muscle": "muscle_group"}).assign(volume=0.5)
    weekly = pd.concat([primary, secondary], ignore_index=True).groupby(["week_start", "muscle_group"], as_index=False).volume.sum().sort_values("week_start")

    groups = sorted(weekly.muscle_group.unique())
    selected = st.multiselect("Muscle groups", groups, default=groups)
    weekly_view = weekly[weekly.muscle_group.isin(selected)]
    if weekly_view.empty:
        st.info("Select at least one muscle group.")
        return

    figure = px.line(weekly_view, x="week_start", y="volume", color="muscle_group", markers=True,
                     labels={"week_start": "Week", "volume": "Weighted Sets"})
    figure.update_traces(opacity=0.75, line={"width": 2})
    maximum = weekly["week_start"].max()
    default_start = pd.Timestamp(maximum) - relativedelta(months=6)
    figure.update_xaxes(range=[max(default_start, weekly["week_start"].min()), maximum], rangeslider_visible=True)
    figure.update_layout(legend_title_text="Muscle Group")
    st.plotly_chart(figure, use_container_width=True)

    st.subheader("Weekly Breakdown")
    weekly_table = weekly_view.pivot(
        index="week_start", columns="muscle_group", values="volume"
    ).fillna(0).sort_index(ascending=False)
    st.dataframe(weekly_table, use_container_width=True)
    weeks = weekly["week_start"].drop_duplicates().sort_values(ascending=False).tolist()
    selected_week = st.selectbox("Select week", weeks, format_func=lambda value: str(value.date()))
    pie_data = weekly_view[weekly_view.week_start == selected_week]
    if pie_data.empty:
        st.info("No volume recorded for the selected week with current filters.")
    else:
        pie = px.pie(pie_data, names="muscle_group", values="volume", hole=0.35)
        pie.update_traces(textposition="inside", textinfo="percent+label")
        total_sets = pie_data["volume"].sum()
        total_label = f"{int(total_sets)} sets" if total_sets % 1 == 0 else f"{total_sets:.1f} sets"
        pie.add_annotation(
            text=total_label,
            showarrow=False,
            font_size=20,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
        )
        pie.update_layout(legend_title_text="Muscle Group")
        st.plotly_chart(pie, use_container_width=True)


def settings() -> None:
    st.title("Exercise mappings")
    st.caption("Manual mappings are authoritative. Primary counts as 1.0 weighted set; secondary counts as 0.5.")
    conn = database()
    try:
        if st.button("Seed unmapped templates from retired Strong title rules"):
            added = seed_mappings(conn)
            load_volume.clear()
            st.success(f"Seeded {added} mappings. Review them before relying on analytics.")
            st.rerun()
        rows = conn.execute(
            """SELECT DISTINCT e.template_id,e.title,m.primary_muscle,m.secondary_muscle
               FROM exercises e LEFT JOIN exercise_mappings m ON m.template_id=e.template_id
               WHERE e.template_id IS NOT NULL ORDER BY e.title"""
        ).fetchall()
        options = {f"{row['title']} — {row['template_id']}": row for row in rows}
        if not options:
            st.info("Sync Hevy first.")
            return

        muscle_groups = sorted(set(MUSCLE_GROUPS) | {
            group
            for row in rows
            for group in (row["primary_muscle"], row["secondary_muscle"])
            if group
        })

        st.subheader("Unmapped queue")
        st.caption("Choose a primary muscle for each exercise you want to add, then save the table.")
        unmapped = pd.DataFrame(
            [
                {
                    "template_id": row["template_id"],
                    "exercise": row["title"],
                    "primary_muscle": "",
                    "secondary_muscle": "",
                }
                for row in rows
                if not row["primary_muscle"]
            ]
        )
        if unmapped.empty:
            st.success("All exercise templates are mapped.")
        elif not muscle_groups:
            st.info("Create the first muscle group with the individual mapping editor below.")
        else:
            edited = st.data_editor(
                unmapped,
                hide_index=True,
                use_container_width=True,
                disabled=["template_id", "exercise"],
                column_config={
                    "template_id": None,
                    "exercise": st.column_config.TextColumn("Exercise"),
                    "primary_muscle": st.column_config.SelectboxColumn(
                        "Primary muscle", options=[""] + muscle_groups, required=False
                    ),
                    "secondary_muscle": st.column_config.SelectboxColumn(
                        "Secondary muscle", options=[""] + muscle_groups, required=False
                    ),
                },
                key="unmapped_mapping_editor",
            )
            if st.button("Save queue mappings", type="primary"):
                additions = edited[edited["primary_muscle"].fillna("").str.strip() != ""]
                for mapping in additions.to_dict("records"):
                    conn.execute(
                        """INSERT INTO exercise_mappings(template_id,exercise_title,primary_muscle,secondary_muscle)
                           VALUES(?,?,?,?) ON CONFLICT(template_id) DO UPDATE SET
                           exercise_title=excluded.exercise_title, primary_muscle=excluded.primary_muscle,
                           secondary_muscle=excluded.secondary_muscle, updated_at=CURRENT_TIMESTAMP""",
                        (
                            mapping["template_id"],
                            mapping["exercise"],
                            mapping["primary_muscle"],
                            mapping["secondary_muscle"] or None,
                        ),
                    )
                conn.commit()
                load_volume.clear()
                st.success(f"Saved {len(additions)} mapping(s).")
                st.rerun()

        st.divider()
        st.subheader("Edit one mapping")
        selected = st.selectbox("Exercise template", options)
        row = options[selected]
        primary_options = muscle_groups + [row["primary_muscle"]] if row["primary_muscle"] and row["primary_muscle"] not in muscle_groups else muscle_groups
        secondary_options = [""] + muscle_groups
        with st.form("mapping"):
            primary = st.selectbox(
                "Primary muscle",
                primary_options,
                index=primary_options.index(row["primary_muscle"]) if row["primary_muscle"] in primary_options else 0,
            ) if primary_options else st.text_input("Primary muscle", row["primary_muscle"] or "")
            secondary_value = row["secondary_muscle"] or ""
            secondary = st.selectbox(
                "Secondary muscle (optional)",
                secondary_options,
                index=secondary_options.index(secondary_value) if secondary_value in secondary_options else 0,
            )
            save_column, remove_column = st.columns(2)
            submitted = save_column.form_submit_button("Save mapping", type="primary")
            deleted = remove_column.form_submit_button("Remove mapping")
        if submitted:
            if not primary.strip():
                st.error("Primary muscle is required.")
            else:
                conn.execute(
                    """INSERT INTO exercise_mappings(template_id,exercise_title,primary_muscle,secondary_muscle)
                       VALUES(?,?,?,?) ON CONFLICT(template_id) DO UPDATE SET
                       exercise_title=excluded.exercise_title, primary_muscle=excluded.primary_muscle,
                       secondary_muscle=excluded.secondary_muscle, updated_at=CURRENT_TIMESTAMP""",
                    (row["template_id"], row["title"], primary.strip(), secondary.strip() or None),
                )
                conn.commit()
                load_volume.clear()
                st.success("Saved.")
                st.rerun()
        if deleted:
            conn.execute("DELETE FROM exercise_mappings WHERE template_id=?", (row["template_id"],))
            conn.commit()
            load_volume.clear()
            st.success("Removed.")
            st.rerun()
    finally:
        conn.close()


page = st.sidebar.radio("Page", ["Dashboard", "Settings"])
settings() if page == "Settings" else dashboard()
