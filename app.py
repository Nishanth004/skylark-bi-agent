import streamlit as st
import pandas as pd
import requests
import openai
import json

# --- APP CONFIG ---
st.set_page_config(page_title="Skylark AI Agent", layout="wide")

st.title("🚁 Skylark Drones BI Agent")
st.markdown("""
This agent integrates directly with **Monday.com Boards** via GraphQL API.
It processes Work Orders and Deals to provide executive insights.
""")

# --- SIDEBAR: AUTHENTICATION ---
with st.sidebar:
    st.header("🔌 Connection Setup")
    st.info("Enter your credentials to connect to the live boards.")
    MONDAY_API_KEY = st.text_input("Monday.com API Key", type="password")
    OPENAI_API_KEY = st.text_input("OpenAI API Key", type="password")
    WO_BOARD_ID = st.text_input("Work Orders Board ID")
    DEALS_BOARD_ID = st.text_input("Deals Board ID")
    
    load_btn = st.button("🔗 Connect & Fetch Data")

# --- FUNCTION: QUERY MONDAY.COM API ---
def get_monday_data(board_id, api_key):
    # This is the specific requirement: querying via API, not CSV
    url = "https://api.monday.com/v2"
    headers = {"Authorization": api_key, "API-Version": "2023-10"}
    
    # GraphQL query to fetch all items and their column values
    query = f"""
    query {{
      boards (ids: {board_id}) {{
        items_page (limit: 500) {{
          items {{
            name
            column_values {{
              column {{ title }}
              text
            }}
          }}
        }}
      }}
    }}
    """
    
    response = requests.post(url, json={'query': query}, headers=headers)
    
    if response.status_code != 200:
        st.error(f"API Error: {response.text}")
        return pd.DataFrame()
        
    data = response.json()
    
    # Check for GraphQL errors
    if 'errors' in data:
        st.error(f"GraphQL Error: {data['errors'][0]['message']}")
        return pd.DataFrame()
        
    try:
        items = data['data']['boards'][0]['items_page']['items']
    except (TypeError, KeyError):
        st.warning(f"No data found for Board ID: {board_id}")
        return pd.DataFrame()

    # Parse JSON response into a clean DataFrame
    rows = []
    for item in items:
        row = {'Name': item['name']}
        for col in item['column_values']:
            if col['column']['title']: # Skip columns with no title
                row[col['column']['title']] = col['text']
        rows.append(row)
        
    return pd.DataFrame(rows)

# --- FUNCTION: CLEAN MESSY DATA ---
def clean_data(df):
    if df.empty: return df
    
    # 1. Handle Currency/Numbers (e.g. "1,200.00" -> 1200.00)
    for col in df.columns:
        if any(x in col.lower() for x in ['amount', 'price', 'value', 'budget']):
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('$', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # 2. Handle Dates
    for col in df.columns:
        if 'date' in col.lower():
            df[col] = pd.to_datetime(df[col], errors='coerce')
            
    return df

# --- FUNCTION: ASK OPENAI ---
def ask_gpt(query, df1, df2, api_key):
    openai.api_key = api_key
    
    # Create a summary context (sending full CSVs might hit token limits)
    context = f"""
    dataset_1_work_orders_sample:\n{df1.head(5).to_csv()}\n
    dataset_1_columns: {list(df1.columns)}\n
    dataset_1_stats: {df1.describe().to_string()}\n
    
    dataset_2_deals_sample:\n{df2.head(5).to_csv()}\n
    dataset_2_columns: {list(df2.columns)}\n
    dataset_2_stats: {df2.describe().to_string()}\n
    """
    
    system_prompt = """
    You are a BI Analyst for Skylark Drones. Answer questions based ONLY on the provided data context.
    - If data is missing or marked "Masked", mention that limitation.
    - For "Leadership Updates", summarize Revenue, Pipeline Health, and Risks.
    - Ignore Rows where "Deal Name" is empty.
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini", # Cost effective and fast
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context data: {context}\n\nUser Question: {query}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {e}"

# --- MAIN LOGIC ---
if 'wo_df' not in st.session_state:
    st.session_state.wo_df = None
if 'deal_df' not in st.session_state:
    st.session_state.deal_df = None

if load_btn:
    if not (MONDAY_API_KEY and WO_BOARD_ID and DEALS_BOARD_ID):
        st.error("Please provide all API Keys and Board IDs.")
    else:
        with st.spinner("Fetching data from Monday.com API..."):
            # Fetch
            raw_wo = get_monday_data(WO_BOARD_ID, MONDAY_API_KEY)
            raw_deal = get_monday_data(DEALS_BOARD_ID, MONDAY_API_KEY)
            
            # Clean
            st.session_state.wo_df = clean_data(raw_wo)
            st.session_state.deal_df = clean_data(raw_deal)
            
            if not st.session_state.wo_df.empty:
                st.success(f"Success! Loaded {len(st.session_state.wo_df)} Work Orders and {len(st.session_state.deal_df)} Deals.")

# --- UI: TABS ---
tab1, tab2 = st.tabs(["💬 Ask AI Agent", "📊 Raw Data Explorer"])

with tab1:
    if st.session_state.wo_df is not None:
        query = st.text_area("Ask a business question:", placeholder="e.g., 'What is the total revenue for the Mining sector?'")
        if st.button("Generate Answer"):
            if not OPENAI_API_KEY:
                st.error("Please enter OpenAI API Key in the sidebar.")
            else:
                with st.spinner("Analyzing..."):
                    answer = ask_gpt(query, st.session_state.wo_df, st.session_state.deal_df, OPENAI_API_KEY)
                    st.write(answer)
    else:
        st.info("Please connect to Monday.com in the sidebar first.")

with tab2:
    if st.session_state.wo_df is not None:
        st.subheader("Work Orders")
        st.dataframe(st.session_state.wo_df)
        st.subheader("Deals")
        st.dataframe(st.session_state.deal_df)
