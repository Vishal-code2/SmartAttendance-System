import streamlit as st
import pandas as pd
from app.ui_components import render_header
from ml.predictor import seed_historical_data

def render_audit(db_manager):
    render_header(
        title="System Audit Trail & Administration",
        subtitle="Track administrator actions, automated system marks, and database maintenance."
    )

    tab1, tab2 = st.tabs(["📝 Audit Logs", "🛡️ Database Administration"])

    # --- TAB 1: AUDIT LOGS ---
    with tab1:
        st.subheader("Action Event Logs")
        
        limit = st.slider("Max Logs to Retrieve", min_value=10, max_value=500, value=100, step=10)
        logs = db_manager.get_audit_logs(limit=limit)

        if not logs:
            st.info("No system action logs recorded yet.")
        else:
            log_data = []
            for l in logs:
                log_data.append({
                    "Log ID": l.log_id,
                    "Timestamp": l.timestamp,
                    "Action Performed": l.action,
                    "Triggered By": l.user
                })
            
            df_logs = pd.DataFrame(log_data)
            st.dataframe(df_logs, width="stretch")

    # --- TAB 2: DATABASE ADMINISTRATION ---
    with tab2:
        st.subheader("System Seeding & Setup Tools")
        st.info("Use these actions to clean the database, register mock student directories, and seed historical class logs to test prediction graphs.")

        col_seed, col_clear = st.columns(2)

        with col_seed:
            st.markdown("### Seeding Tool")
            st.markdown("Seeds the database with **10 students** across 4 departments, registers fake face encodings, logs **60 days of historical logs** (with varying attendance patterns), and trains the ML classifier.")
            if st.button("🌱 Seed Mock Student & Logs"):
                with st.spinner("Seeding database and training Machine Learning model..."):
                    success = seed_historical_data(db_manager)
                    if success:
                        st.success("Successfully seeded historical logs and trained classifier!")
                        st.balloons()
                    else:
                        st.error("Failed to seed. View console logs.")

        with col_clear:
            st.markdown("### Database Sanitisation")
            st.markdown("Performs a complete clean: wipes out all attendance, risk records, and action logs from the SQLite tables.")
            if st.button("🗑️ Clear All Activity Logs"):
                with st.spinner("Wiping activity records..."):
                    success = db_manager.clear_historical_data()
                    if success:
                        st.success("Successfully cleared attendance logs and risk logs!")
                    else:
                        st.error("Failed to wipe data.")
