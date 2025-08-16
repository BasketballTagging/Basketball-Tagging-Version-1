import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import json

st.set_page_config(page_title="StFx MBB Tagger (Streamlit)", layout="wide")

# ---------- Session State Init ----------
if "buttons" not in st.session_state:
    st.session_state.buttons = [
        {"label": "Pick and Roll", "color": "#3f51b5"},
    ]

if "events" not in st.session_state:
    st.session_state.events = []


def compute_counts():
    counts = {}
    for ev in st.session_state.events:
        key = (ev["label"], ev["quarter"], ev["result"])
        counts[key] = counts.get(key, 0) + 1
    return counts


# ---------- Sidebar: Game Meta & Admin ----------
st.sidebar.header("Game Info")
opponent = st.sidebar.text_input("Opponent", placeholder="e.g., Acadia", key="opponent")
game_date = st.sidebar.date_input("Game Date", key="game_date")
quarter = st.sidebar.selectbox("Quarter", ["", "Q1", "Q2", "Q3", "Q4", "OT"], index=0, key="quarter")
st.sidebar.caption("Opponent, Date, and Quarter are required before tagging.")

st.sidebar.header("Buttons")
with st.sidebar.form("new_btn_form", clear_on_submit=True):
    new_label = st.text_input("New Button Label", placeholder="e.g., Pick and Roll")
    new_color = st.color_picker("Color", "#3f51b5")
    submitted = st.form_submit_button("Add Button")
    if submitted:
        lbl = (new_label or "").strip()
        if not lbl:
            st.sidebar.error("Label is required.")
        elif any(b["label"].lower() == lbl.lower() for b in st.session_state.buttons):
            st.sidebar.error("That label already exists.")
        else:
            st.session_state.buttons.append({"label": lbl, "color": new_color})
            st.sidebar.success(f"Added: {lbl}")

st.sidebar.subheader("Layout")
cfg = {"buttons": st.session_state.buttons}
st.sidebar.download_button(
    "Save Layout (JSON)",
    data=json.dumps(cfg, indent=2),
    file_name="tagger_layout.json",
    mime="application/json",
    use_container_width=True
)

uploaded = st.sidebar.file_uploader("Load Layout (JSON)", type=["json"])
if uploaded is not None:
    try:
        content = json.load(uploaded)
        btns = content.get("buttons", [])
        cleaned = []
        for b in btns:
            label = str(b.get("label", "")).strip()[:32]
            color = str(b.get("color", "#3f51b5")).strip()
            if label:
                cleaned.append({"label": label, "color": color})
        if not cleaned:
            st.sidebar.error("No valid buttons found.")
        else:
            st.session_state.buttons = cleaned
            st.sidebar.success(f"Loaded {len(cleaned)} buttons.")
    except Exception as e:
        st.sidebar.error(f"Failed to load: {e}")

st.sidebar.subheader("Session")
if st.sidebar.button("Undo Last Tag", use_container_width=True):
    if st.session_state.events:
        st.session_state.events.pop()
        st.sidebar.success("Undid last tag.")
if st.sidebar.button("Reset Counts", use_container_width=True):
    st.session_state.events = []
    st.sidebar.success("Cleared all events.")


# ---------- Main: Tagging UI ----------
st.title("StFx MBB Tagging Application")
st.caption("Click buttons to tag events. Use sidebar for game info and buttons.")

cols_per_row = 5
buttons = st.session_state.buttons
rows = [buttons[i:i + cols_per_row] for i in range(0, len(buttons), cols_per_row)]
for row in rows:
    cols = st.columns(len(row), gap="small")
    for i, b in enumerate(row):
        label = b["label"]
        if cols[i].button(label, key=f"btn_{label}"):
            if not opponent or not game_date or not quarter:
                st.toast("Enter Opponent, Date, and Quarter first.", icon="⚠️")
            else:
                result = st.selectbox(
                    f"Result for {label} ({quarter})",
                    ["Made 2", "Made 3", "Missed 2", "Missed 3", "Foul"],
                    key=f"result_{len(st.session_state.events)}"
                )
                if result:
                    ev = {
                        "opponent": opponent.strip(),
                        "game_date": str(game_date),
                        "quarter": quarter,
                        "timestamp_iso": datetime.now().isoformat(timespec="seconds"),
                        "label": label,
                        "result": result,
                    }
                    st.session_state.events.append(ev)
                    st.toast(f"Tagged: {label} – {result}", icon="✅")


