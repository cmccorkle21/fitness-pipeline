# app.py
import sqlite3
from os.path import getmtime

import pandas as pd
import plotly.express as px
import streamlit as st
from dateutil.relativedelta import relativedelta

DB_PATH = "synced_workouts.db"
TABLE = "workout_sets_enriched"

st.set_page_config(page_title="Training Dashboard", layout="wide")


def _db_mtime(path: str) -> float:
    try:
        return getmtime(path)
    except FileNotFoundError:
        return 0.0


@st.cache_data
def load_data(_mitime: float) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        q = f"""
        SELECT
            id,
            date(date) AS day,
            exercise_name,
            set_order,
            set_index,
            is_warmup,
            muscle_group_primary AS muscle_group,
            muscle_group_secondary
        FROM {TABLE}
        WHERE is_warmup = 0
          AND (muscle_group IS NULL OR muscle_group != 'Rehab')
        ORDER BY day ASC;
        """
        df = pd.read_sql(q, conn, parse_dates=["day"])
    return df


df = load_data(_db_mtime(DB_PATH))

# Compute week starts (Mon)
df["week_start"] = df["day"] - pd.to_timedelta(df["day"].dt.weekday, unit="d")

# Build weighted rows:
# - primary rows: weight = 1.0
# - secondary rows (when present): weight = 0.5, attributed to the secondary group
primary = df.loc[df["muscle_group"].notna(), ["week_start", "muscle_group"]].copy()
primary["weight"] = 1.0

secondary = df.loc[
    df["muscle_group_secondary"].notna(), ["week_start", "muscle_group_secondary"]
].copy()
secondary = secondary.rename(columns={"muscle_group_secondary": "muscle_group"})
secondary["weight"] = 0.5

weighted = pd.concat([primary, secondary], ignore_index=True)

# Aggregate: weighted sets per week per muscle group
weekly = (
    weighted.groupby(["week_start", "muscle_group"], as_index=False)["weight"]
    .sum()
    .rename(columns={"weight": "volume"})
    .sort_values("week_start")
)

# Sidebar filters
st.sidebar.header("Filters")
all_groups = sorted(weekly["muscle_group"].unique())
selected_groups = st.sidebar.multiselect(
    "Muscle groups", all_groups, default=["Back", "Chest"]
)
weekly_view = weekly[weekly["muscle_group"].isin(selected_groups)]

st.title("Weekly Training Volume")
st.caption(
    "Excludes warmups & Rehab • Overlapping lines • Use range slider or drag to zoom"
)

# Line chart
fig = px.line(
    weekly_view,
    x="week_start",
    y="volume",
    color="muscle_group",
    markers=True,
    labels={"week_start": "Week", "volume": "Weighted Sets"},
)
fig.update_traces(opacity=0.75, line=dict(width=2))

# Default view: last 3 months (but data not truncated; slider lets you zoom)
max_date = weekly["week_start"].max()
if pd.isna(max_date):
    st.warning("No data available.")
    st.stop()
min_date = weekly["week_start"].min()
default_start = pd.Timestamp(max_date) - relativedelta(months=3)

fig.update_xaxes(
    range=[max(default_start, min_date), max_date],
    rangeslider=dict(visible=True),
    rangeselector=dict(
        buttons=[
            dict(count=28, step="day", stepmode="backward", label="4W"),
            dict(count=3, step="month", stepmode="backward", label="3M"),
            dict(count=6, step="month", stepmode="backward", label="6M"),
            dict(step="all", label="All"),
        ]
    ),
    tickformat="%b %d\n%Y",
)

fig.update_layout(legend_title_text="Muscle Group")

st.plotly_chart(fig, use_container_width=True)

with st.expander("Show weekly table"):
    st.dataframe(weekly_view, use_container_width=True)

# --- Weekly donut (pie) breakdown ---
st.subheader("Weekly Breakdown")

# Build week options from full weekly data (not just filtered view)
weeks = weekly["week_start"].dropna().sort_values(ascending=False).unique()
if len(weeks) == 0:
    st.info("No weeks available to show a breakdown.")
else:
    # Default to the most recent week
    default_idx = 0

    # Nice label: WeekStart – WeekEnd
    def week_label(ts):
        start = pd.Timestamp(ts).date()
        end = (pd.Timestamp(ts) + pd.Timedelta(days=6)).date()
        return f"{start} – {end}"

    # Select a week to inspect
    selected_week = st.selectbox(
        "Select week",
        weeks,
        index=default_idx,
        format_func=week_label,
    )

    pie_df = weekly[
        (weekly["week_start"] == selected_week)
        # & (weekly["muscle_group"].isin(selected_groups)) # uncomment to filter donut
    ].copy()

    if pie_df.empty or pie_df["volume"].sum() == 0:
        st.info("No volume recorded for the selected week with current filters.")
    else:
        # Donut chart
        fig_pie = px.pie(
            pie_df,
            names="muscle_group",
            values="volume",
            hole=0.3,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")

        total_sets = pie_df["volume"].sum()
        fig_pie.add_annotation(
            text=(
                f"{total_sets:.1f} sets"
                if total_sets % 1
                else f"{int(total_sets)} sets"
            ),
            showarrow=False,
            font_size=20,
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
        )
        fig_pie.update_layout(legend_title_text="Muscle Group")

        st.plotly_chart(fig_pie, use_container_width=True)
