import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
from groq import Groq
from PIL import Image
import io
import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.linear_model import LinearRegression

# ==========================================
# --- KONFIGURASI API ---
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"Groq error: {e}")

st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="centered")

# ==========================================
# 🎨 CSS
# ==========================================
st.markdown("""
    <style>
    .main .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    .stButton > button { width: 100%; margin: 5px 0; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# DATABASE
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    try:
        conn = sqlite3.connect('djamantara.db')
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
        conn.close()
    except: pass

def load_chat():
    try:
        conn = sqlite3.connect('djamantara.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        history = c.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in history]
    except: return []

def clear_db():
    try:
        conn = sqlite3.connect('djamantara.db')
        conn.cursor().execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
    except: pass

init_db()

# ==========================================
# FUNGSI TRADING (FIXED)
# ==========================================
def get_stock_data(symbol, period="1mo"):
    try:
        df = yf.download(symbol, period=period, progress=False)
        return df
    except:
        return None

def analyze_stock(df):
    df = df.copy()
    df.dropna(inplace=True)
    if len(df) < 2:
        return df, np.array([]), "NO DATA", 0.0

    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['Days'] = np.arange(len(df))
    model = LinearRegression()
    model.fit(df[['Days']], df['Close'])
    
    last_day = df['Days'].iloc[-1]
    future_days = np.array([last_day + i for i in range(1, 8)]).reshape(-1, 1)
    predictions = model.predict(future_days)
    
    # FIX: Konversi ke float agar menjadi angka tunggal (bukan Series)
    current_price = float(df['Close'].iloc[-1])
    predicted_price = float(predictions[-1])
    
    change_pct = ((predicted_price - current_price) / current_price) * 100
    
    # Sekarang perbandingan aman
    trend = "BULLISH 📈" if change_pct > 2 else "BEARISH 📉" if change_pct < -2 else "SIDEWAYS ➡️"
    
    return df, predictions, trend, change_pct

# ==========================================
# FUNGSI SUARA
# ==========================================
async def generate_voice(text):
    try:
        clean_text = text.replace("*", "").replace("#", "")
        communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural")
        await communicate.save("temp_voice.mp3")
        return True
    except:
        return False

# ==========================================
# SESSION STATE
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()
if "page" not in st.session_state:
    st.session_state.page = "chat"
if "uploaded_img" not in st.session_state:
    st.session_state.uploaded_img = None

# ==========================================
# NAVIGATION
# ==========================================
col1, col2 = st.columns(2)
with col1:
    if st.button("💬 Chat", key="chat_btn"):
        st.session_state.page = "chat"
        st.rerun()
    if st.button("📈 Trading", key="trade_btn"):
        st.session_state.page = "trading"
        st.rerun()
with col2:
    if st.button("📸 Foto", key="foto_btn"):
        st.session_state.page = "foto"
        st.rerun()
    if st.button("🗑️ Clear", key="clear_btn"):
        clear_db()
        st.session_state.messages = []
        st.rerun()

st.markdown("---")

# ==========================================
# PAGE: CHAT
# ==========================================
if st.session_state.page == "chat":
    st.title("💬 Chat dengan Djamantara")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("Ketik pesan atau tanya saham/crypto..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_chat("user", prompt)
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Djamantara berpikir..."):
                try:
                    trading_words = ['saham', 'bitcoin', 'btc', 'crypto', 'harga', 'trading', 'stock']
                    if any(word in prompt.lower() for word in trading_words):
                        response = "💡 Untuk analisa trading lengkap, klik tombol **📈 Trading** di atas!"
                    else:
                        completion = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Kamu Djamantara, asisten AI yang santai dan kocak. Panggil user 'Bos'."},
                                {"role": "user", "content": prompt}
                            ],
                            model="llama-3.3-70b-versatile"
                        )
                        response = completion.choices[0].message.content
                    st.markdown(response)
                    asyncio.run(generate_voice(response))
                    if os.path.exists("temp_voice.mp3"):
                        with open("temp_voice.mp3", "rb") as f:
                            st.audio(f.read(), format="audio/mpeg")
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    save_chat("assistant", response)
                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# PAGE: TRADING
# ==========================================
elif st.session_state.page == "trading":
    st.title("📈 Smart Trading Analysis")
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Symbol", "BTC-USD").upper()
    with col2:
        period = st.selectbox("Periode", ["1wk", "2wk", "1mo", "3mo", "6mo", "1y"])
    
    if st.button("🔍 Analisa Sekarang", type="primary", use_container_width=True):
        with st.spinner(f"Mengambil data {symbol}..."):
            df = get_stock_data(symbol, period)
        
        if df is not None and not df.empty:
            df, predictions, trend, change_pct = analyze_stock(df)
            
            current_price = float(df['Close'].iloc[-1])
            prev_price = float(df['Close'].iloc[-2])
            daily_change = ((current_price - prev_price) / prev_price) * 100
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Harga Sekarang", f"${current_price:.2f}", f"{daily_change:.2f}%")
            with col2:
                st.metric("Prediksi 7 Hari", f"${predictions[-1]:.2f}", f"{change_pct:.2f}%")
            with col3:
                st.metric("Trend", trend)
            
            st.markdown("### 📊 Indikator")
            rsi = df['RSI'].iloc[-1]
            st.write(f"**RSI:** {rsi:.1f} - {'Oversold (Buy)' if rsi < 30 else 'Overbought (Sell)' if rsi > 70 else 'Neutral'}")
            st.write(f"**Price vs SMA20:** {'Above (Bullish)' if current_price > df['SMA20'].iloc[-1] else 'Below (Bearish)'}")
            
            st.markdown("### 🎯 Rekomendasi")
            if rsi < 30 and current_price > df['SMA20'].iloc[-1]:
                st.success("✅ STRONG BUY")
            elif rsi > 70 and current_price < df['SMA20'].iloc[-1]:
                st.error("❌ STRONG SELL")
            elif change_pct > 5:
                st.success("✅ BUY - Uptrend kuat")
            elif change_pct < -5:
                st.error("❌ SELL - Downtrend kuat")
            else:
                st.warning("⚠️ HOLD")
        else:
            st.error("❌ Symbol tidak ditemukan!")

# ==========================================
# PAGE: FOTO
# ==========================================
elif st.session_state.page == "foto":
    st.title("📸 Upload & Analisa Foto")
    uploaded_file = st.file_uploader("Pilih gambar", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        st.session_state.uploaded_img = uploaded_file
        st.markdown("### Preview Foto:")
        st.image(uploaded_file, caption="Foto yang diupload", use_container_width=True)
        
        st.markdown("---")
        if st.button("🔍 Analisa Gambar", type="primary", use_container_width=True):
            with st.spinner("AI sedang menganalisa..."):
                try:
                    img = Image.open(uploaded_file)
                    if img.size[0] > 1024:
                        ratio = 1024 / img.size[0]
                        new_size = (1024, int(img.size[1] * ratio))
                        img = img.resize(new_size)
                    
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG")
                    img_base64 = base64.b64encode(buffered.getvalue()).decode()
                    
                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Analisa gambar ini secara detail dalam bahasa Indonesia."},
                                    {"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{img_base64}"}}
                                ]
                            }
                        ],
                        model="llama-3.2-11b-vision-preview"
                    )
                    
                    st.markdown("### Hasil Analisa:")
                    st.success("✅ Analisa berhasil!")
                    st.markdown(response.choices[0].message.content)
                    
                    asyncio.run(generate_voice(response.choices[0].message.content))
                    if os.path.exists("temp_voice.mp3"):
                        with open("temp_voice.mp3", "rb") as f:
                            st.audio(f.read(), format="audio/mpeg")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    else:
        st.info("📤 Silakan upload foto untuk dianalisa")

# Cleanup
if os.path.exists("temp_voice.mp3"):
    try:
        os.remove("temp_voice.mp3")
    except: pass