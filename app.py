import streamlit as st
import edge_tts
import asyncio
import base64
import os
import sqlite3
import io
import logging
from groq import Groq
from PIL import Image
import nest_asyncio

# Fix asyncio event loop di Streamlit
nest_asyncio.apply()

# ==========================================
# 📌 KONFIGURASI & LOGGING
# ==========================================
logging.basicConfig(
    filename='djamantara_debug.log', 
    level=logging.ERROR, 
    format='%(asctime)s | %(levelname)s | %(message)s'
)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
if not GROQ_API_KEY:
    st.error("🔑 API Key Groq tidak ditemukan. Masukkan di `st.secrets` atau env `GROQ_API_KEY`.")
    st.stop()

st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="wide")

# ==========================================
# 🎨 CSS MODERN UI
# ==========================================
st.markdown("""
<style>
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; display: none !important;
    }
    
    /* Chat Bubble Styling */
    .chat-container { display: flex; flex-direction: column; gap: 1rem; padding: 1rem 0; }
    .message { display: flex; align-items: flex-start; gap: 0.75rem; max-width: 85%; }
    .message.user { flex-direction: row-reverse; margin-left: auto; }
    .message.assistant { margin-right: auto; }
    
    .bubble {
        padding: 12px 16px; border-radius: 18px; font-size: 0.95rem; line-height: 1.5;
        word-wrap: break-word; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    .message.user .bubble { background: #0078ff; color: white; border-top-right-radius: 4px; }
    .message.assistant .bubble { background: #f3f4f6; color: #111; border-top-left-radius: 4px; }
    
    /* Avatar */
    .avatar { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
    
    /* Input Area */
    .input-box {
        display: flex; align-items: center; gap: 0.5rem; background: #fff;
        border: 1px solid #ddd; border-radius: 30px; padding: 6px 12px;
        transition: border 0.2s;
    }
    .input-box:focus-within { border-color: #0078ff; box-shadow: 0 0 0 3px rgba(0,120,255,0.15); }
    
    /* Image Preview */
    .img-preview {
        background: #111; border-radius: 12px; padding: 4px; display: inline-flex;
        align-items: center; gap: 6px; margin-top: 6px; border: 1px solid #0078ff;
    }
    .img-preview img { width: 48px; height: 48px; object-fit: cover; border-radius: 8px; }
    .img-preview button { background: none; border: none; color: #fff; font-size: 1rem; cursor: pointer; }
    
    /* Misc */
    .send-btn { background: #0078ff; color: white; border: none; border-radius: 50%; width: 36px; height: 36px; font-size: 1.1rem; cursor: pointer; }
    .send-btn:disabled { background: #ccc; cursor: not-allowed; }
    .empty-state { text-align: center; color: #888; padding: 3rem 1rem; }
    .tts-btn { background: none; border: none; cursor: pointer; font-size: 0.8rem; margin-left: auto; }
</style>
""", unsafe_allow_html=True)

client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# 🗄️ DATABASE & CORE LOGIC
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.close()

def save_chat(role, content):
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    conn.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
    conn.commit()
    conn.close()

init_db()

async def text_to_speech(text):
    clean = text.replace("*", "").replace("#", "").replace("_", "").strip()
    if not clean: return None
    communicate = edge_tts.Communicate(clean, "id-ID-ArdiNeural", pitch="-5Hz")
    await communicate.save("temp_voice.mp3")
    return "temp_voice.mp3"

def play_audio(path):
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            st.audio(f.read(), format="audio/mp3", autoplay=True)
        try: os.remove(path)
        except: pass

# ==========================================
# 🖼️ UI RENDER
# ==========================================
# Header
gif_b64 = ""
if os.path.exists("kucing.gif"):
    with open("kucing.gif", "rb") as f: gif_b64 = base64.b64encode(f.read()).decode()

st.markdown(f'''
<div style="text-align:center; padding: 1rem 0;">
    {f'<img src="data:image/gif;base64,{gif_b64}" width="80" style="border-radius:50%; border:2px solid #0078ff;">' if gif_b64 else ''}
    <h2 style="margin:0.2rem 0 0;">Djamantara AI</h2>
    <p style="margin:0; color:#666; font-size:0.85rem; font-style:italic;">"Nyari ilmu dulu baru nyari kamu, Bos."</p>
</div>
''', unsafe_allow_html=True)

# Session State
if "messages" not in st.session_state: st.session_state.messages = []
if "image_data" not in st.session_state: st.session_state.image_data = None
if "generating" not in st.session_state: st.session_state.generating = False

