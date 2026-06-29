import streamlit as st
import yfinance as yf
import requests
import json

# Page configuration
st.set_page_config(page_title="Desk Quick-Quote Tool", layout="centered")

# --- VISUAL & STRUCTURE LAYER (CSS INJECTION) ---
st.markdown("""
<style>
    html, body, p, .stMarkdown p, [data-testid="stWidgetLabel"] p {
        font-size: 1.25rem !important;
        line-height: 1.6 !important;
    }
    input, textarea, div[data-testid="stMarkdownContainer"] {
        font-size: 1.2rem !important;
    }
    h1 { font-size: 2.5rem !important; }
    h3 { font-size: 1.75rem !important; }

    button.step-up, button.step-down {
        display: none !important;
    }
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { 
        -webkit-appearance: none !important; 
        margin: 0 !important; 
    }
    input[type=number] {
        -moz-appearance: textfield !important;
    }
</style>
""", unsafe_allow_html=True)

# --- BACKEND SECRETS LOADER ---
try:
    gemini_api_key = st.secrets["GEMINI_API_KEY"]
    # Pulls your shared master password out of your hidden backend secrets file
    correct_password = st.secrets["DESK_PASSWORD"]
except Exception:
    gemini_api_key = None
    correct_password = None

# --- PASSWORD VALIDATION ENGINE ---
# If a password isn't set up yet, it forces a warning screen instead of loading data
if not correct_password:
    st.error("🔑 Security Key Error: 'DESK_PASSWORD' is missing from secrets configuration.")
    st.stop()

# Initialize an internal session tracker to keep users logged in while typing
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Render the security gate if the session tracker is currently locked
if not st.session_state["authenticated"]:
    st.title("🔒 Internal Desk Gate")
    user_entry = st.text_input("Enter Desk Access Password to unlock pricing variables:", type="password")
    
    if user_entry:
        if user_entry == correct_password:
            st.session_state["authenticated"] = True
            st.rerun() # Refresh the page immediately to load the core calculator
        else:
            st.error("❌ Incorrect desk password. Access denied.")
            
    st.stop() # Freeze execution here until they pass the security firewall

# --- CORE APPLICATION RUNNER (ONLY ACCESSIBLE IF AUTHENTICATED) ---
st.title("📲 KODA Quick-Pricing Generator")
st.write("Koda strike calculator optimized for formatting WhatsApp client updates.")

if not gemini_api_key:
    st.error("⚠️ Central AI Key missing inside your secrets. Please fix it to unlock AI lookup.")
    st.stop()

# --- INPUT PARAMETERS ---
st.markdown("### 1. Pricing Inputs")

companies_input = st.text_area(
    "Enter 'Company, Strike %' i.e. Westpac AU, 88.46 (One Pair Per Line):", 
    value="Westpac AU, 88.46",
    height=200
)

raw_lines = [line.strip() for line in companies_input.split("\n") if line.strip()]

if raw_lines:
    st.markdown("---")
    st.markdown("### 2. Live Market Calculations")
    
    whatsapp_compiled_output = ""
    
    for line in raw_lines:
        if "," in line:
            parts = line.split(",", 1)
        elif "\t" in line:
            parts = line.split("\t", 1)
        else:
            st.warning(f"⚠️ Line skipped: '{line}' is missing a strike percentage. Use format: Company, Strike")
            continue
            
        query = parts[0].strip()
        
        try:
            clean_strike_string = parts[1].replace("%", "").strip()
            row_strike_pct = float(clean_strike_string)
        except (IndexError, ValueError):
            st.error(f"❌ Missing or invalid strike percentage on line: '{line}'")
            continue
                
        if not query:
            continue
            
        with st.spinner(f"Resolving variables for '{query}'..."):
            api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": gemini_api_key.strip()
            }
            
            system_instruction = (
                "You are a strict, deterministic financial ticker mapping tool. Your job is to output the correct "
                "Yahoo Finance ticker symbol corresponding to the company name provided.\n\n"
                "STRICT REGIONAL EXPLICIT RULES:\n"
                "- If the query contains 'AU', 'AUS', or 'AUSTRALIA', you MUST append '.AX' (e.g., 'rio tinto aus' -> 'RIO.AX').\n"
                "- If the query contains 'SG', 'SINGAPORE', you MUST append '.SI' (e.g., 'singtel singapore' -> 'Z74.SI').\n"
                "- If the query contains 'HK', 'HONG KONG', you MUST append '.HK' (e.g., 'alibaba hk' -> '9988.HK').\n"
                "- If the query contains 'MY', 'MALAYSIA', or 'KLSE', you MUST convert the name to its official 4-digit numeric code and append '.KL' (e.g., 'mahsing my' -> '8583.KL').\n"
                "- If the query contains 'JP', 'JAPAN', or 'TSE', you MUST convert the name to its official 4-digit numeric code and append '.T' (e.g., 'toyota japan' -> '7203.T').\n"
                "- If the query specifies 'US', 'USA', 'ADR', or matches a prominent US tech stock, output the clean US ticker symbol (e.g., 'tsmc us' -> 'TSM', 'apple' -> 'AAPL').\n\n"
                "STRICT INTUITIVE FALLBACK RULE:\n"
                "- If the user does NOT provide any country name, region abbreviation, or exchange suffix, you MUST return the absolute dominant primary domestic listing ticker for that asset. Never default to low-volume OTC listings.\n\n"
                "CRITICAL CONTROLS:\n"
                "1. Do NOT hallucinate or substitute companies.\n"
                "2. If an exchange relies on numeric identifiers, return the exact number ticker code.\n"
                "3. Output ONLY the raw ticker symbol string. No explanations, no markdown formatting, no punctuation."
            )
            
            payload = {
                "contents": [{"parts": [{"text": f"{system_instruction}\n\nUser Query: {query}"}]}],
                "generationConfig": { "temperature": 0.0 }
            }
            
            resolved_ticker = None
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=5)
                if response.status_code == 200:
                    response_json = response.json()
                    raw_text = response_json['candidates'][0]['content']['parts'][0]['text']
                    resolved_ticker = raw_text.strip().replace("`", "").replace("'", "").upper()
            except Exception:
                pass
                
            if not resolved_ticker:
                st.error(f"❌ Could not resolve ticker for query string: **{query}**")
                continue
                
            try:
                asset = yf.Ticker(resolved_ticker)
                spot_price = asset.fast_info['last_price']
                currency = asset.fast_info['currency'].upper()
                company_name = asset.info.get('longName', resolved_ticker)
                
                strike_dollars = spot_price * (row_strike_pct / 100.0)
                st.success(f"✅ **{resolved_ticker}** | Spot: **{spot_price:,.2f} {currency}** | Strike ({row_strike_pct:.2f}%): **{strike_dollars:,.2f} {currency}**")
                
                whatsapp_compiled_output += f"{company_name} ({resolved_ticker})\n"
                whatsapp_compiled_output += f"- Spot: ${spot_price:,.2f} {currency}\n"
                whatsapp_compiled_output += f"- Strike: ${strike_dollars:,.2f} {currency} ({row_strike_pct:.2f}%) \n\n"
                
            except Exception:
                st.error(f"❌ Financial market database lookup failed for resolved symbol: **{resolved_ticker}**")

    # --- DISPLAY CONSOLIDATED CLIPBOARD COPIER ---
    if whatsapp_compiled_output:
        st.markdown("---")
        st.markdown("### 3. WhatsApp Ready Clipboard Block")
        st.code(whatsapp_compiled_output.strip(), language="text")
