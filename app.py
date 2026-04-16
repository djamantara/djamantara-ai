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
from datetime import datetime, timedelta
import plotly.graph_objects as go

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

# Page config
st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="wide")

# ==========================================
# 🎨 CSS - LAYOUT RAPI
# ==========================================
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    .stChatMessage {
        margin: 10px 0;
    }
    .trading-box {
        background: #1e3a5f;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .price-up { color: #00ff88; font-size: 1.5rem; font-weight: bold; }
    .price-down { color: #ff4444; font-size: 1.5rem; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# DATABASE
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
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
# FUNGSI TRADING
# ==========================================
def get_stock_data(symbol, period="1mo"):
    try:
        df = yf.download(symbol, period=period, progress=False)
        return df
    except:
        return None

def analyze_stock(df):
    # Simple Moving Average
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Simple prediction - linear trend
    df['Days'] = range(len(df))
    from sklearn.linear_model import LinearRegression
    model = LinearRegression()
    model.fit(df[['Days']], df['Close'])
    
    last_day = df['Days'].iloc[-1]
    future_days = np.array([last_day + i for i in range(1, 8)]).reshape(-1, 1)
    predictions = model.predict(future_days)
    
    current_price = df['Close'].iloc[-1]
    predicted_price = predictions[-1]
    change_pct = ((predicted_price - current_price) / current_price) * 100
    
    trend = "BULLISH 📈" if change_pct > 2 else "BEARISH 📉" if change_pct < -2 else "SIDEWAYS ➡️"
    
    return df, predictions, trend, change_pct

def create_chart(df, predictions, symbol):
    fig = go.Figure()
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price',
        increasing_line_color='#00ff88',
        decreasing_line_color='#ff4444'
    ))
    
    # SMA
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], name='SMA 20', line=dict(color='blue')))
    
    # Prediction line
    future_dates = pd.date_range(start=df.index[-1], periods=8)[1:]
    fig.add_trace(go.Scatter(
        x=future_dates, 
        y=predictions, 
        name='Prediction (7 days)', 
        line=dict(color='orange', dash='dash')
    ))
    
    fig.update_layout(
        title=f'{symbol} - Price & Prediction',
        yaxis_title='Price',
        xaxis_title='Date',
        height=600,
        template='plotly_dark',
        showlegend=True
    )
    
    return fig

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

def play_audio():
    if os.path.exists("temp_voice.mp3"):
        with open("temp_voice.mp3", "rb") as f:
            st.audio(f.read(), format="audio/mpeg")

# ==========================================
# SESSION STATE
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()
if "page" not in st.session_state:
    st.session_state.page = "chat"

# ==========================================
# NAVIGATION
# ==========================================
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("💬 Chat", use_container_width=True):
        st.session_state.page = "chat"
        st.rerun()
with col2:
    if st.button("📈 Trading", use_container_width=True):
        st.session_state.page = "trading"
        st.rerun()
with col3:
    if st.button("📸 Foto", use_container_width=True):
        st.session_state.page = "foto"
        st.rerun()
with col4:
    if st.button("🗑️ Clear", use_container_width=True):
        clear_db()
        st.session_state.messages = []
        st.rerun()

st.markdown("---")

# ==========================================
# PAGE: CHAT
# ==========================================
if st.session_state.page == "chat":
    st.title("💬 Chat dengan Djamantara")
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ketik pesan atau tanya saham/crypto..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_chat("user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Djamantara berpikir..."):
                try:
                    # Check if trading related
                    trading_words = ['saham', 'bitcoin', 'btc', 'crypto', 'harga', 'trading', 'stock']
                    if any(word in prompt.lower() for word in trading_words):
                        response = "💡 Untuk analisa trading lengkap, klik tombol **📈 Trading** di atas. Masukkan symbol saham/crypto yang mau dianalisa!"
                    else:
                        # AI Response
                        completion = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Kamu Djamantara, asisten AI yang santai dan kocak. Panggil user 'Bos'."},
                                {"role": "user", "content": prompt}
                            ],
                            model="llama-3.3-70b-versatile"
                        )
                        response = completion.choices[0].message.content
                    
                    st.markdown(response)
                    
                    # Generate & play voice
                    asyncio.run(generate_voice(response))
                    time.sleep(0.5)
                    play_audio()
                    
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    save_chat("assistant", response)
                    
                except Exception as e:
                    st.error(f"Error: {e}")

