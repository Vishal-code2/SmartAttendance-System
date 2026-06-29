import streamlit as st

def inject_custom_css():
    
    st.markdown("""
        <style>
        /* General layout customisations */
        .main {
            background-color: #F8FAFC;
        }
        
        /* Metric cards custom styling */
        div[data-testid="stMetric"] {
            background-color: black;
            border: 1px solid #E2E8F0;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }
        
        /* Title adjustments */
        h1, h2, h3 {
            color: #1A365D !important;
            font-family: 'Outfit', 'Inter', sans-serif;
            font-weight: 700;
        }
        
        /* Glassmorphic alerts and cards */
        .glass-card {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.04);
            padding: 20px;
            margin-bottom: 20px;
        }
        
        /* Sidebar styles */
        .sidebar .sidebar-content {
            background-color: #0F172A;
        }
        
        /* Custom status badges */
        .badge {
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
            display: inline-block;
        }
        .badge-excellent { background-color: #DEF7EC; color: #03543F; }
        .badge-good { background-color: #E1EFFE; color: #1E429F; }
        .badge-warning { background-color: #FDF6B2; color: #723B13; }
        .badge-critical { background-color: #FDE8E8; color: #9B1C1C; }
        
        </style>
        """, unsafe_allow_html=True)

def render_metric_card(label: str, value: str, delta: str = None, description: str = None):
   
    with st.container():
        st.metric(label=label, value=value, delta=delta)
        if description:
            st.caption(description)

def render_header(title: str, subtitle: str):
   
    st.title(title)
    st.markdown(f"<p style='color:#718096; font-size:15px; margin-top:-15px; margin-bottom:25px;'>{subtitle}</p>", unsafe_allow_html=True)
    st.divider()
