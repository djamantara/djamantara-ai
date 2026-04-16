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
import logging

# ==========================================
# --- KONFIGURASI & LOGGING ---
# ==========================================
logging.basicConfig(filename='djamantara_error.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# ⚠️ Gunakan st.secrets di deployment. Hardcode hanya untuk dev lokal.
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
if not GROQ_API_KEY:
    st.error("🔑 API Key Groq tidak ditemukan! Masukkan di `st.secrets` atau env `GROQ_API_KEY`.")
    st.stop()

st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="centered")

# ==========================================
# 🎨 CSS CUSTOM - GEMINI STYLE
# ==========================================
st.markdown("""
    <style>
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; display: none !important;
    }
    .header-box { text-align: center; padding: 1rem; }
    .header-box img { max-width: 100px; border-radius: 50%; border: 2px solid #00d9ff; }
    div[data-testid="stExpander"] { border: none !important; background: transparent !important; }
    .preview-container {
        position: fixed; bottom: 100px; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: #1e1e1e; padding: 10px; border-radius: 15px;
        border: 1px solid #00d9ff; display: flex; align-items: center; gap: 10px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.5);
    }
    .moto-text { font-size: 0.8rem; color: #888; font-style: italic; }
    .stChatInput { border: 1px solid #00d9ff; border-radius: 20px; padding: 8px; }
    </style>
""", unsafe_allow_html=True)

client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# --- DATABASE & LOGIC ---
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
    clean_text = text.replace("*", "").replace("#", "").replace("_", "").strip()
    if not clean_text: return
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz")
    await communicate.save("temp_voice.mp3")

def play_audio():
    if os.path.exists("temp_voice.mp3"):
        with open("temp_voice.mp3", "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
        try: os.remove("temp_voice.mp3")
        except: pass

# ==========================================
# --- UI RENDER ---
# ==========================================
# Header
gif_b64 = ""
if os.path.exists("kucing.gif"):
    with open("kucing.gif", "rb") as f:
        gif_b64 = base64.b64encode(f.read()).decode()

st.markdown('<div class="header-box">', unsafe_allow_html=True)
if gif_b64:
    st.markdown(f'<img src="data:image/gif;base64,{gif_b64}">', unsafe_allow_html=True)
st.markdown('<h1>Djamantara AI</h1><p class="moto-text">"Nyari ilmu dulu baru nyari kamu, Bos."</p></div>', unsafe_allow_html=True)

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "image_data" not in st.session_state:
    st.session_state.image_data = None

# Upload Popover
cols = st.columns([1, 1, 1])
with cols[1]:
    with st.popover("📎 Lampirkan Foto"):
        up = st.file_uploader("Pilih gambar", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
        if up:
            try:
                img = Image.open(up)
                if img.mode != 'RGB': img = img.convert('RGB')
                img.thumbnail((800, 800))
                buf = io.BytesIO()
                img.save(buf, format='JPEG')
                st.session_state.image_data = buf.getvalue()
                st.toast("✅ Foto terlampir!", icon="🖼️")
            except Exception as e:
                st.error(f"❌ Gambar tidak valid: {e}")
        if st.button("🗑️ Reset Semua", key="btn_reset"):
            st.session_state.image_data = None
            st.session_state.messages = []
            st.rerun()

# Preview Gambar
if st.session_state.image_data:
    st.markdown('<div class="preview-container">', unsafe_allow_html=True)
    st.image(st.session_state.image_data, width=80)
    if st.button("❌", key="remove_img"):
        st.session_state.image_data = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Tampilkan Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Debug Sidebar (Opsional tapi sangat membantu)
with st.sidebar:
    st.subheader("🔧 Debug Info")
    if st.session_state.image_data:
        st.write(f"✅ Gambar: {len(st.session_state.image_data)} bytes")
    else:
        st.write("📭 Tidak ada gambar")
    if st.button("🗑️ Clear Cache & Reset", key="cache_clear"):
        st.cache_data.clear()
        st.session_state.image_data = None
        st.session_state.messages = []
        st.rerun()

# ==========================================
# --- CORE CHAT LOGIC ---
# ==========================================
if prompt := st.chat_input("Tanya apa hari ini, Bos?"):
    prompt = prompt.strip()
    if not prompt:
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🧠 Sedang berpikir..."):
            try:
                # Siapkan payload teks
                user_content = [{"type": "text", "text": prompt}]
                use_vision = False

                # Validasi & Siapkan Gambar
                if st.session_state.image_
                    try:
                        # Cek apakah file gambar utuh
                        img_test = Image.open(io.BytesIO(st.session_state.image_data))
                        img_test.load()
                        
                        b64_img = base64.b64encode(st.session_state.image_data).decode()
                        user_content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                        })
                        use_vision = True
                    except Exception as img_err:
                        st.warning(f"⚠️ Gambar korup/tidak didukung. Lanjut mode teks.")
                        st.session_state.image_data = None

                # Panggil API Groq
                model = "llama-3.2-11b-vision-preview" if use_vision else "llama-3.1-8b-instant"
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": user_content}],
                    temperature=0.7,
                    max_tokens=1024,
                    timeout=30
                )
                ai_reply = response.choices[0].message.content

                # Tampilkan & Simpan
                st.markdown(ai_reply)
                st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                save_chat("user", prompt)
                save_chat("assistant", ai_reply)

                # TTS
                asyncio.run(text_to_speech(ai_reply))
                play_audio()

                # Bersihkan gambar setelah sukses
                if st.session_state.image_
                    st.session_state.image_data = None

            # ── FALLBACK & ERROR HANDLING ──
            except Exception as e:
                error_str = str(e).lower()
                logging.error(f"API Error: {e}")

                # Fallback ke model teks jika vision gagal
                if use_vision and ("vision" in error_str or "image" in error_str or "400" in error_str):
                    st.warning("🔄 Gagal analisis gambar. Mencoba mode teks saja...")
                    try:
                        fallback_res = client.chat.completions.create(
                            model="llama-3.1-8b-instant",
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.7, max_tokens=1024, timeout=20
                        )
                        ai_reply = f"⚠️ *Mode fallback (teks)*: {fallback_res.choices[0].message.content}"
                        st.markdown(ai_reply)
                        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                        save_chat("user", prompt)
                        save_chat("assistant", ai_reply)
                        asyncio.run(text_to_speech(ai_reply))
                        play_audio()
                        st.session_state.image_data = None
                        st.stop()
                    except Exception as e2:
                        logging.error(f"Fallback Error: {e2}")
                        st.error(f"❌ Fallback juga gagal: {e2}")

                # Error umum
                elif "rate limit" in error_str or "429" in error_str:
                    st.error("⏳ Rate limit tercapai. Tunggu ~60 detik lalu coba lagi.")
                elif "api key" in error_str or "401" in error_str or "403" in error_str:
                    st.error("🔑 API Key tidak valid atau kuota habis. Cek dashboard Groq.")
                elif "timeout" in error_str or "connection" in error_str:
                    st.error("🌐 Koneksi timeout. Periksa internet Anda.")
                else:
                    st.error(f"❌ Terjadi kesalahan: {e}")

                # Log error ke chat history
                err_msg = f"⚠️ Sistem error: {e}"
                save_chat("user", prompt)
                save_chat("assistant", err_msg)