# ==========================================
# PAGE: TRADING
# ==========================================
elif st.session_state.page == "trading":
    st.title("📈 Smart Trading Analysis")
    st.markdown("Analisis teknikal & prediksi harga saham/crypto")
    
    # Input
    col1, col2 = st.columns(2)
    with col1:
        symbol = st.text_input("Symbol", "BTC-USD").upper()
        st.markdown("Contoh: BTC-USD, ETH-USD, BBRI.JK, AAPL")
    with col2:
        period = st.selectbox("Periode", ["1wk", "2wk", "1mo", "3mo", "6mo", "1y"])
    
    if st.button("🔍 Analisa Sekarang", type="primary"):
        with st.spinner(f"Mengambil data {symbol}..."):
            df = get_stock_data(symbol, period)
        
        if df is not None and not df.empty:
            # Analysis
            df, predictions, trend, change_pct = analyze_stock(df)
            
            # Display metrics
            current_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2]
            daily_change = ((current_price - prev_price) / prev_price) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Harga Sekarang", f"${current_price:.2f}", f"{daily_change:.2f}%")
            with col2:
                st.metric("Prediksi 7 Hari", f"${predictions[-1]:.2f}", f"{change_pct:.2f}%")
            with col3:
                st.metric("Trend", trend)
            with col4:
                rsi = df['RSI'].iloc[-1]
                st.metric("RSI", f"{rsi:.1f}")
            
            # Chart
            st.markdown("### 📊 Chart & Prediksi")
            fig = create_chart(df, predictions, symbol)
            st.plotly_chart(fig, use_container_width=True)
            
            # Trading signals
            st.markdown("### 🎯 Trading Signals")
            
            rsi = df['RSI'].iloc[-1]
            price_vs_sma = current_price > df['SMA20'].iloc[-1]
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Indikator:**")
                st.write(f"• RSI: {rsi:.1f} - {'Oversold (Buy)' if rsi < 30 else 'Overbought (Sell)' if rsi > 70 else 'Neutral'}")
                st.write(f"• Price vs SMA20: {'Above (Bullish)' if price_vs_sma else 'Below (Bearish)'}")
                st.write(f"• Trend 7 Hari: {trend}")
            
            with col2:
                st.markdown("**Rekomendasi:**")
                if rsi < 30 and price_vs_sma:
                    st.success("✅ STRONG BUY")
                elif rsi > 70 and not price_vs_sma:
                    st.error("❌ STRONG SELL")
                elif change_pct > 5:
                    st.success("✅ BUY - Uptrend kuat")
                elif change_pct < -5:
                    st.error("❌ SELL - Downtrend kuat")
                else:
                    st.warning("⚠️ HOLD - Wait for better signal")
            
            # AI Insight
            st.markdown("### 🤖 AI Insight")
            try:
                insight_prompt = f"""
                Analisis trading {symbol}:
                - Harga: ${current_price:.2f}
                - Trend: {trend} ({change_pct:.2f}%)
                - RSI: {rsi:.1f}
                - vs SMA20: {'Above' if price_vs_sma else 'Below'}
                
                Berikan insight trading singkat & actionable dalam bahasa Indonesia.
                """
                completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Kamu ahli trading. Berikan insight profesional tapi singkat."},
                        {"role": "user", "content": insight_prompt}
                    ],
                    model="llama-3.3-70b-versatile"
                )
                st.markdown(completion.choices[0].message.content)
            except:
                st.markdown("AI insight tidak tersedia")
        else:
            st.error("❌ Symbol tidak ditemukan!")

# ==========================================
# PAGE: FOTO
# ==========================================
elif st.session_state.page == "foto":
    st.title("📸 Upload & Analisa Foto")
    
    uploaded_file = st.file_uploader("Pilih gambar", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        # Compress
        img = Image.open(uploaded_file)
        if img.size[0] > 1024:
            ratio = 1024 / img.size[0]
            new_size = (1024, int(img.size[1] * ratio))
            img = img.resize(new_size)
        
        st.image(img, caption="Foto yang diupload", use_container_width=True)
        
        if st.button(" Analisa dengan AI"):
            with st.spinner("Mengirim ke AI..."):
                try:
                    # Convert to base64
                    buffered = io.BytesIO()
                    img.save(buffered, format="JPEG")
                    img_base64 = base64.b64encode(buffered.getvalue()).decode()
                    
                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Analisa gambar ini secara detail dalam bahasa Indonesia"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
                                ]
                            }
                        ],
                        model="llama-3.2-90b-vision-preview"
                    )
                    
                    st.markdown("### Hasil Analisa:")
                    st.markdown(response.choices[0].message.content)
                    
                    # Voice
                    asyncio.run(generate_voice(response.choices[0].message.content))
                    time.sleep(0.5)
                    play_audio()
                    
                except Exception as e:
                    st.error(f"Error: {e}")

# Cleanup
if os.path.exists("temp_voice.mp3"):
    try:
        os.remove("temp_voice.mp3")
    except: pass