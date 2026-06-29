import streamlit as st
import plotly.express as px
import pandas as pd
from app.ui_components import render_header
from analytics.engine import AnalyticsEngine

def render_analytics(db_manager):
    render_header(
        title="Classroom Performance Analytics",
        subtitle="Visualise class-wide attendance trends, department benchmarks, and student distributions."
    )

    analytics = AnalyticsEngine(db_manager)
    
    # KPIs
    kpis = analytics.get_kpis_today()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Avg Daily Attendance Rate", f"{kpis['attendance_rate']}%")
    with col2:
        st.metric("Active Defaulters (<75%)", kpis["defaulters_count"])
    with col3:
        st.metric("Total Enrolled Students", kpis["total_students"])
        
    st.divider()

    # Load trends dataframes
    df_daily, df_dept = analytics.get_attendance_trends()

    if df_daily.empty:
        st.info("ℹ️ No historical logs available to build analytical graphs yet.")
        return

    # Layout for charts
    row1_col1, row1_col2 = st.columns(2)
    
    with row1_col1:
        st.subheader("Daily Attendance Trend")
        fig_daily = px.line(
            df_daily,
            x="date",
            y="rate",
            labels={"date": "Date", "rate": "Attendance Rate (%)"},
            title="Daily Attendance Percentage",
            markers=True
        )
        fig_daily.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=30, b=10),
            height=300
        )
        st.plotly_chart(fig_daily, use_container_width=True)

    with row1_col2:
        st.subheader("Department Benchmarks")
        if not df_dept.empty:
            fig_dept = px.bar(
                df_dept,
                x="department",
                y="rate",
                color="department",
                labels={"department": "Department", "rate": "Avg Attendance (%)"},
                title="Average Attendance by Department"
            )
            fig_dept.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=30, b=10),
                height=300,
                showlegend=False
            )
            st.plotly_chart(fig_dept, use_container_width=True)
        else:
            st.info("No department comparison available.")

    st.write("---")
    
    row2_col1, row2_col2 = st.columns(2)
    
    with row2_col1:
        st.subheader("Attendance Health Distribution")
        # Gather health scores
        assessments = db_manager.get_risk_assessments()
        if assessments:
            df_assess = pd.DataFrame(assessments)
            df_dist = df_assess["category"].value_counts().reset_index()
            df_dist.columns = ["Status Zone", "Student Count"]
            
            fig_pie = px.pie(
                df_dist,
                names="Status Zone",
                values="Student Count",
                color="Status Zone",
                color_discrete_map={
                    "Excellent": "#38A169",
                    "Good": "#3182CE",
                    "Warning": "#DD6B20",
                    "Critical": "#E53E3E"
                },
                title="Proportion of Students in Health Status Zones"
            )
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=30, b=10),
                height=300
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No health distribution statistics yet.")

    with row2_col2:
        st.subheader("Day of the Week Attendance")
        # Extract weekday from records
        records = db_manager.get_attendance_records()
        if records:
            df_rec = pd.DataFrame(records)
            df_rec["weekday"] = df_rec["date"].apply(lambda d: pd.to_datetime(d).strftime("%A"))
            
            # Group and calculate presents vs total expected
            students = db_manager.get_all_students()
            total_students = len(students)
            
            weekday_stats = []
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]:
                day_df = df_rec[df_rec["weekday"] == day]
                if day_df.empty:
                    continue
                day_dates = day_df["date"].nunique()
                capacity = total_students * day_dates
                presents = len(day_df[day_df["verification_status"].isin(["VERIFIED", "PROXY_SUSPECT"])])
                rate = (presents / capacity) * 100.0 if capacity > 0 else 0.0
                weekday_stats.append({"Weekday": day, "Rate": round(rate, 1)})
                
            if weekday_stats:
                df_week = pd.DataFrame(weekday_stats)
                fig_week = px.bar(
                    df_week,
                    x="Weekday",
                    y="Rate",
                    labels={"Rate": "Avg Attendance (%)"},
                    title="Average Attendance by Day of Week",
                    color_discrete_sequence=["#4A5568"]
                )
                fig_week.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=300
                )
                st.plotly_chart(fig_week, use_container_width=True)
            else:
                st.info("No weekday calculations available.")
        else:
            st.info("No logs to analyze.")

    # Section for Rankings Tables
    st.write("---")
    st.subheader("Student Rankings & Performance Boards")
    top_perf, defaulters = analytics.get_student_rankings()

    col_top, col_def = st.columns(2)
    with col_top:
        st.markdown("🏆 **Top Performers (Highest Health)**")
        if top_perf:
            df_top = pd.DataFrame(top_perf)[["roll_no", "name", "department", "health_score"]]
            df_top.columns = ["Roll No", "Name", "Department", "Health Score"]
            st.table(df_top)
        else:
            st.info("No leaderboard available.")

    with col_def:
        st.markdown("🚨 **Defaulters Board (Health < 75%)**")
        if defaulters:
            df_def = pd.DataFrame(defaulters)[["roll_no", "name", "department", "health_score"]]
            df_def.columns = ["Roll No", "Name", "Department", "Health Score"]
            st.table(df_def)
        else:
            st.success("No students are below the 75% attendance threshold!")
