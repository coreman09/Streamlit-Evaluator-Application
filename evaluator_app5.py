import pandas as pd

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
    mileage_df['cost ($)'].fillna(0) +
    mileage_df['Per Diem'] +
    mileage_df['Mileage Bonus']
)

# Load job data from updated file
jobs_df = pd.read_excel("Jobs_1526.xlsx")
jobs_df['Customer Company'] = jobs_df['Customer Company'].str.strip()

# Infer number of evaluators needed
jobs_df['Evaluators Needed'] = jobs_df['Assignee(s)'].apply(
    lambda x: len(str(x).split(',')) if pd.notnull(x) else 1
)

# Match jobs to mileage data
merged_df = jobs_df.merge(mileage_df, left_on="Customer Company", right_on="Customer", how="left")

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

# Display or export
print(final_df)
# final_df.to_csv("job_assignments.csv", index=False)