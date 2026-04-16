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
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
warnings.filterwarnings('ignore')

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
    st.error(f"Groq API Error: {e}")

# Page config
st.set_page_config(
    page_title="Djamantara AI - Professional Trading & Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 🎨 PROFESSIONAL CSS
# ==========================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    
    /* Navigation Buttons */
    .nav-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s;
    }
    .nav-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #2d3748;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-label {
        color: #a0aec0;
        font-size: 0.875rem;
        margin-bottom: 8px;
    }
    .metric-value {
        color: #ffffff;
        font-size: 1.875rem;
        font-weight: 700;
    }
    .metric-change-up {
        color: #48bb78;
        font-size: 0.875rem;
    }
    .metric-change-down {
        color: #f56565;
        font-size: 0.875rem;
    }
    
    /* Signal Badges */
    .signal-buy {
        background: #48bb78;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }
    .signal-sell {
        background: #f56565;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }
    .signal-hold {
        background: #ed8936;
        color: white;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 600;
        display: inline-block;
    }
    
    /* Chat Messages */
    .stChatMessage {
        margin: 10px 0;
        padding: 12px;
        border-radius: 8px;
    }
    
    /* Hide Streamlit Branding */
    #MainMenu, footer, header {
        visibility: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# DATABASE
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    try:
        conn = sqlite3.connect('djamantara.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Database error: {e}")

def load_chat():
    try:
        conn = sqlite3.connect('djamantara.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC LIMIT 50")
        history = c.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in history]
    except:
        return []

def clear_db():
    try:
        conn = sqlite3.connect('djamantara.db', check_same_thread=False)
        conn.cursor().execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
    except:
        pass

init_db()

# ==========================================
# TRADING FUNCTIONS
# ==========================================
@st.cache_data(ttl=300)
def get_stock_data(symbol, period="1mo"):
    """Fetch stock data with error handling"""
    try:
        df = yf.download(symbol, period=period, progress=False, interval="1d")
        if df.empty:
            return None
        return df
    except Exception as e:
        st.error(f"Failed to fetch data: {str(e)}")
        return None

def calculate_indicators(df):
    """Calculate technical indicators"""
    try:
        # Moving Averages
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['EMA12'] = df['Close'].ewm(span=12).mean()
        df['EMA26'] = df['Close'].ewm(span=26).mean()
        
        # MACD
        df['MACD'] = df['EMA12'] - df['EMA26']
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
    except Exception as e:
        st.error(f"Indicator calculation error: {e}")
        return df

def predict_trend(df, days=7):
    """Predict price trend using linear regression"""
    try:
        df_clean = df[['Close']].dropna()
        if len(df_clean) < 2:
            return None, "INSUFFICIENT DATA", 0
        
        df_clean = df_clean.copy()
        df_clean['Days'] = range(len(df_clean))
        
        X = df_clean[['Days']]
        y = df_clean['Close']
        
        model = LinearRegression()
        model.fit(X, y)
        
        last_day = df_clean['Days'].iloc[-1]
        future_days = np.array([last_day + i for i in range(1, days + 1)]).reshape(-1, 1)
        predictions = model.predict(future_days)
        
        current_price = df['Close'].iloc[-1]
        predicted_price = predictions[-1]
        
        if pd.isna(current_price) or pd.isna(predicted_price):
            return None, "INVALID DATA", 0
        
        change_pct = ((predicted_price - current_price) / current_price) * 100
        
        if change_pct > 3:
            trend = "STRONG BUY"
        elif change_pct > 1:
            trend = "BUY"
        elif change_pct < -3:
            trend = "STRONG SELL"
        elif change_pct < -1:
            trend = "SELL"
        else:
            trend = "HOLD"
        
        return predictions, trend, change_pct
    except Exception as e:
        st.error(f"Prediction error: {e}")
        return None, "ERROR", 0

def generate_signals(df):
    """Generate trading signals"""
    signals = []
    
    try:
        last_row = df.iloc[-1]
        
        # RSI Signal
        if not pd.isna(last_row['RSI']):
            if last_row['RSI'] < 30:
                signals.append({"type": "BUY", "indicator": "RSI", "value": f"{last_row['RSI']:.1f}", "strength": "Strong"})
            elif last_row['RSI'] > 70:
                signals.append({"type": "SELL", "indicator": "RSI", "value": f"{last_row['RSI']:.1f}", "strength": "Strong"})
        
        # MACD Signal
        if not pd.isna(last_row['MACD']) and not pd.isna(last_row['Signal']):
            if last_row['MACD'] > last_row['Signal']:
                signals.append({"type": "BUY", "indicator": "MACD", "value": "Bullish", "strength": "Medium"})
            else:
                signals.append({"type": "SELL", "indicator": "MACD", "value": "Bearish", "strength": "Medium"})
        
        # SMA Signal
        if not pd.isna(last_row['Close']) and not pd.isna(last_row['SMA20']):
            if last_row['Close'] > last_row['SMA20']:
                signals.append({"type": "BUY", "indicator": "SMA20", "value": "Above", "strength": "Medium"})
            else:
                signals.append({"type": "SELL", "indicator": "SMA20", "value": "Below", "strength": "Medium"})
        
        # Bollinger Bands
        if not pd.isna(last_row['BB_lower']) and not pd.isna(last_row['BB_upper']):
            if last_row['Close'] < last_row['BB_lower']:
                signals.append({"type": "BUY", "indicator": "Bollinger", "value": "Lower Band", "strength": "Strong"})
            elif last_row['Close'] > last_row['BB_upper']:
                signals.append({"type": "SELL", "indicator": "Bollinger", "value": "Upper Band", "strength": "Strong"})
        
    except Exception as e:
        st.error(f"Signal generation error: {e}")
    
    return signals

def create_professional_chart(df, predictions, symbol):
    """Create professional trading chart"""
    try:
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.5, 0.3, 0.2],
            subplot_titles=(f'{symbol} Price Analysis', 'Volume', 'RSI')
        )
        
        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name='Price',
                increasing_line_color='#48bb78',
                decreasing_line_color='#f56565'
            ),
            row=1, col=1
        )
        
        # SMA
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA20'], name='SMA 20', line=dict(color='#4299e1', width=1)),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA50'], name='SMA 50', line=dict(color='#ed8936', width=1)),
            row=1, col=1
        )
        
        # Predictions
        if predictions is not None:
            future_dates = pd.date_range(start=df.index[-1], periods=len(predictions)+1)[1:]
            fig.add_trace(
                go.Scatter(
                    x=future_dates, y=predictions,
                    name='Prediction',
                    line=dict(color='#9f7aea', width=2, dash='dash')
                ),
                row=1, col=1
            )
        
        # Volume
        colors = ['#48bb78' if df['Close'].iloc[i] >= df['Open'].iloc[i] else '#f56565' for i in range(len(df))]
        fig.add_trace(
            go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=colors),
            row=2, col=1
        )
        
        # RSI
        fig.add_trace(
            go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='#e53e3e', width=2)),
            row=3, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
        
        fig.update_layout(
            height=900,
            template='plotly_dark',
            showlegend=True,
            xaxis_rangeslider_visible=False,
            plot_bgcolor='#0d1b2a',
            paper_bgcolor='#0d1b2a',
            font=dict(color='#ffffff', size=12)
        )
        
        return fig
    except Exception as e:
        st.error(f"Chart creation error: {e}")
        return None

