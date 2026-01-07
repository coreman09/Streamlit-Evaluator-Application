import streamlit as st
import pandas as pd
import os
from difflib import get_close_matches   # built-in fuzzy matching
from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpBinary

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

# Load full-time evaluator list
full_time_df = pd.read_csv("Evaluators_FullTime.csv")
full_time_names = full_time_df['Last Name'].str.strip().unique()

# Tag evaluator status
mileage_df['Status'] = mileage_df['Evaluator'].apply(
    lambda name: 'Full-Time' if name.strip() in full_time_names else 'Contract'
)

# Ensure numeric miles
mileage_df['Round-Trip Miles'] = pd.to_numeric(mileage_df['Round-Trip Miles'], errors='coerce')

# --- Overwrite cost column with mileage × 0.725 ---
mileage_df['2026 Cost'] = mileage_df['Round-Trip Miles'] * 0.725

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

# Keep Total Cost as is (base cost + per diem + bonus)
mileage_df['Total Cost'] = (
    mileage_df['2026 Cost'].fillna(0) +
    mileage_df['Per Diem'] +
    mileage_df['Mileage Bonus']
)

# --- NEW: Let user choose available evaluators ---
all_evaluators = sorted(mileage_df['Evaluator'].unique())
available_evaluators = st.multiselect(
    "Select available evaluators",
    options=all_evaluators,
    default=all_evaluators
)
mileage_df = mileage_df[mileage_df['Evaluator'].isin(available_evaluators)]

# Load uploaded job file
jobs_df = pd.read_excel(uploaded_job_file)
jobs_df['Customer Company'] = jobs_df['Customer Company'].astype(str).str.strip().str.lower()
mileage_df['Customer'] = mileage_df['Customer'].astype(str).str.strip().str.lower()

# Fuzzy match customer names (using difflib)
def fuzzy_match_customer(job_name, choices, threshold=0.85):
    matches = get_close_matches(job_name, choices, n=1, cutoff=threshold)
    return matches[0] if matches else None

jobs_df['Matched Customer'] = jobs_df['Customer Company'].apply(
    lambda x: fuzzy_match_customer(x, mileage_df['Customer'].unique())
)

# Infer number of evaluators needed
jobs_df['Evaluators Needed'] = jobs_df['Assignee(s)'].apply(
    lambda x: len(str(x).split(',')) if pd.notnull(x) else 1
)

# Create job slots
job_slots = []
for _, row in jobs_df.iterrows():
    job_slots += [(row['Job number'], row['Matched Customer'])] * row['Evaluators Needed']

# Define last-resort managers and penalty
last_resort_managers = ["Sherman", "Gray", "MacDonald"]
manager_penalty = 10000

# Build cost matrix with penalty
cost_matrix = {}
for evaluator in mileage_df['Evaluator'].unique():
    for job_num, customer in job_slots:
        match = mileage_df[(mileage_df['Evaluator'] == evaluator) & (mileage_df['Customer'] == customer)]
        if not match.empty:
            base_cost = match['Total Cost'].values[0]
            adjusted_cost = base_cost + (manager_penalty if evaluator in last_resort_managers else 0)
            cost_matrix[(evaluator, job_num)] = adjusted_cost

# Define optimization problem
prob = LpProblem("EvaluatorAssignment", LpMinimize)
x = LpVariable.dicts("assign", cost_matrix.keys(), cat=LpBinary)

# Objective: minimize total cost
prob += lpSum([cost_matrix[key] * x[key] for key in cost_matrix])

# Constraint: each job slot filled once
for job_num in set(j[0] for j in job_slots):
    prob += lpSum([x[(evaluator, job_num)] for evaluator in mileage_df['Evaluator'].unique() if (evaluator, job_num) in x]) == job_slots.count((job_num, jobs_df[jobs_df['Job number'] == job_num]['Matched Customer'].iloc[0]))

# Evaluators cannot be reused (one-time use)
for evaluator in mileage_df['Evaluator'].unique():
    prob += lpSum([x[(evaluator, job_num)] for job_num, customer in job_slots if (evaluator, job_num) in x]) <= 1

# Solve
prob.solve()

# --- Manual Selection Mode (chart shows top 5, dropdown allows all, default closest, one-time use enforced) ---
st.subheader("Manual Selection: Chart Top 5, Choose Any Evaluator (One-Time Use)")
selected_assignments = {}
used_evaluators = set()

def get_top_evaluators(job_customer, mileage_df, top_n=5):
    matches = mileage_df[mileage_df['Customer'] == job_customer]
    return matches.nsmallest(top_n, 'Total Cost')[['Evaluator','Round-Trip Miles','2026 Cost','Total Cost']]

for _, job_row in jobs_df.iterrows():
    job_num = job_row['Job number']
    customer = job_row['Matched Customer']
    if pd.isnull(customer):
        continue
    
    # Show top 5 evaluators in chart
    top_eval_df = get_top_evaluators(customer, mileage_df)
    st.write(f"### Job {job_num} - {job_row['Customer Company'].title()}")
    st.dataframe(top_eval_df)
    
    # Dropdown allows ALL evaluators for this customer
    all_matches = mileage_df[mileage_df['Customer'] == customer]
    available_evals = all_matches['Evaluator'].tolist()
    
    # Filter out already-used evaluators
    selectable_evals = [e for e in available_evals if e not in used_evaluators]
    if not selectable_evals:
        # fallback: still show all, but mark reused ones
        selectable_evals = available_evals
    
    # Default to closest among selectable
    closest_eval = all_matches[all_matches['Evaluator'].isin(selectable_evals)].nsmallest(1, 'Total Cost')['Evaluator'].iloc[0]
    default_index = selectable_evals.index(closest_eval) if closest_eval in selectable_evals else 0
    
    chosen_eval = st.selectbox(
        f"Select evaluator for Job {job_num}",
        options=selectable_evals,
        index=default_index,
        key=f"job_{job_num}"
    )
    
    selected_assignments[job_num] = chosen_eval
    used_evaluators.add(chosen_eval)

# Build output from manual selections
assignments = []
for job_num, evaluator in selected_assignments.items():
    job_row = jobs_df[jobs_df['Job number'] == job_num].iloc[0]
    cost_row = mileage_df[(mileage_df['Evaluator'] == evaluator) & (mileage_df['Customer'] == job_row['Matched Customer'])].iloc[0]
    assignment_tier = "Last Resort Manager" if evaluator in last_resort_managers else "Primary"
    assignments.append({
        'Job number': job_num,
        'Customer Company': job_row['Customer Company'].title(),
        'Evaluator': evaluator,
        'Round-Trip Miles': round(cost_row['Round-Trip Miles'], 2),
        '2026 Cost': round(cost_row['2026 Cost'], 2),
        'Per Diem': cost_row['Per Diem'],
        'Mileage Bonus': cost_row['Mileage Bonus'],
        'Total Cost': round(cost_row['Total Cost'], 2),
        'Status': cost_row['Status'],
        'Assignment Tier': assignment_tier
    })

final_df = pd.DataFrame(assignments).sort_values(by=['Job number'])

# Display detailed results
st.subheader("Final Assignments (Detailed)")
st.dataframe(final_df, use_container_width=True)

# Grand total
grand_total = final_df['Total Cost'].sum()
st.markdown(f"### Grand Total Cost: ${grand_total:,.2f}")


