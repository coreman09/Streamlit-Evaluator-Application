import streamlit as st
import pandas as pd
import os
from rapidfuzz import process

st.set_page_config(page_title="Evaluator Assignment Tool", layout="wide")
st.title("Evaluator Assignment by Closest Distance")

# Upload job file
uploaded_job_file = st.file_uploader("Upload a Job File (.xlsx)", type=["xlsx"])
if uploaded_job_file is None:
    st.warning("Please upload a job file to continue.")
    st.stop()

# Load static files
required_files = ["Evaluator_Customer_Mileage.csv", "Evaluators_FullTime.csv"]
missing = [f for f in required_files if not os.path.exists(f)]
if missing:
    st.error(f"Missing required file(s): {', '.join(missing)}. Please upload them to proceed.")
    st.stop()

# Load mileage data
mileage_df = pd.read_csv("Evaluator_Customer_Mileage.csv")
mileage_df.columns = mileage_df.columns.str.strip()
mileage_df.rename(columns={"Cost ($)": "cost ($)"}, inplace=True)

# Load full-time evaluator list
full_time_df = pd.read_csv("Evaluators_FullTime.csv")
full_time_names = full_time_df['Last Name'].str.strip().unique()

# Tag evaluator status
mileage_df['Status'] = mileage_df['Evaluator'].apply(
    lambda name: 'Full-Time' if name.strip() in full_time_names else 'Contract'
)

# Ensure numeric columns
mileage_df['Round-Trip Miles'] = pd.to_numeric(mileage_df['Round-Trip Miles'], errors='coerce')
mileage_df['2026 Cost'] = pd.to_numeric(mileage_df['2026 Cost'], errors='coerce')

# Add Per Diem (contractors only)
mileage_df['Per Diem'] = mileage_df.apply(
    lambda row: 225 if row['Round-Trip Miles'] > 175 and row['Status'] == 'Contract' else 0,
    axis=1
)

# Add Mileage Bonus (contractors only)
def mileage_bonus(row):
    if row['Status'] != 'Contract' or pd.isnull(row['Round-Trip Miles']):
        return 0
    elif row['Round-Trip Miles'] > 800:
        return 500
    elif row['Round-Trip Miles'] > 400:
        return 250
    else:
        return 0

mileage_df['Mileage Bonus'] = mileage_df.apply(mileage_bonus, axis=1)

# Add Total Cost
mileage_df['Total Cost'] = (
    mileage_df['2026 Cost'].fillna(0) +
    mileage_df['Per Diem'] +
    mileage_df['Mileage Bonus']
)

# Load uploaded job file
jobs_df = pd.read_excel(uploaded_job_file)
jobs_df['Customer Company'] = jobs_df['Customer Company'].astype(str).str.strip().str.lower()
mileage_df['Customer'] = mileage_df['Customer'].astype(str).str.strip().str.lower()

# Fuzzy match customer names
def fuzzy_match_customer(job_name, choices, threshold=85):
    match, score, _ = process.extractOne(job_name, choices)
    return match if score >= threshold else None

jobs_df['Matched Customer'] = jobs_df['Customer Company'].apply(
    lambda x: fuzzy_match_customer(x, mileage_df['Customer'].unique())
)

# Infer number of evaluators needed
jobs_df['Evaluators Needed'] = jobs_df['Assignee(s)'].apply(
    lambda x: len(str(x).split(',')) if pd.notnull(x) else 1
)

# Merge using fuzzy-matched customer
merged_df = jobs_df.merge(mileage_df, left_on="Matched Customer", right_on="Customer", how="left")

# Select closest evaluators per job
def select_closest(group):
    n = group['Evaluators Needed'].iloc[0]
    return group.nsmallest(n, 'Round-Trip Miles')

ranked_df = merged_df.groupby('Job number').apply(select_closest).reset_index(drop=True)

# Format output
ranked_df['Round-Trip Miles'] = ranked_df['Round-Trip Miles'].round(2)
ranked_df['Total Cost'] = ranked_df['Total Cost'].round(2)

# Final columns
output_cols = [
    'Job number', 'Customer Company', 'Evaluator',
    'Round-Trip Miles', 'cost ($)', 'Per Diem', 'Mileage Bonus',
    'Total Cost', 'Status'
]

final_df = ranked_df[output_cols].sort_values(by=['Job number', 'Round-Trip Miles'])

# Display results
st.subheader("Closest Evaluators Assigned to Each Job")
st.dataframe(final_df, use_container_width=True)

# Download button
csv = final_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Assignment Table as CSV",
    data=csv,
    file_name="evaluator_assignments.csv",
    mime="text/csv"

)


