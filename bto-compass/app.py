import streamlit as st
import pandas as pd
from src.graph import app_graph

st.set_page_config(page_title="BTO Compass", layout="wide")

st.title("🧭 BTO Compass MVP")
st.markdown("Find the best HDB BTO project based on your constraints.")

# Sidebar for User Inputs
st.sidebar.header("Applicant Profile")
applicant_type = st.sidebar.selectbox("Applicant Type", ["single", "family", "joint"])
age = st.sidebar.number_input("Age", min_value=21, max_value=99, value=35)
budget = st.sidebar.slider("Budget (SGD)", min_value=100000, max_value=1000000, value=300000, step=10000)
max_wait = st.sidebar.slider("Max Wait Time (Years)", min_value=1.0, max_value=7.0, value=4.0, step=0.1)
towns = st.sidebar.multiselect(
    "Preferred Towns", 
    ["Tampines", "Toa Payoh", "Sembawang", "Yishun", "Jurong West"],
    default=["Tampines", "Toa Payoh", "Sembawang"]
)

if st.sidebar.button("Find My BTO"):
    initial_state = {
        "applicant": {
            "applicant_type": applicant_type,
            "age": age,
            "budget": budget,
            "max_wait": max_wait,
            "preferred_towns": towns
        },
        "iteration_count": 0
    }
    
    with st.spinner("Analyzing projects and referencing HDB policies..."):
        # Run the LangGraph workflow
        final_state = app_graph.invoke(initial_state)
        
    st.success("Analysis Complete!")
    
    # Display Top 3 Recommendations
    st.subheader("🏆 Top 3 Recommendations")
    if final_state.get("rankings"):
        df_rankings = pd.DataFrame(final_state["rankings"])
        st.dataframe(df_rankings, use_container_width=True, hide_index=True)
    else:
        st.warning("No projects match your current budget and wait time constraints.")
        
    # Display LLM Explanation
    st.subheader("🤖 AI Advisor Rationale")
    st.markdown(final_state["explanation"])
