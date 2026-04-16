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
from plotly.subplots import make_subplots
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import MinMaxScaler

# ==========================================
# --- KONFIGURASI API AMAN ---
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
    if not GROQ_API_KEY:
        st.error("⚠️ API Key tidak ditemukan!")
        st.stop()

# --- SETTING LAYAR MOBILE RESPONSIF ---
st.set_page_config(
    page_title="Djamantara AI - Trading & Chat", 
    page_icon="📈", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 🎨 CSS INJECTION - TRADING UI
# ==========================================
st.markdown("""
    <style>
    /* Hide ALL default elements */
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; 
        display: none !important;
    }
    .viewerBadge, .github-link, [data-testid="stDecoration"], .stDeployButton {
        visibility: hidden !important; 
        display: none !important;
    }
    
    /* Main container */
    .main .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    
    /* Trading Card */
    .trading-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        border: 1px solid #00d9ff;
        box-shadow: 0 4px 15px rgba(0, 217, 255, 0.2);
    }
    
    /* Price Display */
    .price-display {
        font-size: 2rem;
        font-weight: bold;
        color: #00ff88;
        margin: 10px 0;
    }
    .price-down {
        color: #ff4444;
    }
    
    /* Prediction Badge */
    .prediction-badge {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        margin: 5px;
        font-size: 0.9rem;
    }
    .bullish {
        background: #00ff88;
        color: #000;
    }
    .bearish {
        background: #ff4444;
        color: #fff;
    }
    .neutral {
        background: #ffa500;
        color: #000;
    }
    
    /* GIF Styling */
    .cat-container img {
        max-width: 100px !important;
        height: auto !important;
        display: block !important;
        margin: 0 auto !important;
    }
    .moto-text {
        font-size: 0.8rem !important;
        line-height: 1.4 !important;
        text-align: center !important;
        margin-top: 5px !important;
        margin-bottom: 10px !important;
        color: #888 !important;
    }
    
    /* Image Preview Box */
    .image-preview-box {
        background: #1a1f2e;
        padding: 10px;
        border-radius: 12px;
        margin: 10px 0;
        border: 1px solid #333;
    }
    
    /* Chat Input Container */
    .stChatInputContainer {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        padding: 10px 15px 15px 15px !important;
        background: linear-gradient(to top, #0e1117 0%, transparent 100%) !important;
        z-index: 999 !important;
        margin: 0 !important;
    }
    
    /* Mobile adjustments */
    @media only screen and (max-width: 600px) {
        h1 { font-size: 1.3rem !important; }
        .price-display { font-size: 1.5rem !important; }
        .moto-text { font-size: 0.7rem !important; }
    }
    
    /* Hide scrollbar */
    ::-webkit-scrollbar { width: 0px; }
    
    /* Main content padding */
    .main > div {
        padding-bottom: 150px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Setup Klien API
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Waduh Bos, Groq-nya bermasalah: {e}")

# ==========================================
# --- 1. SISTEM INGATAN (DATABASE) ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
        conn.close()
    except: pass

def load_chat():
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        history = c.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in history]
    except: return []

def clear_chat_db():
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        conn.cursor().execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        return True
    except:
        return False

init_db()

# ==========================================
# --- 2. FUNGSI TRADING PREDICTION ---
# ==========================================
def fetch_stock_data(symbol, period="1mo"):
    """Fetch data saham/crypto dari Yahoo Finance"""
    try:
        stock = yf.download(symbol, period=period, interval="1d")
        return stock
    except Exception as e:
        st.error(f"❌ Gagal ambil data: {e}")
        return None

def calculate_indicators(df):
    """Hitung indikator teknikal"""
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['EMA_12'] = df['Close'].ewm(span=12).mean()
    df['EMA_26'] = df['Close'].ewm(span=26).mean()
    
    # MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['Signal'] = df['MACD'].ewm(span=9).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    df['BB_std'] = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + (df['BB_std'] * 2)
    df['BB_lower'] = df['BB_middle'] - (df['BB_std'] * 2)
    
    return df

def predict_trend(df, days=7):
    """Prediksi trend dengan Linear Regression"""
    df_train = df[['Close']].dropna()
    df_train['Days'] = np.arange(len(df_train))
    
    X = df_train[['Days']]
    y = df_train['Close']
    
    model = LinearRegression()
    model.fit(X, y)
    
    # Prediksi
    last_day = df_train['Days'].iloc[-1]
    future_days = np.arange(last_day + 1, last_day + 1 + days).reshape(-1, 1)
    predictions = model.predict(future_days)
    
    # Trend analysis
    current_price = df['Close'].iloc[-1]
    predicted_price = predictions[-1]
    change_percent = ((predicted_price - current_price) / current_price) * 100
    
    trend = "BULLISH 📈" if change_percent > 2 else "BEARISH 📉" if change_percent < -2 else "NEUTRAL ➡️"
    
    return predictions, trend, change_percent

def generate_signals(df):
    """Generate buy/sell signals"""
    signals = []
    
    last_row = df.iloc[-1]
    
    # RSI Signal
    if last_row['RSI'] < 30:
        signals.append("✅ RSI Oversold (Buy Signal)")
    elif last_row['RSI'] > 70:
        signals.append("⚠️ RSI Overbought (Sell Signal)")
    
    # MACD Signal
    if last_row['MACD'] > last_row['Signal']:
        signals.append("✅ MACD Bullish")
    else:
        signals.append("⚠️ MACD Bearish")
    
    # SMA Signal
    if last_row['Close'] > last_row['SMA_20']:
        signals.append("✅ Price Above SMA-20")
    else:
        signals.append("⚠️ Price Below SMA-20")
    
    # Bollinger Bands
    if last_row['Close'] < last_row['BB_lower']:
        signals.append("✅ Price at Lower BB (Buy)")
    elif last_row['Close'] > last_row['BB_upper']:
        signals.append("⚠️ Price at Upper BB (Sell)")
    
    return signals

def create_chart(df, predictions, symbol):
    """Buat chart interaktif dengan Plotly"""
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, 
                        row_heights=[0.7, 0.3],
                        subplot_titles=(f'{symbol} Price & Prediction', 'Volume'))
    
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
    ), row=1, col=1)
    
    # SMA
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], 
                             name='SMA 20', line=dict(color='blue', width=1)), 
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], 
                             name='SMA 50', line=dict(color='orange', width=1)), 
                  row=1, col=1)
    
    # Predictions
    future_dates = pd.date_range(start=df.index[-1], periods=len(predictions)+1)[1:]
    fig.add_trace(go.Scatter(x=future_dates, y=predictions, 
                             name='Prediction', 
                             line=dict(color='#00d9ff', width=2, dash='dash')), 
                  row=1, col=1)
    
    # Volume
    colors = ['#00ff88' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#ff4444' 
              for i in range(len(df))]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], 
                         name='Volume', 
                         marker_color=colors), 
                  row=2, col=1)
    
    fig.update_layout(
        height=800,
        template='plotly_dark',
        showlegend=True,
        xaxis_rangeslider_visible=False
    )
    
    return fig

# ==========================================
# --- 3. FUNGSI PENDUKUNG LAINNYA ---
# ==========================================
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as file_:
            contents = file_.read()
            return base64.b64encode(contents).decode("utf-8")
    return None

def compress_image(uploaded_file, max_size=1024, quality=85):
    img = Image.open(uploaded_file)
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    
    width, height = img.size
    if width > max_size or height > max_size:
        ratio = min(max_size / width, max_size / height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
    img_byte_arr.seek(0)
    
    return img_byte_arr

def encode_image(image_source):
    if hasattr(image_source, 'seek'):
        image_source.seek(0)
    return base64.b64encode(image_source.read()).decode('utf-8')

def run_async_safe(coro_func, *args):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import threading
            result = None
            def _run():
                nonlocal result
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(coro_func(*args))
                new_loop.close()
            thread = threading.Thread(target=_run)
            thread.start()
            thread.join()
            return result
        else:
            return loop.run_until_complete(coro_func(*args))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro_func(*args))
        loop.close()
        return result

async def generate_voice(text):
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

# ==========================================
# --- 4. INISIALISASI SESSION STATE ---
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()
if "current_image" not in st.session_state:
    st.session_state.current_image = None
if "compressed_image" not in st.session_state:
    st.session_state.compressed_image = None

# ==========================================
# --- 5. TAMPILAN UTAMA ---
# ==========================================

# Tabs untuk navigasi
tab1, tab2, tab3 = st.tabs(["💬 Chat AI", "📈 Trading Prediction", "📸 Upload Foto"])

with tab1:
    # --- CHAT SECTION ---
    gif_result = get_local_gif("kucing.gif")
    
    if gif_result is not None:
        st.markdown(
            f"""
            <div style="text-align: center; margin-top: -10px;" class="cat-container">
                <img src="image/gif;base64,{gif_result}" style="z-index: 1;">
                <h1 style="margin: 5px 0; padding: 0; font-size: 1.5rem;">🤖 Djamantara AI</h1>
                <p class="moto-text">Chat & Trading Assistant</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    # Chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ngobrol atau tanya saham/crypto, Bos..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_chat("user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Si Kocheng lagi mikir..."):
                try:
                    # Cek apakah pertanyaan tentang trading
                    trading_keywords = ['saham', 'stock', 'bitcoin', 'btc', 'crypto', 'eth', 'ethereum', 'harga', 'price', 'trading']
                    is_trading_query = any(keyword in prompt.lower() for keyword in trading_keywords)
                    
                    if is_trading_query:
                        # Handle trading query
                        response_text = f"Bos, untuk analisis trading lengkap, silakan buka tab **📈 Trading Prediction** di atas. Di situ ada chart, prediksi, dan sinyal lengkap! 📊"
                    else:
                        # Regular chat
                        context = st.session_state.messages[-5:]
                        chat_completion = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Gunakan bahasa santai Indonesia-Madura."},
                                *context
                            ],
                            model="llama-3.3-70b-versatile",
                        )
                        response_text = chat_completion.choices[0].message.content
                    
                    st.markdown(response_text)
                    
                    # Voice
                    run_async_safe(generate_voice, response_text)
                    if os.path.exists("temp_voice.mp3"):
                        st.audio("temp_voice.mp3", format="audio/mpeg")
                    
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    save_chat("assistant", response_text)
                    
                except Exception as e:
                    st.error(f"Duh Bos, sistem macet: {str(e)}")