# Main Layout
col1, col2, col3 = st.columns([2, 10, 2])
with col2:
    # Chat Display
    chat_box = st.container()
    with chat_box:
        if not st.session_state.messages:
            st.markdown('<div class="empty-state">🐱 Hai Bos! Mau tanya apa hari ini?<br><small style="color:#aaa;">Upload gambar untuk analisis, atau ketik langsung.</small></div>', unsafe_allow_html=True)
        
        for idx, msg in enumerate(st.session_state.messages):
            is_user = msg["role"] == "user"
            avatar_url = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzNiIgaGVpZ2h0PSIzNiIgdmlld0JveD0iMCAwIDM2IDM2Ij48Y2lyY2xlIGN4PSIxOCIgY3k9IjE4IiByPSIxOCIgZmlsbD0iI2ZmZiIvPjx0ZXh0IHg9IjE4IiB5PSIyNCIgZm9udC1zaXplPSIxNiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSI+772vPC90ZXh0Pjwvc3ZnPg==" if not is_user else "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIzNiIgaGVpZ2h0PSIzNiIgdmlld0JveD0iMCAwIDM2IDM2Ij48Y2lyY2xlIGN4PSIxOCIgY3k9IjE4IiByPSIxOCIgZmlsbD0iIzAwNzhmZiIvPjx0ZXh0IHg9IjE4IiB5PSIyNCIgZm9udC1zaXplPSIxNiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZG9taW5hbnQtYmFzZWxpbmU9Im1pZGRsZSIgZmlsbD0id2hpdGUiPjwvdGV4dD48L3N2Zz4="
            
            st.markdown(f'''
            <div class="message {'user' if is_user else 'assistant'}">
                <img src="{avatar_url}" class="avatar">
                <div class="bubble">
                    <div>{msg["content"]}</div>
                    {'<button class="tts-btn" onclick="document.getElementById(\'tts_'+str(idx)+'\').play()">🔊 Suara</button>' if not is_user and 'TTS' in msg else ''}
                </div>
            </div>
            ''', unsafe_allow_html=True)
            if not is_user and 'TTS' in msg:
                st.empty() # Placeholder for TTS audio

    # Input Area
    with st.form("chat_input", border=False):
        inp_col1, inp_col2 = st.columns([6, 1])
        with inp_col1:
            user_text = st.text_input("Ketik pesan...", key="input_text", label_visibility="collapsed", placeholder="Tanya apa saja...")
            if st.session_state.image_data:
                st.markdown('<div class="img-preview">', unsafe_allow_html=True)
                st.image(st.session_state.image_data, width=50)
                if st.button("✖️", key="remove_img_btn"):
                    st.session_state.image_data = None
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        with inp_col2:
            send_btn = st.form_submit_button("🚀", use_container_width=True, type="primary")

# ==========================================
# 🧠 PROSES CHAT
# ==========================================
if send_btn and user_text.strip() and not st.session_state.generating:
    prompt = user_text.strip()
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.rerun()

# Render pesan user & jalankan AI
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    current_msg = st.session_state.messages[-1]
    with st.chat_message("assistant"):
        with st.spinner("🧠 Menganalisis..."):
            try:
                st.session_state.generating = True
                
                # Siapkan payload
                user_content = [{"type": "text", "text": current_msg["content"]}]
                use_vision = False
                
                if st.session_state.image_
                    try:
                        Image.open(io.BytesIO(st.session_state.image_data)).load()
                        b64_img = base64.b64encode(st.session_state.image_data).decode()
                        user_content.append({"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{b64_img}"}})
                        use_vision = True
                    except Exception as img_err:
                        st.session_state.image_data = None
                        st.session_state.messages[-1]["content"] += f"\n⚠️ *Gambar tidak valid. Mode teks aktif.*"
                        st.rerun()

                # Panggil API
                model = "llama-3.2-11b-vision-preview" if use_vision else "llama-3.1-8b-instant"
                res = client.chat.completions.create(
                    model=model, messages=[{"role": "user", "content": user_content}],
                    temperature=0.7, max_tokens=1024, timeout=30
                )
                ai_text = res.choices[0].message.content
                
                # Simpan & Tampilkan
                st.session_state.messages.append({"role": "assistant", "content": ai_text, "TTS": True})
                save_chat("user", current_msg["content"])
                save_chat("assistant", ai_text)
                
                # TTS & Rerun untuk render UI baru
                asyncio.run(text_to_speech(ai_text))
                play_audio("temp_voice.mp3")
                st.session_state.generating = False
                st.rerun()

            except Exception as e:
                err_str = str(e).lower()
                logging.error(f"AI Error: {e}")
                st.session_state.generating = False
                
                if use_vision and any(k in err_str for k in ["vision", "image", "400"]):
                    st.session_state.messages[-1]["content"] += "\n🔄 *Fallback ke mode teks saja...*"
                    st.rerun()
                elif "rate limit" in err_str or "429" in err_str:
                    st.session_state.messages.append({"role": "assistant", "content": "⏳ *Rate limit tercapai. Tunggu ~60 detik lalu coba lagi.*"})
                elif "api key" in err_str or any(c in err_str for c in ["401", "403"]):
                    st.session_state.messages.append({"role": "assistant", "content": "🔑 *API Key tidak valid atau kuota habis.*"})
                else:
                    st.session_state.messages.append({"role": "assistant", "content": f"❌ *Error sistem: {e}*"})
                
                save_chat("user", current_msg["content"])
                save_chat("assistant", st.session_state.messages[-1]["content"])
                st.rerun()