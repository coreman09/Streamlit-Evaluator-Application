import streamlit as st
import pandas as pd

# Load main data
df = pd.read_csv("Evaluator_Customer_Mileage.csv")
df.columns = df.columns.str.strip()

# Normalize cost column
if "Cost ($)" in df.columns:
    df.rename(columns={"Cost ($)": "cost ($)"}, inplace=True)

# Drop one-way miles if present
if "One-Way Miles" in df.columns:
    df.drop(columns=["One-Way Miles"], inplace=True)

# Load full-time evaluator list
full_time_df = pd.read_csv("Evaluators_FullTime.csv")
full_time_names = full_time_df['Last Name'].str.strip().unique()

# Tag evaluator status
df['Status'] = df['Evaluator'].apply(
    lambda name: 'Full-Time' if name.strip() in full_time_names else 'Contract'
)

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

# Add Per Diem (only for contractors)
filtered_df['Per Diem'] = filtered_df.apply(
    lambda row: 225 if row['Round-Trip Miles'] > 175 and row['Status'] != 'Full-Time' else 0,
    axis=1
)

# Add Mileage Bonus (only for contractors)
def mileage_bonus(row):
    if row['Status'] == 'Full-Time' or pd.isnull(row['Round-Trip Miles']):
        return 0
    elif row['Round-Trip Miles'] > 800:
        return 500
    elif row['Round-Trip Miles'] > 400:
        return 250
    else:
        return 0

filtered_df['Mileage Bonus'] = filtered_df.apply(mileage_bonus, axis=1)

# Add Total Cost
filtered_df['Total Cost'] = (
    filtered_df['cost ($)'].fillna(0) +
    filtered_df['Per Diem'] +
    filtered_df['Mileage Bonus']
)

# Highlight closest evaluator per customer
def highlight_grouped_rows(df_grouped):
    highlight = pd.DataFrame('', index=df_grouped.index, columns=df_grouped.columns)
    for customer, group in df_grouped.groupby('Customer'):
        if not group.empty and 'Round-Trip Miles' in group.columns:
            min_index = group['Round-Trip Miles'].idxmin()
            highlight.loc[min_index] = ['background-color: lightgreen'] * len(group.columns)
    return highlight

# Format currency columns
for col in ['cost ($)', 'Per Diem', 'Mileage Bonus', 'Total Cost']:
    if col in filtered_df.columns:
        filtered_df[col] = filtered_df[col].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")

# Remove index before styling
filtered_df = filtered_df.reset_index(drop=True)

# Apply styling
styled_df = filtered_df.style\
    .apply(highlight_grouped_rows, axis=None)

# Display results
st.subheader("Closest Evaluator per Customer")
st.dataframe(styled_df, use_container_width=True)

# Download button
csv = filtered_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Filtered Data as CSV",
    data=csv,
    file_name="filtered_evaluators.csv",
    mime="text/csv"
)