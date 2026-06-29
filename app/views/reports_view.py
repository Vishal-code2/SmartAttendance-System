import os
import streamlit as st
from app.ui_components import render_header
from reports.generator import ReportGenerator

def render_reports(db_manager):
    render_header(
        title="Report Generation Center",
        subtitle="Export polished executive PDF summaries, Excel sheets, and raw CSV dumps."
    )

    generator = ReportGenerator(db_manager)
    students = db_manager.get_all_students()

    col1, col2, col3 = st.columns(3)

    # --- Student Report Section ---
    with col1:
        st.subheader("Student Report Card")
        st.markdown("Generates detail sheet on student attendance, health scores, and ML logs.")
        
        r_student_id = st.selectbox("Select Student", [""] + [f"{s.student_id} - {s.name}" for s in students], key="rep_student")
        r_student_format = st.selectbox("Format", ["pdf", "xlsx", "csv"], key="rep_student_format")
        
        if st.button("Generate Student Report", key="rep_student_btn"):
            if not r_student_id:
                st.error("Please select a student.")
            else:
                sid = r_student_id.split(" - ")[0]
                with st.spinner("Generating report..."):
                    path = generator.generate_student_report(sid, r_student_format)
                    if path and os.path.exists(path):
                        st.success("Report generated!")
                        with open(path, "rb") as f:
                            btn = st.download_button(
                                label=f"⬇️ Download {r_student_format.upper()}",
                                data=f.read(),
                                file_name=os.path.basename(path),
                                mime=_get_mime_type(r_student_format)
                            )
                    else:
                        st.error("Failed to generate report.")

    # --- Class Report Section ---
    with col2:
        st.subheader("Class Summary Report")
        st.markdown("Generates analytics sheet detailing roll lists, presence tallies, and defaulters.")
        
        departments = list(set(s.department for s in students))
        r_dept = st.selectbox("Select Department", [""] + departments, key="rep_class_dept")
        
        years = list(set(s.year for s in students))
        r_year = st.selectbox("Select Academic Year", [""] + years, key="rep_class_year")
        
        r_class_format = st.selectbox("Format", ["pdf", "xlsx", "csv"], key="rep_class_format")
        
        if st.button("Generate Class Report", key="rep_class_btn"):
            if not r_dept or not r_year:
                st.error("Please specify both Department and Academic Year.")
            else:
                with st.spinner("Generating class report..."):
                    path = generator.generate_class_report(r_dept, r_year, r_class_format)
                    if path and os.path.exists(path):
                        st.success("Report generated!")
                        with open(path, "rb") as f:
                            st.download_button(
                                label=f"⬇️ Download {r_class_format.upper()}",
                                data=f.read(),
                                file_name=os.path.basename(path),
                                mime=_get_mime_type(r_class_format)
                            )
                    else:
                        st.error("Failed to generate report.")

    # --- Faculty Summary Section ---
    with col3:
        st.subheader("Faculty Summary")
        st.markdown("Generates high-level summaries highlighting AI insights, risks, and audit indicators.")
        
        r_fac_dept = st.selectbox("Select Department", [""] + departments, key="rep_fac_dept")
        r_fac_format = st.selectbox("Format", ["pdf", "xlsx", "csv"], key="rep_fac_format")
        
        if st.button("Generate Faculty Report", key="rep_fac_btn"):
            if not r_fac_dept:
                st.error("Please select a department.")
            else:
                with st.spinner("Generating departmental summary..."):
                    path = generator.generate_faculty_report(r_fac_dept, r_fac_format)
                    if path and os.path.exists(path):
                        st.success("Report generated!")
                        with open(path, "rb") as f:
                            st.download_button(
                                label=f"⬇️ Download {r_fac_format.upper()}",
                                data=f.read(),
                                file_name=os.path.basename(path),
                                mime=_get_mime_type(r_fac_format)
                            )
                    else:
                        st.error("Failed to generate report.")


def _get_mime_type(format_type: str) -> str:
    if format_type == "pdf":
        return "application/pdf"
    elif format_type == "xlsx":
        return "application/vnd.ms-excel"
    else:
        return "text/csv"