with tab2:
    # --- TRADING PREDICTION SECTION ---
    st.markdown("## 📈 Smart Trading Prediction")
    st.markdown("Analisis teknikal & prediksi harga saham/crypto dengan AI")
    
    # Input symbol
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        symbol = st.text_input("Symbol (contoh: BBRI.JK, BTC-USD, AAPL)", "BTC-USD").upper()
    with col2:
        period = st.selectbox("Periode", ["1wk", "1mo", "3mo", "6mo", "1y"])
    with col3:
        analyze_btn = st.button("🔍 Analisis", use_container_width=True)
    
    if analyze_btn or 'last_symbol' in st.session_state:
        st.session_state.last_symbol = symbol
        
        with st.spinner(f"📊 Mengambil data {symbol}..."):
            df = fetch_stock_data(symbol, period)
        
        if df is not None and not df.empty:
            # Calculate indicators
            df = calculate_indicators(df)
            
            # Predict trend
            predictions, trend, change_percent = predict_trend(df, days=7)
            
            # Generate signals
            signals = generate_signals(df)
            
            # Display info
            col1, col2, col3, col4 = st.columns(4)
            current_price = df['Close'].iloc[-1]
            price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
            change_pct = (price_change / df['Close'].iloc[-2]) * 100
            
            with col1:
                st.markdown("### Harga Saat Ini")
                st.markdown(f"<div class='price-display {'price-down' if price_change < 0 else ''}'>${current_price:.2f}</div>", unsafe_allow_html=True)
                st.markdown(f"{'📈' if price_change > 0 else '📉'} {change_pct:.2f}%")
            
            with col2:
                st.markdown("### Prediksi 7 Hari")
                st.markdown(f"<div class='price-display'>${predictions[-1]:.2f}</div>", unsafe_allow_html=True)
                st.markdown(f"{'📈' if change_percent > 0 else '📉'} {change_percent:.2f}%")
            
            with col3:
                st.markdown("### Trend")
                trend_class = "bullish" if "BULLISH" in trend else "bearish" if "BEARISH" in trend else "neutral"
                st.markdown(f"<div class='prediction-badge {trend_class}'>{trend}</div>", unsafe_allow_html=True)
            
            with col4:
                st.markdown("### RSI")
                rsi_value = df['RSI'].iloc[-1]
                rsi_status = "Oversold ✅" if rsi_value < 30 else "Overbought ⚠️" if rsi_value > 70 else "Normal ➡️"
                st.markdown(f"**{rsi_value:.1f}** - {rsi_status}")
            
            # Chart
            st.markdown("### 📊 Chart & Prediksi")
            fig = create_chart(df, predictions, symbol)
            st.plotly_chart(fig, use_container_width=True)
            
            # Signals
            st.markdown("### 🎯 Trading Signals")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Indikator Teknikal:**")
                for signal in signals:
                    st.markdown(signal)
            
            with col2:
                st.markdown("**Rekomendasi:**")
                buy_signals = sum(1 for s in signals if "✅" in s)
                sell_signals = sum(1 for s in signals if "⚠️" in s)
                
                if buy_signals > sell_signals:
                    st.success("✅ **RECOMMENDED: BUY**")
                    st.markdown(f"Strong buy signal ({buy_signals}/{len(signals)} indicators)")
                elif sell_signals > buy_signals:
                    st.error("⚠️ **RECOMMENDED: SELL/WAIT**")
                    st.markdown(f"Strong sell signal ({sell_signals}/{len(signals)} indicators)")
                else:
                    st.warning("➡️ **RECOMMENDED: HOLD**")
                    st.markdown("Neutral signals")
            
            # AI Analysis
            st.markdown("### 🤖 AI Analysis")
            with st.spinner("Djamantara sedang menganalisa..."):
                try:
                    analysis_prompt = f"""
                    Berikan analisis trading untuk {symbol} berdasarkan data:
                    - Harga saat ini: ${current_price:.2f}
                    - Trend: {trend}
                    - Prediksi 7 hari: ${predictions[-1]:.2f} ({change_percent:.2f}%)
                    - RSI: {rsi_value:.1f}
                    - Signals: {', '.join(signals)}
                    
                    Berikan saran trading yang santai dan mudah dimengerti dalam bahasa Indonesia.
                    """
                    
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Kamu adalah asisten trading AI yang ahli. Berikan analisis profesional tapi santai."},
                            {"role": "user", "content": analysis_prompt}
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                    
                    ai_analysis = chat_completion.choices[0].message.content
                    st.markdown(ai_analysis)
                    
                except Exception as e:
                    st.error(f"AI analysis error: {e}")
        else:
            st.error("❌ Data tidak ditemukan. Cek symbol yang dimasukkan!")

with tab3:
    # --- UPLOAD FOTO SECTION ---
    st.markdown("## 📸 Upload Foto untuk Analisa")
    
    uploaded_file = st.file_uploader("Pilih gambar...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        with st.spinner("🔄 Kompres & upload..."):
            try:
                compressed_img = compress_image(uploaded_file, max_size=1024, quality=85)
                st.session_state.current_image = uploaded_file
                st.session_state.compressed_image = compressed_img
                st.success("✅ Upload berhasil!")
                
                # Preview
                st.image(uploaded_file, caption="Foto yang diupload", use_container_width=True)
                
                if st.button("❌ Hapus Foto"):
                    st.session_state.current_image = None
                    st.session_state.compressed_image = None
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error: {e}")

# Cleanup
if os.path.exists("temp_voice.mp3"):
    try: 
        time.sleep(3)
        os.remove("temp_voice.mp3")
    except: pass