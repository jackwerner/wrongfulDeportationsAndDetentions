import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import re

# Set page configuration
st.set_page_config(
    page_title="Wrongful Deportation & Detention Dashboard",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Title and description
st.title("⚖️ Wrongful Deportation & Detention Dashboard")
st.markdown("This dashboard displays court cases involving wrongful deportation or detention from CourtListener data.")

# Add explanation about CourtListener and query used
with st.expander("About the Data Source", expanded=False):
    st.markdown("""
    **What is CourtListener?**
    
    CourtListener is a free legal research platform that provides access to millions of court opinions, oral arguments, and other legal documents. It's maintained by the non-profit Free Law Project and aggregates data from federal and state courts across the United States.
    
    **Search Query Used:**
    
    The data in this dashboard was extracted using the following search query:
    ```
    ("alien enemy act" OR "el salvador" OR "cecot" OR "terrorism confinement center") AND 
    (wrongful OR wrongfully OR unlawful OR unlawfully) AND 
    (deportation OR deported OR detention OR detained OR removal OR removed OR "habeas corpus" OR 
    "due process" OR "ICE" OR "Immigration and Customs Enforcement" OR "Department of Homeland Security" OR 
    "DHS" OR "Trump" OR "Noem" OR "DOJ" OR "Trump Administration")
    ```
    
    This query focuses on cases involving potential wrongful deportation or detention, particularly those related to specific policies or legal frameworks. The query includes all cases filed after March 15th, 2025 which is the date that the Trump administration invoked the Alien Enemies Act.
    
    If a case is not shown in the dashboard, there is likely not a case filed no one has yet brought a federal lawsuit in their name and hasn't been spun off into its own complaint or appeal. Most of the challenges to the March 2025 deportation flights have been handled as a class action (e.g. J.G.G. v. Trump), with detainees identified by initials or put into an aggregated "class" rather than named individually. Unless the victim (or a legal aid organization on their behalf) files a distinct complaint or intervenes in the pending lawsuits, you won't see their name on the public dockets.
    """)

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv("courtlistener_cases.csv")
    # Convert string to boolean for filtering
    for col in ['wrongful_deportation', 'wrongful_detention']:
        df[col] = df[col].map({'yes': True, 'no': False, 'unknown': None})
    # Convert date string to datetime
    df['date_filed'] = pd.to_datetime(df['date_filed'])
    return df

df = load_data()

# Function to identify related cases
def group_related_cases(cases_df):
    # Extract names from case titles
    cases_df['case_parties'] = cases_df['case_name'].apply(lambda x: set(re.split(r'\sv\.\s|\sv\s', x)))
    
    # Create a dictionary to store case groups
    case_groups = {}
    group_id = 0
    assigned_cases = set()
    
    # Group by person_name (when available and not unknown)
    for idx, row in cases_df.iterrows():
        if idx in assigned_cases:
            continue
            
        if pd.notna(row['person_name']) and row['person_name'].lower() != 'unknown':
            # Find all cases with the same person
            same_person = cases_df[cases_df['person_name'] == row['person_name']].index.tolist()
            if len(same_person) > 1:
                case_groups[group_id] = same_person
                assigned_cases.update(same_person)
                group_id += 1
    
    # Group by case parties for remaining cases
    for idx, row in cases_df.iterrows():
        if idx in assigned_cases:
            continue
            
        related_cases = [idx]
        for idx2, row2 in cases_df.iterrows():
            if idx != idx2 and idx2 not in assigned_cases:
                # Check if case names share parties
                if row['case_parties'] & row2['case_parties']:  # Set intersection
                    related_cases.append(idx2)
        
        if len(related_cases) > 1:
            case_groups[group_id] = related_cases
            assigned_cases.update(related_cases)
            group_id += 1
    
    # Create a new dataframe with group information
    result_df = cases_df.copy()
    result_df['case_group'] = None
    
    for group_id, case_indices in case_groups.items():
        result_df.loc[case_indices, 'case_group'] = group_id
    
    # Cases not in any group get their own group ID
    ungrouped_cases = result_df[result_df['case_group'].isna()].index
    for i, idx in enumerate(ungrouped_cases):
        result_df.loc[idx, 'case_group'] = group_id + i
    
    return result_df

# Filter for wrongful deportation or detention cases
wrongful_cases = df[(df['wrongful_deportation'] == True) | (df['wrongful_detention'] == True)]

# Group related cases
grouped_cases = group_related_cases(wrongful_cases)

# Sidebar filters
st.sidebar.header("Filters")

# Court filter
all_courts = sorted(df['court'].unique())
selected_courts = st.sidebar.multiselect("Select Courts", all_courts, default=[])

# Date range filter
min_date = df['date_filed'].min().date()
max_date = df['date_filed'].max().date()
date_range = st.sidebar.date_input(
    "Date Range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

# Citizenship status filter
citizenship_options = ['All', 'US Citizen', 'Non-US Citizen', 'Unknown']
citizenship_filter = st.sidebar.selectbox("Citizenship Status", citizenship_options)

# Apply filters to get base filtered cases
filtered_base = wrongful_cases.copy()

if selected_courts:
    filtered_base = filtered_base[filtered_base['court'].isin(selected_courts)]

if len(date_range) == 2:
    start_date, end_date = date_range
    filtered_base = filtered_base[(filtered_base['date_filed'].dt.date >= start_date) & 
                                (filtered_base['date_filed'].dt.date <= end_date)]

if citizenship_filter != 'All':
    if citizenship_filter == 'US Citizen':
        filtered_base = filtered_base[filtered_base['is_us_citizen'] == 'yes']
    elif citizenship_filter == 'Non-US Citizen':
        filtered_base = filtered_base[filtered_base['is_us_citizen'] == 'no']
    elif citizenship_filter == 'Unknown':
        filtered_base = filtered_base[filtered_base['is_us_citizen'] == 'unknown']

# Get the filtered and grouped cases
filtered_cases = group_related_cases(filtered_base)

# Dashboard metrics
st.header("Case Statistics")
st.caption("Note: Statistics grouped by person")
metric_cols = st.columns(3)

with metric_cols[0]:
    st.metric("Total Wrongful Cases", len(grouped_cases['case_group'].unique()))

with metric_cols[1]:
    deportation_groups = grouped_cases[grouped_cases['wrongful_deportation'] == True]['case_group'].unique()
    st.metric("Wrongful Deportation", len(deportation_groups))

with metric_cols[2]:
    detention_groups = grouped_cases[grouped_cases['wrongful_detention'] == True]['case_group'].unique()
    st.metric("Wrongful Detention", len(detention_groups))

# Case details by case group
st.subheader("Case Details")

if filtered_cases.empty:
    st.warning("No cases match the selected filters.")
else:
    # Group cases by case_group
    unique_groups = filtered_cases['case_group'].unique()
    
    for group in unique_groups:
        group_cases = filtered_cases[filtered_cases['case_group'] == group].sort_values('date_filed', ascending=False)
        
        if len(group_cases) == 1:
            # Single case
            case = group_cases.iloc[0]
            with st.expander(f"{case['case_name']} - {case['docket_number']} ({case['court']})"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Date Filed:** {case['date_filed'].date()}")
                    st.markdown(f"**Person Name:** {case['person_name']}")
                    st.markdown(f"**Case Title:** {case['case_title']}")
                    st.markdown("**Case Summary:**")
                    st.markdown(case['case_summary'])
                    
                with col2:
                    st.markdown("**Case Details:**")
                    st.markdown(f"- Wrongful Deportation: {'Yes' if case['wrongful_deportation'] else 'No'}")
                    st.markdown(f"- Wrongful Detention: {'Yes' if case['wrongful_detention'] else 'No'}")
                    st.markdown(f"- US Citizen: {case['is_us_citizen'].capitalize() if not pd.isna(case['is_us_citizen']) else 'Unknown'}")
                    
                    if pd.notna(case['url']):
                        st.markdown(f"[View Full Case](https://courtlistener.com{case['url']})")
        else:
            # Multiple related cases
            # Use the most recent case name as the group title or the one with the person's name
            named_cases = group_cases[pd.notna(group_cases['person_name']) & (group_cases['person_name'].str.lower() != 'unknown')]
            if not named_cases.empty:
                primary_case = named_cases.iloc[0]
                person_name = primary_case['person_name']
            else:
                primary_case = group_cases.iloc[0]
                person_name = "Unknown"
            
            with st.expander(f"Case Group: {person_name} - {len(group_cases)} related cases"):
                st.markdown(f"**Person Involved:** {person_name}")
                
                # Show citizenship if consistent across cases
                citizenship_values = group_cases['is_us_citizen'].unique()
                if len(citizenship_values) == 1 and pd.notna(citizenship_values[0]):
                    st.markdown(f"**US Citizen:** {citizenship_values[0].capitalize()}")
                
                # Case timeline
                st.markdown("### Case Timeline")
                for i, (_, case) in enumerate(group_cases.iterrows()):
                    st.markdown(f"**{case['date_filed'].date()} - {case['case_name']} ({case['court']})**")
                    st.markdown(f"Docket: {case['docket_number']}")
                    
                    # Show full summary for the latest case (first in the list), truncate others
                    if i == 0:
                        st.markdown(f"Summary: {case['case_summary']}")
                    else:
                        summary = case['case_summary']
                        truncated_summary = summary[:150] + "..." if len(summary) > 150 else summary
                        st.markdown(f"Summary: {truncated_summary}")
                    
                    if pd.notna(case['url']):
                        st.markdown(f"[View Full Case](https://courtlistener.com{case['url']})")
                    st.markdown("---")

# Visualizations
st.header("Visualizations")
st.caption("Note: Visualizations show individual cases, not grouped by person")
viz_cols = st.columns(2)

with viz_cols[0]:
    # Count by court
    if not filtered_cases.empty:
        st.subheader("Cases by Court")
        court_counts = filtered_cases['court'].value_counts().reset_index()
        court_counts.columns = ['Court', 'Count']
        
        fig, ax = plt.subplots(figsize=(10, 6))
        sns.barplot(data=court_counts, x='Count', y='Court', ax=ax)
        ax.set_xlim(right=max(court_counts['Count']) * 1.1)  # Add consistent padding
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("No data available with current filters")

with viz_cols[1]:
    # Timeline of cases
    if not filtered_cases.empty:
        st.subheader("Timeline of Cases")
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Group by month for the timeline
        filtered_cases['month'] = filtered_cases['date_filed'].dt.to_period('M')
        timeline_data = filtered_cases.groupby('month').size().reset_index(name='count')
        timeline_data['month_date'] = timeline_data['month'].dt.to_timestamp()
        
        ax.plot(timeline_data['month_date'], timeline_data['count'], marker='o')
        ax.set_xlabel('Date')
        ax.set_ylabel('Number of Cases')
        plt.xticks(rotation=45)
        ax.set_ylim(bottom=0, top=max(timeline_data['count']) * 1.1)  # Add consistent padding
        plt.tight_layout()
        st.pyplot(fig)
    else:
        st.info("No data available with current filters")

# Footer
st.divider()
st.caption("Data source: CourtListener database")
st.caption("As long as the courts keep fighting, this dashboard will keep running.")
