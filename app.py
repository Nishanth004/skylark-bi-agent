import streamlit as st
import pandas as pd
import requests
import openai
from openai import OpenAI  # Updated for v1.0+ client

# --- APP CONFIG ---
st.set_page_config(page_title="Skylark AI Agent", layout="wide")

st.title("🚁 Skylark Drones BI Agent")
st.markdown("""
**Status:** Local Test Mode
This agent integrates directly with **Monday.com Boards** via GraphQL API.
""")

# --- SIDEBAR: AUTHENTICATION ---
with st.sidebar:
    st.header("🔌 Connection Setup")
    MONDAY_API_KEY = st.text_input("Monday.com API Key", type="password")
    OPENAI_API_KEY = st.text_input("OpenAI API Key", type="password")
    WO_BOARD_ID = st.text_input("Work Orders Board ID")
    DEALS_BOARD_ID = st.text_input("Deals Board ID")
    
    load_btn = st.button("🔗 Connect & Fetch Data")

# --- FUNCTION: QUERY MONDAY.COM API ---
def get_monday_data(board_id, api_key):
    url = "https://api.monday.com/v2"
    headers = {"Authorization": api_key, "API-Version": "2023-10"}
    
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
    
    try:
        response = requests.post(url, json={'query': query}, headers=headers)
        if response.status_code != 200:
            st.error(f"API Error: {response.text}")
            return pd.DataFrame()
            
        data = response.json()
        if 'errors' in data:
            st.error(f"GraphQL Error: {data['errors'][0]['message']}")
            return pd.DataFrame()
            
        items = data['data']['boards'][0]['items_page']['items']
        
        rows = []
        for item in items:
            row = {'Name': item['name']}
            for col in item['column_values']:
                if col['column']['title']:
                    row[col['column']['title']] = col['text']
            rows.append(row)
            
        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Connection failed: {e}")
        return pd.DataFrame()

# --- FUNCTION: CLEAN DATA ---
def clean_data(df):
    if df.empty: return df
    for col in df.columns:
        # Numeric cleaning
        if any(x in col.lower() for x in ['amount', 'price', 'value', 'budget']):
            df[col] = df[col].astype(str).str.replace(',', '').str.replace('$', '')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        # Date cleaning
        if 'date' in col.lower():
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

# --- FUNCTION: ASK OPENAI (UPDATED FOR v1.0+) ---
def ask_gpt(query, df1, df2, api_key):
    # Initialize the client with the key provided in sidebar
    client = OpenAI(api_key=api_key)
    
    context = f"""
    WORK_ORDERS_SAMPLE:\n{df1.head(5).to_csv()}\n
    WORK_ORDERS_STATS:\n{df1.describe().to_string()}\n
    DEALS_SAMPLE:\n{df2.head(5).to_csv()}\n
    DEALS_STATS:\n{df2.describe().to_string()}\n
    """
    
    system_prompt = """
    You are a BI Analyst for Skylark Drones. 
    Answer questions based ONLY on the provided data context.
    If asked for a Leadership Update, summarize:
    1. Revenue (Billed vs Collected)
    2. Pipeline Health (High probability deals)
    3. Risks (Stuck projects)
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Data Context:\n{context}\n\nQuestion: {query}"}
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
        st.error("Please fill in all fields.")
    else:
        with st.spinner("Fetching data..."):
            wo_raw = get_monday_data(WO_BOARD_ID, MONDAY_API_KEY)
            deal_raw = get_monday_data(DEALS_BOARD_ID, MONDAY_API_KEY)
            
            st.session_state.wo_df = clean_data(wo_raw)
            st.session_state.deal_df = clean_data(deal_raw)
            
            if not st.session_state.wo_df.empty:
                st.success("Data Loaded Successfully!")

tab1, tab2 = st.tabs(["💬 Chat", "📊 Data"])

with tab1:
    query = st.text_area("Ask a question:")
    if st.button("Submit"):
        if st.session_state.wo_df is not None and OPENAI_API_KEY:
            with st.spinner("Thinking..."):
                ans = ask_gpt(query, st.session_state.wo_df, st.session_state.deal_df, OPENAI_API_KEY)
                st.markdown(ans)
        else:
            st.warning("Connect to Monday.com first.")

with tab2:
    if st.session_state.wo_df is not None:
        st.dataframe(st.session_state.wo_df)