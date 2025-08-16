import streamlit as st
import pandas as pd
from datetime import datetime
import json

st.set_page_config(page_title="StFx MBB Tagger (Streamlit)", layout="wide")

# ---------- Session State Init ----------
if "buttons" not in st.session_state:
    st.session_state.buttons = [
        {"label": "Pick and Roll", "color": "#3f51b5"},
    ]

if "events" not in st.session_state:
    st.session_state.events = []  # list of dicts: opponent, game_date, quarter, result, timestamp_iso, label

if "pending_tag" not in st.session_state:
    st.session_state.pending_tag = None  # holds label if a button was clicked

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
st.sidebar.caption("Opponent, Date, and Quarter are required before you can tag.")

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
# Save config
cfg = {"buttons": st.session_state.buttons}
st.sidebar.download_button(
    "Save Layout (JSON)",
    data=json.dumps(cfg, indent=2),
    file_name="tagger_layout.json",
    mime="application/json",
    use_container_width=True
)

# Load config
uploaded = st.sidebar.file_uploader("Load Layout (JSON)", type=["json"], accept_multiple_files=False)
if uploaded is not None:
    try:
        content = json.load(uploaded)
        btns = content.get("buttons", [])
        cleaned = []
        for b in btns:
            label = str(b.get("label","")).strip()[:32]
            color = str(b.get("color","#3f51b5")).strip()
            if label:
                cleaned.append({"label": label, "color": color})
        if not cleaned:
            st.sidebar.error("No valid buttons found in uploaded layout.")
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
    else:
        st.sidebar.info("No events to undo.")

if st.sidebar.button("Reset Counts", use_container_width=True):
    st.session_state.events = []
    st.sidebar.success("Cleared all events.")

# ---------- Main: Tagging UI ----------
st.title("StFx MBB Tagging Application")
st.caption("Click buttons to tag events in real time. Use the sidebar to manage game info and buttons.")

# Buttons grid
cols_per_row = 5
buttons = st.session_state.buttons
if not buttons:
    st.info("No buttons yet. Add tags from the sidebar → New Button Label.")

rows = [buttons[i:i+cols_per_row] for i in range(0, len(buttons), cols_per_row)]
for row in rows:
    cols = st.columns(len(row), gap="small")
    for i, b in enumerate(row):
        label = b["label"]
        if cols[i].button(label, key=f"btn_{label}"):
            if not opponent or not game_date or not quarter:
                st.toast("Enter Opponent, Date, and Quarter first.", icon="⚠️")
            else:
                st.session_state.pending_tag = label  # store temporarily until result is chosen

# ---------- Result Prompt ----------
if st.session_state.pending_tag:
    st.subheader(f"Result for: {st.session_state.pending_tag}")
    result = st.radio(
        "Select outcome",
        ["Made 2", "Made 3", "Missed 2", "Missed 3", "Foul"],
        horizontal=True,
        key="result_choice"
    )
    if st.button("Confirm Result"):
        ev = {
            "opponent": opponent.strip(),
            "game_date": str(game_date),
            "quarter": quarter,
            "result": result,
            "timestamp_iso": datetime.now().isoformat(timespec="seconds"),
            "label": st.session_state.pending_tag,
        }
        st.session_state.events.append(ev)
        st.toast(f"Tagged: {st.session_state.pending_tag} ({quarter}, {result})", icon="✅")
        st.session_state.pending_tag = None  # reset

# ---------- Totals ----------
st.subheader("Totals")
counts = compute_counts()
if counts:
    df_counts = pd.DataFrame(
        [{"Tag": k[0], "Quarter": k[1], "Result": k[2], "Total": v} for k, v in sorted(counts.items())]
    )
    st.dataframe(df_counts, use_container_width=True, hide_index=True)

    # ---------- Analytics Visualization ----------
    st.subheader("Analytics Visualization")
    pivot = df_counts.pivot_table(index="Tag", columns=["Quarter", "Result"], values="Total").fillna(0)
    pivot.columns = [f"{q}_{r}" for q, r in pivot.columns]  # flatten MultiIndex
    st.bar_chart(pivot)
else:
    st.write("No tags yet.")

# ---------- Recent Events ----------
st.subheader("Recent Events")
if st.session_state.events:
    df_events = pd.DataFrame(st.session_state.events)
    st.dataframe(df_events.sort_values("timestamp_iso", ascending=False), use_container_width=True, hide_index=True)
    csv = df_events.to_csv(index=False).encode("utf-8")
    st.download_button("Export CSV", data=csv, file_name="tag_events.csv", mime="text/csv")
else:
    st.write("No events yet.")

st.markdown("---")
st.caption("Tip: To deploy online, push this folder to a GitHub repo and use Streamlit Community Cloud to run it directly from the repo.")
