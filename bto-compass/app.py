# app.py
import streamlit as st
from langchain_core.messages import HumanMessage
from src.graph import app_graph
from src.cost_tracker import UsageTracker
from src.extractors import extract_income_from_pdf

st.set_page_config(page_title="BTO Compass", layout="wide")
st.title("🏡 BTO Compass AI Assistant")

tracker = UsageTracker()

# Safe default session state initialization dictionary
DEFAULTS = {
    "monthly_income": 0.0,
    "budget": 500000.0,
    "is_first_timer": True,
    "preferred_towns": [],
    "max_wait": 5.0,
    "applicant_type": "couple",
    "messages": []
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val
        
# Initialize session state variables
if "monthly_income" not in st.session_state:
    st.session_state["monthly_income"] = 0.0
if "budget" not in st.session_state:
    st.session_state["budget"] = 500000.0
if "is_first_timer" not in st.session_state:
    st.session_state["is_first_timer"] = True
if "preferred_towns" not in st.session_state:
    st.session_state["preferred_towns"] = []
if "max_wait" not in st.session_state:
    st.session_state["max_wait"] = 5.0
if "applicant_type" not in st.session_state:
    st.session_state["applicant_type"] = "couple"
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar Controls & Document Uploader
with st.sidebar:
    st.header("📄 Payslip Auto-Fill")
    uploaded_pdf = st.file_uploader("Upload Payslip (PDF)", type=["pdf"])
    if uploaded_pdf and st.button("Extract Income"):
        pdf_bytes = uploaded_pdf.read()
        try:
            extracted = extract_income_from_pdf(pdf_bytes)
            st.session_state["monthly_income"] = float(extracted.gross_income)
            st.success(f"Extracted Income: ${extracted.gross_income:,.2f} SGD")
        except Exception as e:
            st.error(f"Error extracting income: {e}")

    st.divider()
    st.header("👤 Applicant Profile")
    
    # Household income
    monthly_income = st.number_input(
        "Gross Monthly Household Income (SGD)",
        min_value=0.0,
        value=float(st.session_state["monthly_income"]),
        step=500.0
    )
    st.session_state["monthly_income"] = monthly_income

    # Max budget
    budget = st.number_input(
        "Max Housing Budget (SGD)",
        min_value=100000.0,
        max_value=2000000.0,
        value=float(st.session_state["budget"]),
        step=25000.0
    )
    st.session_state["budget"] = budget

    # Preferred towns
    preferred_towns = st.multiselect(
        "Preferred Towns",
        options=["Yishun", "Kallang / Whampoa", "Bishan", "Tampines", "Punggol", "Jurong East", "Woodlands", "Bedok"],
        default=st.session_state["preferred_towns"]
    )
    st.session_state["preferred_towns"] = preferred_towns

    # Maximum waiting time in years
    max_wait = st.slider(
        "Max Waiting Time (Years)",
        min_value=1.0,
        max_value=10.0,
        value=float(st.session_state["max_wait"]),
        step=0.5
    )
    st.session_state["max_wait"] = max_wait

    # Applicant type
    applicant_type_label = st.selectbox(
        "Applicant Type",
        options=["Couple / Family", "Single (35+)"],
        index=0 if st.session_state["applicant_type"] == "couple" else 1
    )
    st.session_state["applicant_type"] = "couple" if applicant_type_label == "Couple / Family" else "single"

    # First-timer checkbox
    is_first_timer = st.checkbox(
        "First-Time BTO Applicant",
        value=st.session_state["is_first_timer"]
    )
    st.session_state["is_first_timer"] = is_first_timer

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Chat Input
# app.py (Inside chat input handler)
if prompt := st.chat_input("Ask about BTO eligibility, housing grants, or flat recommendations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Explicit fallbacks for every field
        applicant_data = {
            "monthly_income": float(st.session_state.get("monthly_income") or 0.0),
            "is_first_timer": bool(st.session_state.get("is_first_timer", True)),
            "budget": float(st.session_state.get("budget") or 500000.0),
            "preferred_towns": st.session_state.get("preferred_towns") or [],
            "max_wait": float(st.session_state.get("max_wait") or 5.0),
            "applicant_type": str(st.session_state.get("applicant_type") or "couple")
        }

        with st.spinner("Analyzing housing options..."):
            response = app_graph.invoke({
                "messages": [HumanMessage(content=prompt)],
                "applicant": applicant_data
            })

        # Extract output cleanly
        if isinstance(response, dict) and "explanation" in response:
            assistant_output = response["explanation"]
        elif isinstance(response, dict) and "messages" in response and response["messages"]:
            last_msg = response["messages"][-1]
            assistant_output = getattr(last_msg, "content", str(last_msg))
        else:
            assistant_output = "No recommendations found."

        st.markdown(assistant_output)
        st.session_state.messages.append({"role": "assistant", "content": assistant_output})

        # Token cost tracking (if response metadata exists)
        if isinstance(response, dict) and "messages" in response and response["messages"]:
            last_msg = response["messages"][-1]
            if hasattr(last_msg, "response_metadata") and "usage" in last_msg.response_metadata:
                usage = last_msg.response_metadata["usage"]
                cost = tracker.calculate_cost(usage)
                st.caption(f"⚡ Token Cost: ${cost:.5f} USD | Total Tokens: {usage.get('total_tokens', 0)}")
