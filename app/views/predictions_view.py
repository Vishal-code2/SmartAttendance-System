import streamlit as st
import pandas as pd
from app.ui_components import render_header
from analytics.engine import AnalyticsEngine
from ml.predictor import RiskPredictor
from app.analytics.predictor import calculate_student_features

def render_predictions(db_manager):
    render_header(
        title="Predictive Risk Center & AI Insights",
        subtitle="Machine learning forecasting of attendance drops and automated EdTech recommendations."
    )

    predictor = RiskPredictor()
    analytics = AnalyticsEngine(db_manager)

    # Left Column: ML Forecasts, Right Column: AI Insights
    ml_col, insights_col = st.columns([5, 4])

    with ml_col:
        st.subheader("Attendance Drop Risk Forecasts")
        st.markdown("This list shows students predicted to fall below the **75% attendance threshold** by the end of the term.")
        
        # Interactive Risk Slider
        risk_cutoff = st.slider("Filter Risk Cutoff Probability (%)", min_value=10, max_value=90, value=50, step=5)

        # Retrieve risk assessments
        assessments = db_manager.get_risk_assessments()
        
        if not assessments:
            st.info("No prediction data available. Make sure the database is seeded or logs are present.")
        else:
            # We want to display student risk details
            high_risk_list = []
            for r in assessments:
                if r["risk_score"] >= risk_cutoff:
                    # Get student details and recommendation
                    # Recalculate recommendation dynamically
                    student_att = db_manager.get_attendance_records(student_id=r["student_id"])
                    
                    # Calculate features to pass to predictor
                    records = db_manager.get_attendance_records()
                    total_classes = len(set(x["date"] for x in records)) if records else 1
                    
                    feats = calculate_student_features(student_att, total_classes)
                    prob, cat, recommendation = predictor.predict_risk(feats)

                    high_risk_list.append({
                        "ID": r["student_id"],
                        "Roll No": r["roll_no"],
                        "Name": r["name"],
                        "Department": r["department"],
                        "Current Health": f"{r['health_score']}%",
                        "Risk Probability": f"{r['risk_score']}%",
                        "Recommendation": recommendation
                    })
            
            if not high_risk_list:
                st.success("🎉 No students are above the specified drop-out risk threshold.")
            else:
                st.write(f"Flagged **{len(high_risk_list)}** students at risk.")
                df_risk = pd.DataFrame(high_risk_list)
                
                # Render list nicely in a loop with colored warnings or styled boxes
                for idx, row in df_risk.iterrows():
                    st.markdown(f"""
                    <div style='background-color: #FFF5F5; border-left: 4px solid #E53E3E; padding: 15px; border-radius: 4px; margin-bottom: 12px;'>
                        <span style='font-size: 14px; font-weight: bold; color: #9B1C1C;'>🚨 {row['Name']} ({row['Roll No']}) - Risk: {row['Risk Probability']}</span><br/>
                        <span style='font-size: 12px; color: #4A5568;'><b>Department:</b> {row['Department']} | <b>Current Attendance Health:</b> {row['Current Health']}</span><br/>
                        <div style='margin-top: 6px; font-size: 12px; font-style: italic; color: #2D3748; background-color: white; padding: 8px; border-radius: 4px; border: 1px solid #FEB2B2;'>
                            💡 <b>Action Recommendation:</b> {row['Recommendation']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

        # Trigger model retraining manually
        st.write("---")
        st.subheader("Model Administration")
        if st.button("🔄 Retrain ML Risk Classifier"):
            # Fetch all students and retrain
            students = db_manager.get_all_students()
            records = db_manager.get_attendance_records()
            
            if len(records) < 10:
                st.error("Cannot retrain model: Insufficient historical log records. Seed historical data first.")
            else:
                with st.spinner("Retraining Random Forest model..."):
                    # Re-run seeder training process using current DB state
                    
                    import numpy as np
                    
                    total_classes = len(set(x["date"] for x in records))
                    
                    X_train_list = []
                    y_train_list = []
                    
                    # Generate feature sets for training from current DB
                    for s in students:
                        student_att = db_manager.get_attendance_records(student_id=s.student_id)
                        feats = calculate_student_features(student_att, total_classes)
                        
                        # Label is 1 if final rate is below 75%
                        label = 1 if feats["attendance_rate"] < 0.75 else 0
                        
                        X_train_list.append([
                            feats["attendance_rate"],
                            feats["recent_attendance_rate"],
                            feats["consecutive_absences"],
                            feats["trend_slope"],
                            feats["monday_absence_rate"],
                            feats["friday_absence_rate"]
                        ])
                        y_train_list.append(label)
                    
                    df_X = pd.DataFrame(X_train_list, columns=[
                        "attendance_rate", "recent_attendance_rate", "consecutive_absences", 
                        "trend_slope", "monday_absence_rate", "friday_absence_rate"
                    ])
                    df_y = pd.Series(y_train_list)
                    
                    success = predictor.train_model(df_X, df_y)
                    if success:
                        st.success("Random Forest classifier model retrained and saved successfully!")
                        st.session_state.retrained = True
                    else:
                        st.error("Retraining failed. Check logs.")

    with insights_col:
        st.subheader("AI Automated Classroom Insights")
        st.markdown("Dynamic statistics parsed from current attendance database logs.")
        
        insights = analytics.generate_ai_insights()
        
        insights_html = "<div style='font-family: \"Outfit\", sans-serif;'>"
        for ins in insights:
            insights_html += f"""
            <div style='background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 12px 16px; border-radius: 8px; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.02);'>
                {ins}
            </div>
            """
        insights_html += "</div>"
        st.markdown(insights_html, unsafe_allow_html=True)
