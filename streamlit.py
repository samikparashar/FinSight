import streamlit as st
from main import run_pipeline   # your function

st.set_page_config(page_title="FinSight", layout="wide")

st.title("📊 FinSight - AI Financial Analyst")

company = st.text_input("Enter Company Name")

if st.button("Generate Report"):
    with st.spinner("Analyzing..."):
        result = run_pipeline(company)

    st.subheader("📝 Final Report")
    st.write(result)