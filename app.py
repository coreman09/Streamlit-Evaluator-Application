import pandas as pd
import streamlit as st

# Load mileage data
df = pd.read_csv("Evaluator_Customer_Mileage.csv")

# Sidebar filters
st.sidebar.header("Filter Options")
customer = st.sidebar.selectbox("Select Customer", sorted(df['Customer'].unique()))
evaluator = st.sidebar.selectbox("Filter by Evaluator (optional)", ["All"] + sorted(df['Evaluator'].unique()))

# Filtered results
filtered = df[df['Customer'] == customer]
if evaluator != "All":
    filtered = filtered[filtered['Evaluator'] == evaluator]

# Sort and display
filtered = filtered.sort_values(by='Round-Trip Miles')
st.title("Evaluator Distance & Cost Viewer")
st.subheader(f"Closest Evaluators to: {customer}")
st.dataframe(filtered[['Evaluator', 'One-Way Miles', 'Round-Trip Miles', 'Drive Time (min)', 'Cost ($)']])