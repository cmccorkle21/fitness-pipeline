# app.py
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta

DB_PATH = "synced_workouts.db"
TABLE = "workout_sets_enriched"

st.set_page_config(page_title="Training Volume", layout="wide")

@st.cache_data
def load_data():
    with sqlite3.connect(DB_PATH) as conn:
        q = f"""
        SELECT
          date(date) AS day,
          muscle_group_primary AS muscle_group,
          is_warmup
        FROM {TABLE}
        WHERE muscle_group_primary IS NOT NULL
        """
        df = pd.read_sql(q, conn, parse_dates=["day"])
    return df

df = load_data()

# Exclude warmups if column exists (treat 1 as warmup)
if "is_warmup" in df.columns:
    df = df[df["is_warmup"] != 1]

# Compute week starts (Mon)
df["week_start"] = df["day"] - pd.to_timedelta(df["day"].dt.weekday, unit="d")

# Aggregate: sets per week per muscle group
weekly = (
    df.groupby(["week_start", "muscle_group"])
      .size()
      .reset_index(name="volume")
      .sort_values("week_start")
)

# Sidebar filters
st.sidebar.header("Filters")
all_groups = sorted(weekly["muscle_group"].unique())
selected_groups = st.sidebar.multiselect(
    "Muscle groups", all_groups, default=all_groups
)
weekly_view = weekly[weekly["muscle_group"].isin(selected_groups)]

st.title("📈 Weekly Training Volume (Lines)")
st.caption("Excludes warmups • Hover legend to focus/compare • Use range slider or drag to zoom")

# Line chart
fig = px.line(
    weekly_view,
    x="week_start",
    y="volume",
    color="muscle_group",
    markers=True,  # dots help when weeks are sparse
    labels={"week_start": "Week", "volume": "Sets"},
)

# Determine default 3-month window (initial view only; data not truncated)
max_date = weekly["week_start"].max()
if pd.isna(max_date):
    st.warning("No data available."); st.stop()
min_date = weekly["week_start"].min()

# Use Timestamp everywhere to avoid type mismatch
default_start = pd.Timestamp(max_date) - relativedelta(months=3)

fig.update_xaxes(
    range=[max(default_start, min_date), max_date],
    rangeslider=dict(visible=True),
    rangeselector=dict(
        buttons=[
            dict(count=28, step="day", stepmode="backward", label="4W"),
            dict(count=3,  step="month", stepmode="backward", label="3M"),
            dict(count=6,  step="month", stepmode="backward", label="6M"),
            dict(step="all", label="All"),
        ]
    ),
    tickformat="%b %d\n%Y",
)

fig.update_layout(legend_title_text="Muscle Group")

st.plotly_chart(fig, use_container_width=True)

with st.expander("Show weekly table"):
    st.dataframe(weekly_view, use_container_width=True)