# ---------- Highlight Function ----------
def highlight_result(val):
    if isinstance(val, str):
        if val.startswith("Made"):
            return "color: green; font-weight: bold"
        elif val.startswith("Missed"):
            return "color: red; font-weight: bold"
        elif val == "Foul":
            return "color: orange; font-weight: bold"
    return ""


# ---------- Totals ----------
st.subheader("Totals")
counts = compute_counts()
if counts:
    df_counts = pd.DataFrame(
        [{"Tag": k[0], "Quarter": k[1], "Result": k[2], "Total": v} for k, v in sorted(counts.items())]
    )
    styled_counts = df_counts.style.applymap(highlight_result, subset=["Result"])
    st.dataframe(styled_counts, use_container_width=True, hide_index=True)

    # ---------- Raw Counts Chart (Altair with colors) ----------
    st.subheader("Analytics Visualization (Raw Counts)")
    chart_counts = alt.Chart(df_counts).mark_bar().encode(
        x="Tag:N",
        y="Total:Q",
        color=alt.Color("Result:N",
                        scale=alt.Scale(domain=["Made 2", "Made 3", "Missed 2", "Missed 3", "Foul"],
                                        range=["green", "green", "red", "red", "orange"]))
    ).properties(width=700, height=400)
    st.altair_chart(chart_counts, use_container_width=True)

    # ---------- FG% Breakdown ----------
    st.subheader("FG% Breakdown")
    made_mask = df_counts["Result"].str.startswith("Made")
    miss_mask = df_counts["Result"].str.startswith("Missed")

    df_counts_fg = df_counts.copy()
    df_counts_fg["Made"] = df_counts_fg["Total"].where(made_mask, 0)
    df_counts_fg["Missed"] = df_counts_fg["Total"].where(miss_mask, 0)

    fg_summary = df_counts_fg.groupby(["Tag", "Quarter"])[["Made", "Missed"]].sum()
    fg_summary["Attempts"] = fg_summary["Made"] + fg_summary["Missed"]
    fg_summary["FG%"] = (fg_summary["Made"] / fg_summary["Attempts"]).replace([None, float("nan")], 0) * 100

    fg_reset = fg_summary.reset_index()

    # FG% chart with conditional coloring
    chart_fg = alt.Chart(fg_reset).mark_bar().encode(
        x="Tag:N",
        y="FG%:Q",
        color=alt.condition(
            alt.datum["FG%"] >= 50,
            alt.value("green"),
            alt.value("red")
        ),
        column="Quarter:N"
    ).properties(width=120, height=400)
    st.altair_chart(chart_fg, use_container_width=True)

    # FG% table with highlights
    styled_fg = fg_reset.style.applymap(
        lambda v: "color: green; font-weight: bold" if isinstance(v, (int, float)) and v >= 50
        else "color: red; font-weight: bold" if isinstance(v, (int, float)) else ""
    , subset=["FG%"])
    st.dataframe(styled_fg, use_container_width=True, hide_index=True)

    # Overall FG%
    total_made = fg_summary["Made"].sum()
    total_attempts = fg_summary["Attempts"].sum()
    overall_fg = (total_made / total_attempts * 100) if total_attempts > 0 else 0
    st.metric("Overall FG%", f"{overall_fg:.1f}%")

else:
    st.write("No tags yet.")


# ---------- Recent Events ----------
st.subheader("Recent Events")
if st.session_state.events:
    df_events = pd.DataFrame(st.session_state.events)
    cols_order = ["result", "label", "quarter", "opponent", "game_date", "timestamp_iso"]
    df_events = df_events[cols_order]
    styled_df = df_events.style.applymap(highlight_result, subset=["result"])
    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    csv = df_events.to_csv(index=False).encode("utf-8")
    st.download_button("Export CSV", data=csv, file_name="tag_events.csv", mime="text/csv")
else:
    st.write("No events yet.")

st.markdown("---")
st.caption("Deploy to Streamlit Cloud by pushing to GitHub and linking the repo.")
