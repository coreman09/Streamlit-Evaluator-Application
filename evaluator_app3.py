import streamlit as st
import pandas as pd

# Load and clean data
df = pd.read_csv("Evaluator_Customer_Mileage.csv")
df.columns = df.columns.str.strip().str.lower()  # Normalize column names

# Sidebar filters
st.sidebar.header("Filter Options")
selected_customers = st.sidebar.multiselect(
    "Select Customers",
    options=sorted(df['customer'].unique()),
    default=[]
)

selected_evaluators = st.sidebar.multiselect(
    "Select Evaluators",
    options=sorted(df['evaluator'].unique()),
    default=[]
)

# Apply filters
filtered_df = df.copy()
if selected_customers:
    filtered_df = filtered_df[filtered_df['customer'].isin(selected_customers)]
if selected_evaluators:
    filtered_df = filtered_df[filtered_df['evaluator'].isin(selected_evaluators)]

# Ensure numeric columns
filtered_df['round-trip miles'] = pd.to_numeric(filtered_df.get('round-trip miles'), errors='coerce')
filtered_df['cost ($)'] = pd.to_numeric(filtered_df.get('cost ($)'), errors='coerce')

# Add Per Diem
filtered_df['per diem'] = filtered_df['round-trip miles'].apply(
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

filtered_df['mileage bonus'] = filtered_df['round-trip miles'].apply(mileage_bonus)

# Add Total Cost
filtered_df['total cost'] = (
    filtered_df['cost ($)'].fillna(0) +
    filtered_df['per diem'] +
    filtered_df['mileage bonus']
)

# Drop original cost column if not needed
filtered_df.drop(columns=['cost ($)'], inplace=True)

# Highlight closest evaluator per customer
def highlight_grouped_rows(df_grouped):
    highlight = pd.DataFrame('', index=df_grouped.index, columns=df_grouped.columns)
    for customer, group in df_grouped.groupby('customer'):
        if not group.empty and 'round-trip miles' in group.columns:
            min_index = group['round-trip miles'].idxmin()
            highlight.loc[min_index] = ['background-color: lightgreen'] * len(group.columns)
    return highlight

# Format numeric columns
format_dict = {col: '{:.2f}' for col in filtered_df.select_dtypes(include='number').columns}
for col in ['per diem', 'mileage bonus', 'total cost']:
    if col in format_dict:
        format_dict[col] = '${:,.2f}'

# Apply styling
styled_df = filtered_df.style\
    .apply(highlight_grouped_rows, axis=None)\
    .format(format_dict)

# Display results
st.subheader("Closest Evaluator per Customer")
st.dataframe(styled_df)

# Download button
csv = filtered_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Filtered Data as CSV",
    data=csv,
    file_name="filtered_evaluators.csv",
    mime="text/csv"
)