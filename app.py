import streamlit as st
import os
from groq import Groq
import sqlite3
import time
import base64
import io
from PIL import Image
import yfinance as yf
import pandas as pd

# ==========================================
# KONFIGURASI
# ==========================================
st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="wide")

# API Key
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

try:
    client = Groq(api_key=GROQ_API_KEY)
except:
    st.error("API Error - Check your key")
    st.stop()

# ==========================================
# DATABASE SIMPLE
# ==========================================
@st.cache_resource
def init_db():
    return sqlite3.connect('djamantara.db', check_same_thread=False)

conn = init_db()
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS chat 
             (role TEXT, content TEXT, time DATETIME DEFAULT CURRENT_TIMESTAMP)''')
conn.commit()

def save_msg(role, content):
    try:
        c.execute("INSERT INTO chat (role, content) VALUES (?, ?)", (role, content))
        conn.commit()
    except: pass

def load_msg():
    try:
        c.execute("SELECT role, content FROM chat ORDER BY time LIMIT 50")
        return [{"role": r, "content": c} for r, c in c.fetchall()]
    except: return []

def clear_msg():
    c.execute("DELETE FROM chat")
    conn.commit()

# ==========================================
# TRADING SIMPLE
# ==========================================
def get_price(symbol, period="1mo"):
    try:
        df = yf.download(symbol, period=period, progress=False)
        if df.empty: return None
        return df
    except: return None

def analyze_simple(df):
    try:
        current = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        change = ((current - prev) / prev) * 100
        
        # Simple trend
        sma = df['Close'].rolling(20).mean().iloc[-1]
        trend = "BULLISH 📈" if current > sma else "BEARISH 📉"
        
        return {
            'price': current,
            'change': change,
            'trend': trend,
            'sma': sma
        }
    except: return None

# ==========================================
# SESSION
# ==========================================
if 'page' not in st.session_state:
    st.session_state.page = 'chat'
if 'messages' not in st.session_state:
    st.session_state.messages = load_msg()

# ==========================================
# NAVIGATION
# ==========================================
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("💬 Chat", use_container_width=True):
        st.session_state.page = 'chat'
        st.rerun()
with col2:
    if st.button("📈 Trading", use_container_width=True):
        st.session_state.page = 'trading'
        st.rerun()
with col3:
    if st.button("📸 Foto", use_container_width=True):
        st.session_state.page = 'foto'
        st.rerun()

st.markdown("---")

# ==========================================
# PAGE: CHAT
# ==========================================
if st.session_state.page == 'chat':
    st.title("💬 Djamantara AI Chat")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])
    
    if prompt := st.chat_input("Ketik pesan..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_msg("user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            try:
                response = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Kamu Djamantara, AI assistant yang helpful. Panggil user 'Bos'."},
                        {"role": "user", "content": prompt}
                    ],
                    model="llama-3.3-70b-versatile"
                )
                reply = response.choices[0].message.content
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
                save_msg("assistant", reply)
            except Exception as e:
                st.error(f"Error: {e}")

# ==========================================
# PAGE: TRADING
# ==========================================
elif st.session_state.page == 'trading':
    st.title("📈 Trading Analysis")
    
    symbol = st.text_input("Symbol (BTC-USD, BBRI.JK, AAPL)", "BTC-USD").upper()
    period = st.selectbox("Periode", ["1wk", "1mo", "3mo", "6mo", "1y"])
    
    if st.button("Analisa", type="primary"):
        with st.spinner(f"Loading {symbol}..."):
            df = get_price(symbol, period)
        
        if df is not None and len(df) > 20:
            data = analyze_simple(df)
            if data:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Harga", f"${data['price']:.2f}", f"{data['change']:.2f}%")
                with col2:
                    st.metric("Trend", data['trend'])
                with col3:
                    st.metric("SMA 20", f"${data['sma']:.2f}")
                
                # Simple chart
                st.line_chart(df['Close'])
                
                # AI Insight
                with st.spinner("AI analyzing..."):
                    try:
                        insight = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Berikan analisis trading singkat dalam bahasa Indonesia."},
                                {"role": "user", "content": f"{symbol}: ${data['price']:.2f}, {data['change']:.2f}%, {data['trend']}"}
                            ],
                            model="llama-3.3-70b-versatile"
                        )
                        st.markdown("### AI Insight:")
                        st.markdown(insight.choices[0].message.content)
                    except: pass
            else:
                st.error("Analysis failed")
        else:
            st.error("Data tidak cukup. Pilih periode lebih panjang.")

# ==========================================
# PAGE: FOTO
# ==========================================
elif st.session_state.page == 'foto':
    st.title("📸 Image Analysis")
    
    uploaded = st.file_uploader("Upload foto", type=["jpg", "jpeg", "png"])
    
    if uploaded:
        st.image(uploaded, caption="Preview", use_container_width=True)
        
        if st.button("Analisa Gambar", type="primary"):
            with st.spinner("Processing..."):
                try:
                    img = Image.open(uploaded)
                    
                    # Resize
                    if img.size[0] > 1024:
                        ratio = 1024 / img.size[0]
                        img = img.resize((1024, int(img.size[1] * ratio)))
                    
                    # Convert
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG")
                    img_b64 = base64.b64encode(buffered.getvalue()).decode()
                    
                    # AI Vision
                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Analisa gambar ini dalam bahasa Indonesia"},
                                    {"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{img_b64}"}}
                                ]
                            }
                        ],
                        model="llama-3.2-90b-vision-preview"
                    )
                    
                    st.markdown("### Hasil:")
                    st.markdown(response.choices[0].message.content)
                    
                except Exception as e:
                    st.error(f"Error: {e}")

# Clear button
if st.button("🗑️ Clear Chat"):
    clear_msg()
    st.session_state.messages = []
    st.rerun()