import streamlit as st
import pandas as pd

# Load your data
df = pd.read_csv("Evaluator_Customer_Mileage.csv")  # Replace with your actual filename

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

# Ensure 'Round-Trip Miles' column exists and is numeric
if 'Round-Trip Miles' in filtered_df.columns:
    filtered_df['Round-Trip Miles'] = pd.to_numeric(filtered_df['Round-Trip Miles'], errors='coerce')

    # Identify closest evaluator per customer
    def highlight_grouped_rows(df_grouped):
        highlight = pd.DataFrame('', index=df_grouped.index, columns=df_grouped.columns)
        for customer, group in df_grouped.groupby('Customer'):
            if not group.empty:
                min_index = group['Round-Trip Miles'].idxmin()
                highlight.loc[min_index] = ['background-color: lightgreen'] * len(group.columns)
        return highlight

    styled_df = filtered_df.style.apply(highlight_grouped_rows, axis=None)
    st.subheader("Closest Evaluator per Customer")
    st.dataframe(styled_df)
else:
    st.error("Column 'Round-Trip Miles' not found in your data.")

# Download button
csv = filtered_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download Filtered Data as CSV",
    data=csv,
    file_name="filtered_evaluators.csv",
    mime="text/csv"
)