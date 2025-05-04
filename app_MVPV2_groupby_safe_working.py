import streamlit as st
import pandas as pd
import datetime
from pathlib import Path
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === CONFIG ===
SHEET_KEY = "1ly7zmZwCEy3Dl7iChVbLiaT4KgOyhNB-3zXEHa8S3c8"
LOG_DIR = Path("client_logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# === GOOGLE SHEETS AUTH ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

# === LOAD WEEKLY QUOTE (no headers) ===
try:
    quote_ws = sheet.worksheet("Quotes")
    quote_values = quote_ws.col_values(1)
    current_week = datetime.date.today().isocalendar().week
    weekly_quote = quote_values[current_week - 1] if current_week <= len(quote_values) else ""
except Exception as e:
    weekly_quote = ""

# === UI SETUP ===
st.set_page_config(page_title="Training Log", layout="wide")
st.markdown("""
    <style>
        input, select, textarea { font-size: 18px !important; }
        .stButton>button { font-size: 18px; }
    </style>
""", unsafe_allow_html=True)

# === Welcome Input ===
first_name = st.text_input("Enter Your First Name", placeholder="e.g. Alex")
if not first_name:
    st.warning("👋 Please enter your first name to continue.")
    st.stop()

col1, col2 = st.columns([1, 4])
with col1:
    st.image("bodylab_logo_clean.png", width=160)

with col2:
    st.markdown(f"## 👋 Welcome {first_name.title()}!")
    if weekly_quote:
        st.markdown(
            f"""
            <div style='padding-top: 10px; font-size: 20px; font-style: italic; color: #555;'>
                “{weekly_quote}”
            </div>
            """, unsafe_allow_html=True
        )

st.title("Client Training Log")


# === LOAD CLIENT WORKOUT TEMPLATE ===
try:
    sheet = client.open_by_key(SHEET_KEY)
    worksheet = sheet.worksheet(first_name.title())
    records = worksheet.get_all_records()
    df_template = pd.DataFrame(records)
except Exception as e:
    st.error(f"Failed to load Google Sheet tab for {first_name.title()}: {e}")
    st.stop()

available_workouts = df_template["Workout #"].dropna().unique().tolist()
selected_workout = st.selectbox("Select Workout", available_workouts)
df_selected = df_template[df_template["Workout #"] == selected_workout]

if df_selected.empty:
    st.warning("No exercises found for this workout.")
    st.stop()

log_date = st.date_input("Enter Date of Workout", value=datetime.date.today())

with st.expander(f"📋 {selected_workout} Overview"):
    st.dataframe(df_selected[["Order", "Movement Pattern", "Exercise", "Sets", "Reps", "Rest (sec)", "Demo"]].reset_index(drop=True), use_container_width=True)

st.markdown("### 📝 Log RPE, Notes & Mark Completion")
log_file = LOG_DIR / first_name.strip().lower() / "history_log.xlsx"
prev_logs = pd.DataFrame()
if log_file.exists():
    prev_logs = pd.read_excel(log_file)
    prev_logs["Date"] = pd.to_datetime(prev_logs["Date"])

entries = []
for i, row in df_selected.iterrows():
    past_rpe = past_note = None
    if not prev_logs.empty:
        match = prev_logs[
            (prev_logs["Exercise #"] == row["Order"]) &
            (prev_logs["Exercise"] == row["Exercise"])
        ].sort_values("Date", ascending=False)
        if not match.empty:
            past_rpe = match.iloc[0]["RPE"]
            past_note = match.iloc[0]["Notes"]

    with st.container():
        tempo_raw = str(row.get("Tempo", ""))
        if tempo_raw.count(",") == 2:
            t1, t2, t3 = tempo_raw.split(",")
            formatted_tempo = f"{t1.strip()} ⬇️ | {t2.strip()} ⏸️ | {t3.strip()} ⬆️"
        else:
            formatted_tempo = "None"
        tempo_raw = str(row.get("Tempo", ""))
        if tempo_raw.count(',') == 2:
            t1, t2, t3 = tempo_raw.split(',')
            formatted_tempo = f"{t1.strip()} ⬇️ | {t2.strip()} ⏸️ | {t3.strip()} ⬆️"
        elif len(tempo_raw) == 3 and tempo_raw.isdigit():
            formatted_tempo = f"{tempo_raw[0]} ⬇️ | {tempo_raw[1]} ⏸️ | {tempo_raw[2]} ⬆️"
        else:
            formatted_tempo = "None"
        if formatted_tempo != "None":
            st.markdown(f"**{row['Order']} - {row['Exercise']}** | Sets: {row['Sets']} | Reps: {row['Reps']} | **{formatted_tempo}**")
        else:
            st.markdown(f"**{row['Order']} - {row['Exercise']}** | Sets: {row['Sets']} | Reps: {row['Reps']}")
        tempo_raw = str(row.get("Tempo", ""))
        if tempo_raw.count(',') == 2:
            t1, t2, t3 = tempo_raw.split(',')
            formatted_tempo = f"{t1.strip()} ⬇️ | {t2.strip()} ⏸️ | {t3.strip()} ⬆️"
            st.markdown(f"**Tempo:** {formatted_tempo}")
        if "http" in row["Demo"]:
            st.markdown(f"[▶️ Demo VidOrder]({row['Demo']})")
        cols = st.columns([1, 3, 1])
        rpe = cols[0].selectbox("RPE", options=list(range(1, 11)), index=(int(past_rpe)-1) if past_rpe else 5, key=f"rpe_{i}")
        note = cols[1].text_input("Notes", value=past_note if past_note else "", key=f"note_{i}")
        checked = cols[2].checkbox("Done", key=f"done_{i}")
        entries.append({
            "Client": first_name.title(),
            "Date": log_date,
            "Workout #": selected_workout,
            "Exercise #": row["Order"],
            "Movement Pattern": row["Movement Pattern"],
            "Exercise": row["Exercise"],
            "Sets": row["Sets"],
            "Reps": row["Reps"],
            "Rest (sec)": row["Rest (sec)"],
            "Demo": row["Demo"],
            "RPE": rpe,
            "Notes": note,
            "Completed": checked
        })

if st.button("✅ Save Workout Log"):
    df_log = pd.DataFrame(entries)
    client_dir = LOG_DIR / first_name.strip().lower()
    client_dir.mkdir(parents=True, exist_ok=True)

    if log_file.exists():
        old_df = pd.read_excel(log_file)
        df_log = pd.concat([old_df, df_log], ignore_index=True)

    df_log.to_excel(log_file, index=False)
    st.toast("Workout saved!", icon="💪")

    st.markdown("### ✅ Weekly Completion Summary")
    recent = df_log[pd.to_datetime(df_log["Date"]) >= pd.Timestamp.now() - pd.Timedelta(days=7)]
recent = df_log[df_log["Client Name"] == first_name].sort_values(by="Date", ascending=False).head(10)
log_file = f"client_logs/{first_name}_log.xlsx"
df_log = pd.read_excel(log_file)
recent = df_log[df_log["Client Name"] == first_name].sort_values(by="Date", ascending=False).head(10)
if not recent.empty and "Workout #" in recent.columns and "Date" in recent.columns:
    summary = recent.groupby(["Workout #", "Date"]).agg(
        Exercises=("Exercise", "count"),
        Completed=("Completed", "sum"),
        Avg_RPE=("RPE", "mean")
        ).reset_index().sort_values(by=["Date"], ascending=False)
    st.dataframe(summary.reset_index(drop=True), use_container_width=True)
    st.line_chart(summary.set_index("Date")["Avg_RPE"])
else:
    st.info("No recent workout data available to summarize.")
    st.dataframe(summary.reset_index(drop=True), use_container_width=True)
    st.line_chart(summary.set_index("Date")["Avg_RPE"])