# ==========================================
# VOICE FUNCTION
# ==========================================
async def generate_voice(text):
    """Generate voice from text"""
    try:
        clean_text = text.replace("*", "").replace("#", "").replace("_", "")
        communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural")
        await communicate.save("temp_voice.mp3")
        return True
    except Exception as e:
        st.error(f"Voice generation error: {e}")
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
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("💬 Chat AI", use_container_width=True, key="nav_chat"):
        st.session_state.page = "chat"
        st.rerun()
with col2:
    if st.button("📈 Trading Pro", use_container_width=True, key="nav_trade"):
        st.session_state.page = "trading"
        st.rerun()
with col3:
    if st.button("📸 Vision AI", use_container_width=True, key="nav_foto"):
        st.session_state.page = "foto"
        st.rerun()
with col4:
    if st.button("🗑️ Clear Data", use_container_width=True, key="nav_clear"):
        clear_db()
        st.session_state.messages = []
        st.session_state.uploaded_img = None
        st.rerun()

st.markdown("---")

# ==========================================
# PAGE: CHAT
# ==========================================
if st.session_state.page == "chat":
    st.title("💬 Chat dengan Djamantara AI")
    st.markdown("Asisten AI profesional untuk trading & analisis")
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Tanya tentang trading, saham, crypto, atau upload foto untuk analisa..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_chat("user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Menganalisis..."):
                try:
                    # Check if trading related
                    trading_keywords = ['saham', 'bitcoin', 'btc', 'crypto', 'eth', 'trading', 'harga', 'price', 'analisa']
                    is_trading = any(keyword in prompt.lower() for keyword in trading_keywords)
                    
                    if is_trading:
                        response = "💡 **Trading Analysis:** Untuk analisis trading profesional dengan chart dan prediksi, silakan klik tab **📈 Trading Pro** di atas. Masukkan symbol saham/crypto yang ingin dianalisis."
                    else:
                        completion = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Anda adalah Djamantara AI, asisten trading profesional yang ramah dan informatif. Gunakan bahasa Indonesia yang baik."},
                                {"role": "user", "content": prompt}
                            ],
                            model="llama-3.3-70b-versatile",
                            temperature=0.7
                        )
                        response = completion.choices[0].message.content
                    
                    st.markdown(response)
                    
                    # Voice
                    asyncio.run(generate_voice(response))
                    if os.path.exists("temp_voice.mp3"):
                        with open("temp_voice.mp3", "rb") as f:
                            st.audio(f.read(), format="audio/mpeg")
                    
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    save_chat("assistant", response)
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ==========================================
# PAGE: TRADING
# ==========================================
elif st.session_state.page == "trading":
    st.title("📈 Professional Trading Analysis")
    st.markdown("Analisis teknikal profesional dengan AI-powered prediction")
    
    # Input section
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        symbol = st.text_input("Symbol", "BTC-USD", help="Contoh: BTC-USD, ETH-USD, BBRI.JK, AAPL").upper()
    with col2:
        period = st.selectbox("Periode", ["1wk", "2wk", "1mo", "3mo", "6mo", "1y", "2y"])
    with col3:
        analyze_btn = st.button("🔍 Analisa Sekarang", type="primary", use_container_width=True)
    
    if analyze_btn:
        with st.spinner(f"Mengambil data {symbol}..."):
            df = get_stock_data(symbol, period)
        
        if df is not None and not df.empty and len(df) > 20:
            # Calculate indicators
            df = calculate_indicators(df)
            
            # Predict trend
            predictions, trend, change_pct = predict_trend(df, days=7)
            
            # Generate signals
            signals = generate_signals(df)
            
            # Metrics
            current_price = float(df['Close'].iloc[-1])
            prev_price = float(df['Close'].iloc[-2])
            daily_change = ((current_price - prev_price) / prev_price) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">Harga Saat Ini</div>
                        <div class="metric-value">${current_price:,.2f}</div>
                        <div class="{'metric-change-up' if daily_change >= 0 else 'metric-change-down'}">
                            {daily_change:+.2f}%
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col2:
                pred_price = float(predictions[-1]) if predictions is not None else current_price
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">Prediksi 7 Hari</div>
                        <div class="metric-value">${pred_price:,.2f}</div>
                        <div class="{'metric-change-up' if change_pct >= 0 else 'metric-change-down'}">
                            {change_pct:+.2f}%
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col3:
                signal_class = "signal-buy" if "BUY" in trend else "signal-sell" if "SELL" in trend else "signal-hold"
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">Trend Signal</div>
                        <div style="margin-top: 10px;">
                            <span class="{signal_class}">{trend}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            
            with col4:
                rsi = float(df['RSI'].iloc[-1]) if not pd.isna(df['RSI'].iloc[-1]) else 50
                rsi_status = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral"
                st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">RSI (14)</div>
                        <div class="metric-value">{rsi:.1f}</div>
                        <div style="color: #a0aec0; font-size: 0.875rem;">{rsi_status}</div>
                    </div>
                """, unsafe_allow_html=True)
            
            # Chart
            st.markdown("### 📊 Technical Chart")
            fig = create_professional_chart(df, predictions, symbol)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            
            # Trading Signals
            st.markdown("### 🎯 Trading Signals")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Technical Indicators:**")
                for signal in signals:
                    icon = "✅" if signal["type"] == "BUY" else "⚠️"
                    st.markdown(f"{icon} **{signal['indicator']}**: {signal['value']} ({signal['strength']})")
            
            with col2:
                st.markdown("**Recommendation:**")
                buy_count = sum(1 for s in signals if s["type"] == "BUY")
                sell_count = sum(1 for s in signals if s["type"] == "SELL")
                
                if buy_count > sell_count + 1:
                    st.success("✅ **STRONG BUY** - Multiple buy signals detected")
                elif buy_count > sell_count:
                    st.success("✅ **BUY** - More buy signals")
                elif sell_count > buy_count + 1:
                    st.error("❌ **STRONG SELL** - Multiple sell signals detected")
                elif sell_count > buy_count:
                    st.error("❌ **SELL** - More sell signals")
                else:
                    st.warning("⚠️ **HOLD** - Neutral signals, wait for confirmation")
            
            # AI Analysis
            st.markdown("### 🤖 AI-Powered Analysis")
            with st.spinner("Generating AI analysis..."):
                try:
                    analysis_prompt = f"""
                    Professional trading analysis for {symbol}:
                    - Current Price: ${current_price:,.2f} ({daily_change:+.2f}%)
                    - 7-Day Prediction: ${pred_price:,.2f} ({change_pct:+.2f}%)
                    - Trend: {trend}
                    - RSI: {rsi:.1f} ({rsi_status})
                    - Signals: {buy_count} Buy, {sell_count} Sell
                    
                    Provide concise, actionable trading advice in Indonesian.
                    """
                    
                    completion = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "You are a professional trading analyst. Provide clear, actionable advice."},
                            {"role": "user", "content": analysis_prompt}
                        ],
                        model="llama-3.3-70b-versatile",
                        temperature=0.7
                    )
                    
                    st.markdown(completion.choices[0].message.content)
                    
                except Exception as e:
                    st.error(f"AI analysis error: {e}")
        
        elif df is not None and len(df) <= 20:
            st.error("❌ Insufficient data. Please select a longer time period.")
        else:
            st.error("❌ Symbol not found or no data available. Check the symbol and try again.")

# ==========================================
# PAGE: FOTO
# ==========================================
elif st.session_state.page == "foto":
    st.title("📸 Vision AI - Image Analysis")
    st.markdown("Upload foto untuk dianalisis oleh AI")
    
    uploaded_file = st.file_uploader("Pilih gambar (JPG, PNG)", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        st.session_state.uploaded_img = uploaded_file
        
        # Preview
        col1, col2 = st.columns([3, 1])
        with col1:
            st.image(uploaded_file, caption="Preview", use_container_width=True)
        with col2:
            st.markdown("### Options")
            if st.button("🔍 Analisa Gambar", type="primary", use_container_width=True):
                with st.spinner("Menganalisis gambar..."):
                    try:
                        # Process image
                        img = Image.open(uploaded_file)
                        
                        # Resize if too large
                        if img.size[0] > 1024:
                            ratio = 1024 / img.size[0]
                            new_size = (1024, int(img.size[1] * ratio))
                            img = img.resize(new_size, Image.Resampling.LANCZOS)
                        
                        # Convert to base64
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG", quality=85)
                        img_base64 = base64.b64encode(buffered.getvalue()).decode()
                        
                        # AI Analysis
                        response = client.chat.completions.create(
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "Analisis gambar ini secara detail dan profesional dalam bahasa Indonesia. Jelaskan objek, konteks, dan informasi penting yang terlihat."},
                                        {"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{img_base64}"}}
                                    ]
                                }
                            ],
                            model="llama-3.2-90b-vision-preview"
                        )
                        
                        st.markdown("### Hasil Analisis:")
                        st.markdown(response.choices[0].message.content)
                        
                        # Voice
                        asyncio.run(generate_voice(response.choices[0].message.content))
                        if os.path.exists("temp_voice.mp3"):
                            with open("temp_voice.mp3", "rb") as f:
                                st.audio(f.read(), format="audio/mpeg")
                        
                    except Exception as e:
                        st.error(f"Analysis error: {e}")
            
            if st.button("🗑️ Hapus Gambar", use_container_width=True):
                st.session_state.uploaded_img = None
                st.rerun()
    else:
        st.info("📤 Upload gambar untuk memulai analisis")

# Cleanup
if os.path.exists("temp_voice.mp3"):
    try:
        os.remove("temp_voice.mp3")
    except:
        pass