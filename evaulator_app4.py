import streamlit as st
import pandas as pd

# Load and clean data
df = pd.read_csv("Evaluator_Customer_Mileage.csv")
df.columns = df.columns.str.strip()  # Remove leading/trailing spaces

# Rename cost column to consistent casing
if "Cost ($)" in df.columns:
    df.rename(columns={"Cost ($)": "cost ($)"}, inplace=True)

# Drop one-way miles if present
if "One-Way Miles" in df.columns:
    df.drop(columns=["One-Way Miles"], inplace=True)

# Sidebar filters
st.sidebar.header("Filter Options")
selected_customers = st.sidebar.multiselect(
    "Select Customers",
    options=sorted(df['Customer'].unique()),
    default=[]
)

selected_evaluators = st.sidebar.multiselect(
    "Select Evaluators",
    options=sorted(df['Evaluator'].unique()),
    default=[]
)

# Apply filters
filtered_df = df.copy()
if selected_customers:
    filtered_df = filtered_df[filtered_df['Customer'].isin(selected_customers)]
if selected_evaluators:
    filtered_df = filtered_df[filtered_df['Evaluator'].isin(selected_evaluators)]

# Ensure numeric columns
filtered_df['Round-Trip Miles'] = pd.to_numeric(filtered_df.get('Round-Trip Miles'), errors='coerce')
filtered_df['cost ($)'] = pd.to_numeric(filtered_df.get('cost ($)'), errors='coerce')

# Add Per Diem
filtered_df['Per Diem'] = filtered_df['Round-Trip Miles'].apply(
    lambda x: 225 if pd.notnull(x) and x > 175 else 0
)

# Add Mileage Bonus
def mileage_bonus(miles):
    if pd.isnull(miles):
        return 0
    elif miles > 800:
        return 500
    elif miles > 400:
        return 250
    else:
        return 0

filtered_df['Mileage Bonus'] = filtered_df['Round-Trip Miles'].apply(mileage_bonus)

# Add Total Cost
filtered_df['Total Cost'] = (
    filtered_df['cost ($)'].fillna(0) +
    filtered_df['Per Diem'] +
    filtered_df['Mileage Bonus']
)

# Format currency columns
for col in ['cost ($)', 'Per Diem', 'Mileage Bonus', 'Total Cost']:
    if col in filtered_df.columns:
        filtered_df[col] = filtered_df[col].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")

# Display results with no index
st.subheader("Closest Evaluator per Customer")
st.data_editor(filtered_df, use_container_width=True, disabled=True)

# Download button (no index column)
csv = filtered_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Filtered Data as CSV",
    data=csv,
    file_name="filtered_evaluators.csv",
    mime="text/csv"
)