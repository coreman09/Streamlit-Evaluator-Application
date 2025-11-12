import streamlit as st
import pandas as pd

# Load your data
df = pd.read_csv("Evaluator_Customer_Mileage.csv")  # Make sure this file is in your GitHub repo

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

# Ensure 'Round-Trip Miles' is numeric
if 'Round-Trip Miles' in filtered_df.columns:
    filtered_df['Round-Trip Miles'] = pd.to_numeric(filtered_df['Round-Trip Miles'], errors='coerce')

# Ensure 'cost ($)' is numeric if present
if 'cost ($)' in filtered_df.columns:
    filtered_df['cost ($)'] = pd.to_numeric(filtered_df['cost ($)'], errors='coerce')

# Highlight closest evaluator per customer
def highlight_grouped_rows(df_grouped):
    highlight = pd.DataFrame('', index=df_grouped.index, columns=df_grouped.columns)
    for customer, group in df_grouped.groupby('Customer'):
        if not group.empty and 'Round-Trip Miles' in group.columns:
            min_index = group['Round-Trip Miles'].idxmin()
            highlight.loc[min_index] = ['background-color: lightgreen'] * len(group.columns)
    return highlight

# Format all numeric columns to 2 decimals
format_dict = {col: '{:.2f}' for col in filtered_df.select_dtypes(include='number').columns}
if 'cost ($)' in format_dict:
    format_dict['cost ($)'] = '${:,.2f}'

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