import os
import datetime
import pandas as pd
from typing import List, Dict, Any, Optional
from pathlib import Path
from config import config
from utils.logger import setup_logger

# ReportLab Imports
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

logger = setup_logger("reports")

class NumberedCanvas(canvas.Canvas):
    """Custom canvas to compute page numbers dynamically and add headers/footers."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#7A8B9E"))
        
        # Header
        self.drawString(54, 750, "SmartAttend AI - Intelligent Classroom Platform")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 742, 558, 742)
        
        # Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 40, page_text)
        self.drawString(54, 40, f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.line(54, 52, 558, 52)
        
        self.restoreState()


class ReportGenerator:
    def __init__(self, db_manager):
        self.db = db_manager
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        # Custom styles for reports
        self.primary_color = colors.HexColor("#1A365D")  # Navy
        self.secondary_color = colors.HexColor("#2B6CB0")  # Blue
        self.text_dark = colors.HexColor("#2D3748")  # Slate
        self.text_muted = colors.HexColor("#718096")  # Light Grey
        
        self.title_style = ParagraphStyle(
            'DocTitle',
            parent=self.styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=self.primary_color,
            spaceAfter=15
        )
        
        self.subtitle_style = ParagraphStyle(
            'DocSubTitle',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=self.text_muted,
            spaceAfter=25
        )
        
        self.section_heading = ParagraphStyle(
            'SectionHeading',
            parent=self.styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=self.primary_color,
            spaceBefore=15,
            spaceAfter=10,
            keepWithNext=True
        )

        self.body_style = ParagraphStyle(
            'DocBody',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            textColor=self.text_dark
        )

        self.table_cell_style = ParagraphStyle(
            'TableCell',
            parent=self.styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=self.text_dark
        )

        self.table_header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white
        )

    def _get_health_color_hex(self, category: str) -> str:
        if category == "Excellent":
            return "#38A169" # Green
        elif category == "Good":
            return "#3182CE" # Blue
        elif category == "Warning":
            return "#DD6B20" # Orange
        else:
            return "#E53E3E" # Red

    # --- STUDENT REPORT ---
    def generate_student_report(self, student_id: str, format_type: str = "pdf") -> Optional[str]:
        """
        Generate detailed attendance and risk report for a single student.
        Returns the absolute path to the generated file.
        """
        student = self.db.get_student(student_id)
        if not student:
            logger.error(f"Student {student_id} not found to generate report.")
            return None

        # Fetch records & risk
        records = self.db.get_attendance_records(student_id=student_id)
        risk = self.db.get_risk_assessment(student_id)
        
        health_score = risk.health_score if risk else 100.0
        health_category = risk.category if risk else "Excellent"
        risk_score = risk.risk_score if risk else 0.0

        presents = [r for r in records if r["verification_status"] in ("VERIFIED", "PROXY_SUSPECT")]
        present_count = len(presents)
        absent_count = len([r for r in records if r["verification_status"] == "ABSENT"])
        total_classes = len(records)
        attendance_percentage = (present_count / total_classes * 100.0) if total_classes > 0 else 100.0

        # Filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Student_Report_{student_id}_{timestamp}.{format_type}"
        file_path = str(config.EXPORT_DIR / filename)

        if format_type == "csv":
            df = pd.DataFrame(records)
            if not df.empty:
                df.to_csv(file_path, index=False)
            else:
                with open(file_path, "w") as f:
                    f.write("No records found")
            return file_path

        elif format_type == "xlsx":
            df = pd.DataFrame(records)
            if not df.empty:
                # Reorder columns nicely
                cols = ["date", "time", "confidence_score", "verification_status"]
                df = df[cols]
                df.to_excel(file_path, index=False, sheet_name="Attendance Details")
                
                # Format sheet (can add styling using openpyxl later if needed, simple export satisfies core requirement)
            else:
                pd.DataFrame([{"Message": "No logs"}]).to_excel(file_path, index=False)
            return file_path

        elif format_type == "pdf":
            # PDF Generation with ReportLab
            doc = SimpleDocTemplate(
                file_path,
                pagesize=letter,
                leftMargin=54,
                rightMargin=54,
                topMargin=72,
                bottomMargin=72
            )
            story = []

            # Title & Subtitle
            story.append(Paragraph(f"SmartAttend Student Attendance Report", self.title_style))
            story.append(Paragraph(f"Personal analytics report for {student.name} ({student.student_id})", self.subtitle_style))
            story.append(Spacer(1, 10))

            # Student Info Table
            info_data = [
                [
                    Paragraph("<b>Student ID:</b>", self.body_style), Paragraph(student.student_id, self.body_style),
                    Paragraph("<b>Department:</b>", self.body_style), Paragraph(student.department, self.body_style)
                ],
                [
                    Paragraph("<b>Roll Number:</b>", self.body_style), Paragraph(student.roll_no, self.body_style),
                    Paragraph("<b>Year/Division:</b>", self.body_style), Paragraph(f"{student.year} - Div {student.division}", self.body_style)
                ],
                [
                    Paragraph("<b>Email:</b>", self.body_style), Paragraph(student.email, self.body_style),
                    Paragraph("<b>Phone:</b>", self.body_style), Paragraph(student.phone, self.body_style)
                ]
            ]
            info_table = Table(info_data, colWidths=[100, 150, 100, 150])
            info_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            story.append(info_table)
            story.append(Spacer(1, 20))

            # Metrics / KPIs Panel Table
            health_color = self._get_health_color_hex(health_category)
            kpi_data = [
                [
                    Paragraph("<b>Overall Attendance</b>", self.body_style),
                    Paragraph("<b>Attendance Health Score</b>", self.body_style),
                    Paragraph("<b>Class Risk Status</b>", self.body_style)
                ],
                [
                    Paragraph(f"<font size=16 color='{self.secondary_color.hexval()}'><b>{round(attendance_percentage, 1)}%</b></font><br/>{present_count} / {total_classes} Classes", self.body_style),
                    Paragraph(f"<font size=16 color='{health_color}'><b>{health_score} / 100</b></font><br/>Status: {health_category}", self.body_style),
                    Paragraph(f"<font size=16 color='{colors.HexColor('#E53E3E').hexval() if risk_score > 50 else self.primary_color.hexval()}'><b>{risk_score}%</b></font><br/>ML Risk Score", self.body_style)
                ]
            ]
            kpi_table = Table(kpi_data, colWidths=[166, 166, 166])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 25))

            # Attendance Log Table
            story.append(Paragraph("Detailed Attendance Log", self.section_heading))
            
            table_data = [[
                Paragraph("<b>Date</b>", self.table_header_style),
                Paragraph("<b>Time</b>", self.table_header_style),
                Paragraph("<b>Confidence Score</b>", self.table_header_style),
                Paragraph("<b>Verification Status</b>", self.table_header_style)
            ]]

            for r in records[:50]:  # Limit to last 50 for clean reporting representation
                status_color = "#38A169" if r["verification_status"] == "VERIFIED" else ("#DD6B20" if r["verification_status"] == "PROXY_SUSPECT" else "#E53E3E")
                table_data.append([
                    Paragraph(r["date"], self.table_cell_style),
                    Paragraph(r["time"], self.table_cell_style),
                    Paragraph(f"{int(r['confidence_score'] * 100)}%", self.table_cell_style),
                    Paragraph(f"<font color='{status_color}'><b>{r['verification_status']}</b></font>", self.table_cell_style)
                ])

            log_table = Table(table_data, colWidths=[120, 100, 130, 150])
            log_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            story.append(log_table)

            if len(records) > 50:
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"<i>Showing latest 50 logs out of {len(records)} records. Please export to Excel/CSV for full logs.</i>", self.body_style))

            # Build Document
            doc.build(story, canvasmaker=NumberedCanvas)
            return file_path

    # --- CLASS REPORT ---
    def generate_class_report(self, department: str, year: str, format_type: str = "pdf") -> Optional[str]:
        """
        Generate summary report for a specific class/year/department.
        """
        students = self.db.get_all_students(department=department)
        students = [s for s in students if s.year == year]
        
        if not students:
            logger.error(f"No students found in class: {department} - {year}")
            return None

        # Fetch records
        records = self.db.get_attendance_records(department=department)
        df_records = pd.DataFrame(records)
        if not df_records.empty:
            df_records = df_records[df_records["year"] == year]

        # Process stats
        student_summaries = []
        total_sessions = df_records["date"].nunique() if not df_records.empty else 0
        
        for s in students:
            s_rec = df_records[df_records["student_id"] == s.student_id] if not df_records.empty else pd.DataFrame()
            presents = len(s_rec[s_rec["verification_status"].isin(["VERIFIED", "PROXY_SUSPECT"])]) if not s_rec.empty else 0
            absents = total_sessions - presents
            pct = (presents / total_sessions * 100.0) if total_sessions > 0 else 100.0
            
            risk = self.db.get_risk_assessment(s.student_id)
            health = risk.health_score if risk else 100.0
            category = risk.category if risk else "Excellent"

            student_summaries.append({
                "student_id": s.student_id,
                "name": s.name,
                "roll_no": s.roll_no,
                "present_count": presents,
                "absent_count": absents,
                "attendance_percentage": round(pct, 1),
                "health_score": health,
                "health_category": category
            })

        df_summary = pd.DataFrame(student_summaries).sort_values("roll_no")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dept_clean = department.replace(" ", "_")
        filename = f"Class_Report_{dept_clean}_{year.replace(' ', '_')}_{timestamp}.{format_type}"
        file_path = str(config.EXPORT_DIR / filename)

        if format_type == "csv":
            df_summary.to_csv(file_path, index=False)
            return file_path

        elif format_type == "xlsx":
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df_summary.to_excel(writer, index=False, sheet_name="Class Summary")
                if not df_records.empty:
                    df_records[["student_id", "name", "date", "time", "confidence_score", "verification_status"]].to_excel(
                        writer, index=False, sheet_name="Raw Logs"
                    )
            return file_path

        elif format_type == "pdf":
            doc = SimpleDocTemplate(
                file_path,
                pagesize=letter,
                leftMargin=54,
                rightMargin=54,
                topMargin=72,
                bottomMargin=72
            )
            story = []

            # Header
            story.append(Paragraph(f"Class Performance Report", self.title_style))
            story.append(Paragraph(f"Academic Report for {department} - {year} (Total: {len(students)} Students, {total_sessions} Sessions)", self.subtitle_style))
            story.append(Spacer(1, 10))

            # Class KPIs
            avg_att = df_summary["attendance_percentage"].mean() if not df_summary.empty else 100.0
            defaulters_count = len(df_summary[df_summary["attendance_percentage"] < 75.0])
            avg_health = df_summary["health_score"].mean() if not df_summary.empty else 100.0

            kpi_data = [
                [
                    Paragraph("<b>Class Average Attendance</b>", self.body_style),
                    Paragraph("<b>Average Health Score</b>", self.body_style),
                    Paragraph("<b>Students Below 75%</b>", self.body_style)
                ],
                [
                    Paragraph(f"<font size=16 color='{self.secondary_color.hexval()}'><b>{round(avg_att, 1)}%</b></font>", self.body_style),
                    Paragraph(f"<font size=16 color='{self.primary_color.hexval()}'><b>{round(avg_health, 1)} / 100</b></font>", self.body_style),
                    Paragraph(f"<font size=16 color='{colors.HexColor('#E53E3E').hexval() if defaulters_count > 0 else self.primary_color.hexval()}'><b>{defaulters_count}</b></font>", self.body_style)
                ]
            ]
            kpi_table = Table(kpi_data, colWidths=[166, 166, 166])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 20))

            # Student list table
            story.append(Paragraph("Student Performance Metrics", self.section_heading))
            
            table_data = [[
                Paragraph("<b>Roll No</b>", self.table_header_style),
                Paragraph("<b>Name</b>", self.table_header_style),
                Paragraph("<b>Presents / Total</b>", self.table_header_style),
                Paragraph("<b>Att. %</b>", self.table_header_style),
                Paragraph("<b>Health Score</b>", self.table_header_style),
                Paragraph("<b>Risk category</b>", self.table_header_style)
            ]]

            for _, row in df_summary.iterrows():
                h_color = self._get_health_color_hex(row["health_category"])
                table_data.append([
                    Paragraph(row["roll_no"], self.table_cell_style),
                    Paragraph(row["name"], self.table_cell_style),
                    Paragraph(f"{row['present_count']} / {total_sessions}", self.table_cell_style),
                    Paragraph(f"{row['attendance_percentage']}%", self.table_cell_style),
                    Paragraph(f"<b>{row['health_score']}</b>", self.table_cell_style),
                    Paragraph(f"<font color='{h_color}'><b>{row['health_category']}</b></font>", self.table_cell_style)
                ])

            summary_table = Table(table_data, colWidths=[60, 140, 90, 60, 70, 80])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            story.append(summary_table)

            doc.build(story, canvasmaker=NumberedCanvas)
            return file_path
            
    # --- FACULTY SUMMARY REPORT ---
    def generate_faculty_report(self, department: str, format_type: str = "pdf") -> Optional[str]:
        """
        Generate high-level departmental faculty summary report including AI insights.
        """
        students = self.db.get_all_students(department=department)
        if not students:
            logger.error(f"No students found in department: {department}")
            return None

        # Analytics calculations
        from analytics.engine import AnalyticsEngine
        analytics = AnalyticsEngine(self.db)
        
        # Trends
        df_daily, df_dept = analytics.get_attendance_trends()
        
        # Insights
        insights = analytics.generate_ai_insights()
        
        # Get risk items
        assessments = self.db.get_risk_assessments()
        dept_risk = [r for r in assessments if r["department"] == department]
        defaulters = [r for r in dept_risk if r["health_score"] < 75.0]

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Faculty_Report_{department.replace(' ', '_')}_{timestamp}.{format_type}"
        file_path = str(config.EXPORT_DIR / filename)

        if format_type != "pdf":
            # Excel / CSV exports of department assessment
            df_risk = pd.DataFrame(dept_risk)
            if format_type == "xlsx":
                df_risk.to_excel(file_path, index=False)
            else:
                df_risk.to_csv(file_path, index=False)
            return file_path

        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=72,
            bottomMargin=72
        )
        story = []

        # Header
        story.append(Paragraph(f"Faculty Departmental Dashboard Report", self.title_style))
        story.append(Paragraph(f"Summary Report for the {department} Department (Total: {len(students)} Enrolled Students)", self.subtitle_style))
        story.append(Spacer(1, 10))

        # Dynamic AI Insights section
        story.append(Paragraph("AI-Generated Classroom Insights", self.section_heading))
        for ins in insights:
            story.append(Paragraph(f"• {ins}", self.body_style))
            story.append(Spacer(1, 4))
        
        story.append(Spacer(1, 15))

        # Risk Actions Table
        story.append(Paragraph("Immediate Intervention Required (Defaulters & High-Risk)", self.section_heading))
        if not defaulters:
            story.append(Paragraph("Excellent! No students are currently in the risk categories.", self.body_style))
        else:
            table_data = [[
                Paragraph("<b>Roll No</b>", self.table_header_style),
                Paragraph("<b>Name</b>", self.table_header_style),
                Paragraph("<b>Health Score</b>", self.table_header_style),
                Paragraph("<b>ML Risk Probability</b>", self.table_header_style),
                Paragraph("<b>Recommended Intervention Action</b>", self.table_header_style)
            ]]

            for r in sorted(defaulters, key=lambda x: x["risk_score"], reverse=True)[:10]:  # Show top 10 at risk
                # Action recommendation text based on risk score
                rec_text = "Schedule Parent Meeting" if r["risk_score"] > 70.0 else "Send Official Attendance Alert Email"
                table_data.append([
                    Paragraph(r["roll_no"], self.table_cell_style),
                    Paragraph(r["name"], self.table_cell_style),
                    Paragraph(f"<b>{r['health_score']}</b>", self.table_cell_style),
                    Paragraph(f"<font color='red'><b>{r['risk_score']}%</b></font>", self.table_cell_style),
                    Paragraph(rec_text, self.table_cell_style)
                ])

            risk_table = Table(table_data, colWidths=[50, 100, 70, 100, 180])
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), self.primary_color),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            story.append(risk_table)

        doc.build(story, canvasmaker=NumberedCanvas)
        return file_path
