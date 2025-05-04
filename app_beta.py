
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

# === LOAD CLIENT CODES ===
try:
    sheet = client.open_by_key(SHEET_KEY)
    worksheet_codes = sheet.worksheet("Client_Codes")
    raw_values = worksheet_codes.get_all_values()

    headers = raw_values[0]
    rows = raw_values[1:]
    code_df = pd.DataFrame(rows, columns=headers)
    CLIENT_CODES = dict(zip(code_df["Client Name"].str.strip().str.lower(), code_df["Access Code"]))
except Exception as e:
    st.error("⚠️ Failed to read Client_Codes tab.")
    st.code(str(e))
    st.stop()

# === STREAMLIT UI ===
st.set_page_config(page_title="Training Log", layout="wide")
st.title("Client Training Log")
st.image("bodylab_logo_clean.png", width=180)


client_name = st.text_input("Enter Your Name", placeholder="e.g. Alex")
client_code = st.text_input("Enter Your Access Code", placeholder="e.g. code123", type="password")

if not client_name or not client_code:
    st.stop()

client_key = client_name.strip().lower()
if client_key not in CLIENT_CODES or CLIENT_CODES[client_key] != client_code:
    st.error("Invalid client code. Please try again or contact your coach.")
    st.stop()

# ✅ Now show refresh button AFTER login success
if st.button("🔄 Refresh to Load New Template"):
    st.rerun()

# === LOAD CLIENT WORKOUT TEMPLATE ===
try:
    worksheet = sheet.worksheet(client_name.title())
    records = worksheet.get_all_records()
    df_template = pd.DataFrame(records)
except Exception as e:
    st.error(f"Failed to load Google Sheet tab for {client_name}: {e}")
    st.stop()

available_workouts = df_template["Workout #"].dropna().unique().tolist()
selected_workout = st.selectbox("Select Workout", available_workouts)
df_selected = df_template[df_template["Workout #"] == selected_workout]

if df_selected.empty:
    st.warning("No exercises found for this workout.")
    st.stop()

log_date = st.date_input("Enter Date of Workout", value=datetime.date.today())

st.markdown(f"### 📋 {selected_workout} Overview")
st.dataframe(df_selected[["Code", "Pattern", "Exercise", "Sets", "Reps", "Demo"]].reset_index(drop=True), use_container_width=True)

st.markdown("### 📝 Log RPE, Notes & Mark Completion")
log_file = LOG_DIR / client_key / "history_log.xlsx"
prev_logs = pd.DataFrame()
if log_file.exists():
    prev_logs = pd.read_excel(log_file)
    prev_logs["Date"] = pd.to_datetime(prev_logs["Date"])

entries = []
for i, row in df_selected.iterrows():
    past_rpe = None
    if not prev_logs.empty:
        match = prev_logs[
            (prev_logs["Exercise #"] == row["Code"]) &
            (prev_logs["Exercise"] == row["Exercise"])
        ].sort_values("Date", ascending=False)
        if not match.empty:
            past_rpe = match.iloc[0]["RPE"]

    with st.container():
        st.markdown(f"**{row['Code']} - {row['Exercise']}** | Sets: {row['Sets']} | Reps: {row['Reps']} | Pattern: {row['Pattern']}")
        cols = st.columns([1, 3, 1])
        rpe = cols[0].selectbox("RPE", options=list(range(1, 11)), index=(int(past_rpe)-1) if past_rpe else 5, key=f"rpe_{i}")
        note = cols[1].text_input("Notes", key=f"note_{i}")
        checked = cols[2].checkbox("Done", key=f"done_{i}")
        entries.append({
            "Client": client_name.title(),
            "Date": log_date,
            "Workout #": selected_workout,
            "Exercise #": row["Code"],
            "Movement Pattern": row["Pattern"],
            "Exercise": row["Exercise"],
            "Sets": row["Sets"],
            "Reps": row["Reps"],
            "Demo": row["Demo"],
            "RPE": rpe,
            "Notes": note,
            "Completed": checked
        })

if st.button("✅ Save Workout Log"):
    df_log = pd.DataFrame(entries)
    client_dir = LOG_DIR / client_key
    client_dir.mkdir(parents=True, exist_ok=True)

    if log_file.exists():
        old_df = pd.read_excel(log_file)
        df_log = pd.concat([old_df, df_log], ignore_index=True)

    df_log.to_excel(log_file, index=False)
    st.success("✅ Saved to logs, great work!")

    st.markdown("### ✅ Weekly Completion Summary")
    recent = df_log[pd.to_datetime(df_log["Date"]) >= pd.Timestamp.now() - pd.Timedelta(days=7)]
    summary = recent.groupby(["Workout #", "Date"]).agg(
        Exercises=("Exercise", "count"),
        Completed=("Completed", "sum"),
        Avg_RPE=("RPE", "mean")
    ).reset_index().sort_values(by=["Date"], ascending=False)
    st.dataframe(summary.reset_index(drop=True), use_container_width=True)
