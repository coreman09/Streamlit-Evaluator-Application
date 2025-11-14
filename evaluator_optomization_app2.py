import streamlit as st
import pandas as pd
import os
import re
from rapidfuzz import process
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpBinary, LpStatus
from collections import Counter

st.set_page_config(page_title="Evaluator Optimizer", layout="wide")
st.title("Optimized Evaluator Assignment")

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
mileage_df['cost ($)'] = pd.to_numeric(mileage_df['cost ($)'], errors='coerce')

# Add Per Diem and Mileage Bonus
mileage_df['Per Diem'] = mileage_df.apply(
    lambda row: 225 if row['Round-Trip Miles'] > 175 and row['Status'] == 'Contract' else 0,
    axis=1
)
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
mileage_df['Total Cost'] = mileage_df['cost ($)'].fillna(0) + mileage_df['Per Diem'] + mileage_df['Mileage Bonus']

# Load job file
jobs_df = pd.read_excel(uploaded_job_file)

# Case-insensitive cleaning
def clean_customer_name(name):
    name = re.sub(r'^\d+\s*[-–]?\s*', '', str(name))
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'[^a-zA-Z0-9\s]', '', name)
    return name.lower().strip()

jobs_df['Cleaned Customer'] = jobs_df['Customer Company'].apply(clean_customer_name)
mileage_df['Cleaned Customer'] = mileage_df['Customer'].apply(clean_customer_name)

# Manual override map
manual_map = {
    "precision pipeline solutions": "precision pipeline solutions",
    "j mullen sons inc": "j mullen & sons"
}

# Fuzzy match with override
def fuzzy_match_customer(job_name, choices, threshold=90):
    cleaned = job_name.lower().strip()
    if cleaned in manual_map:
        return manual_map[cleaned]
    match, score, _ = process.extractOne(cleaned, choices)
    return match if score >= threshold else None

jobs_df['Matched Customer'] = jobs_df['Cleaned Customer'].apply(
    lambda x: fuzzy_match_customer(x, mileage_df['Cleaned Customer'].unique())
)

# Priority sorting
priority_customers = ["national fuel"]
jobs_df['Priority'] = jobs_df['Matched Customer'].apply(lambda x: 1 if x in priority_customers else 0)
jobs_df = jobs_df.sort_values(by='Priority', ascending=False)

# Log matched customers
st.subheader("📋 Matched Customers")
st.dataframe(jobs_df[['Job number', 'Customer Company', 'Matched Customer']])

# Evaluators needed
jobs_df['Evaluators Needed'] = jobs_df['Assignee(s)'].apply(
    lambda x: len(str(x).split(',')) if pd.notnull(x) else 1
)

# Create job slots
job_slots = []
for _, row in jobs_df.iterrows():
    if pd.notnull(row['Matched Customer']):
        job_slots += [(row['Job number'], row['Matched Customer'].lower().strip())] * row['Evaluators Needed']

# Log job slot count
expected_slots = jobs_df['Evaluators Needed'].sum()
actual_slots = len(job_slots)
st.write(f"🧮 Expected job slots: {expected_slots}, Actual job slots: {actual_slots}")

# Build cost matrix
cost_matrix = {}
unmatched_pairs = []
for evaluator in mileage_df['Evaluator'].unique():
    for job_num, customer in job_slots:
        customer = customer.lower().strip()
        match = mileage_df[
            (mileage_df['Evaluator'] == evaluator) &
            (mileage_df['Cleaned Customer'].str.lower().str.strip() == customer)
        ]
        if not match.empty:
            best_row = match.sort_values(by='Total Cost', ascending=False).iloc[0]
            cost_matrix[(evaluator, job_num)] = best_row['Total Cost']
        else:
            unmatched_pairs.append((evaluator, job_num, customer))

if unmatched_pairs:
    st.warning(f"⚠️ Unmatched evaluator–customer pairs (sample): {unmatched_pairs[:10]}")

# Log missing jobs
covered_jobs = set([job_num for (_, job_num) in cost_matrix.keys()])
all_jobs = set([job_num for job_num, _ in job_slots])
missing_jobs = sorted(all_jobs - covered_jobs)
if missing_jobs:
    st.warning(f"⚠️ Jobs missing from cost matrix: {missing_jobs}")

# Optimization
prob = LpProblem("EvaluatorAssignment", LpMinimize)
x = LpVariable.dicts("assign", cost_matrix.keys(), cat=LpBinary)
prob += lpSum([cost_matrix[key] * x[key] for key in cost_matrix])

# Multi-evaluator constraint
slot_counts = Counter([job_num for job_num, _ in job_slots])
for job_num, count in slot_counts.items():
    prob += lpSum([x[(evaluator, job_num)] for evaluator in mileage_df['Evaluator'].unique() if (evaluator, job_num) in x]) == count

# Strict one-time use
for evaluator in mileage_df['Evaluator'].unique():
    prob += lpSum([x[(evaluator, job_num)] for job_num, _ in job_slots if (evaluator, job_num) in x]) <= 1

# Solve
prob.solve()
st.write(f"🧠 Solver status: {LpStatus[prob.status]}")

# Assignment tier logic
last_resort_managers = ["Sherman", "Gray", "Macdonald"]

# Build output
assignments = []
for (evaluator, job_num), var in x.items():
    if var.value() == 1:
        job_row = jobs_df[jobs_df['Job number'] == job_num].iloc[0]
        cost_row = mileage_df[
            (mileage_df['Evaluator'] == evaluator) &
            (mileage_df['Cleaned Customer'].str.lower().str.strip() == job_row['Matched Customer'].lower().strip())
        ].sort_values(by='Total Cost', ascending=False).iloc[0]
        assignment_tier = "Last Resort Manager" if evaluator in last_resort_managers else "Primary"
        assignments.append({
            'Job number': job_num,
            'Customer Company': job_row['Customer Company'],
            'Evaluator': evaluator,
            'Round-Trip Miles': round(cost_row['Round-Trip Miles'], 2),
            'cost ($)': round(cost_row['cost ($)'], 2),
            'Per Diem': cost_row['Per Diem'],
            'Mileage Bonus': cost_row['Mileage Bonus'],
            'Total Cost': round(cost_row['Total Cost'], 2),
            'Status': cost_row['Status'],
            'Assignment Tier': assignment_tier
        })

final_df = pd.DataFrame(assignments).sort_values(by=['Job number', 'Round-Trip Miles'])
st.subheader("Optimized Evaluator Assignments")
st.dataframe(final_df, use_container_width=True)

csv = final_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Assignment Table as CSV",
    data=csv,
    file_name="optimized_evaluator_assignments.csv",
    mime="text/csv"
)