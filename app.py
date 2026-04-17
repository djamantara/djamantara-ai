import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
from groq import Groq

# ==========================================
# --- KONFIGURASI API AMAN (SECRETS) ---
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("⚠️ API Key 'GROQ_API_KEY' tidak ditemukan!")
    st.stop()

client = None
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Waduh Bos, Groq-nya bermasalah: {e}")

# ==========================================
# --- SETTING LAYAR ---
# ==========================================
st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="centered", initial_sidebar_state="collapsed")

# ==========================================
# --- CSS: HIDE BRANDING + UI RAPI + TOMBOL MELENGKET ---
# ==========================================
st.markdown("""
    <style>
    /* HIDE STREAMLIT BRANDING */
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden !important;}
    .stAppDeployButton, [data-testid="stFooter"], .stDeployButton {display: none !important;}
    
    /* LAYOUT & NO BLACK BAR */
    .main .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .cat-container img { max-width: 90px; height: auto; }
    .moto-text { font-size: 0.85rem !important; color: #888; font-style: italic; text-align: center; }
    
    /* CONTROL PANEL (UPLOAD + HAPUS) MELENGKET DI ATAS CHAT */
    .control-panel {
        position: sticky;
        bottom: 0;
        background: var(--background-color);
        padding: 8px 0 12px 0;
        z-index: 10;
        border-top: 1px solid #333;
    }
    .stButton>button { border-radius: 8px; font-weight: bold; }
    .upload-box { background: #1e1e1e; padding: 8px; border-radius: 8px; border: 1px solid #444; }
    
    /* CHAT INPUT */
    .stChatInputContainer { padding-top: 0; }
    
    @media (max-width: 600px) {
        h1 { font-size: 1.6rem !important; }
        .moto-text { font-size: 0.75rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# --- 1. DATABASE ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit(); conn.close()

def save_chat(role, content):
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        conn.cursor().execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit(); conn.close()
    except: pass

def load_chat():
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        history = c.fetchall(); conn.close()
        return [{"role": r, "content": c} for r, c in history]
    except: return []

init_db()

# ==========================================
# --- 2. FUNGSI PENDUKUNG ---
# ==========================================
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

def encode_image(file_obj):
    file_obj.seek(0)
    return base64.b64encode(file_obj.read()).decode('utf-8')

def run_async_safe(coro_func, *args):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import threading
            result = [None]
            def _run():
                new_loop = asyncio.new_event_loop(); asyncio.set_event_loop(new_loop)
                result[0] = new_loop.run_until_complete(coro_func(*args)); new_loop.close()
            threading.Thread(target=_run).start()
            # Wait safely
            while result[0] is None and threading.active_count() > 1: time.sleep(0.05)
            return result[0]
        return loop.run_until_complete(coro_func(*args))
    except:
        new_loop = asyncio.new_event_loop(); asyncio.set_event_loop(new_loop)
        res = new_loop.run_until_complete(coro_func(*args)); new_loop.close()
        return res

async def generate_voice(text):
    clean = text.replace("*","").replace("#","").replace("`","").replace("-"," ")
    comm = edge_tts.Communicate(clean, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await comm.save("temp_voice.mp3")

def autoplay_audio(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

# ==========================================
# --- 3. TAMPILAN UTAMA ---
# ==========================================
gif_data = get_local_gif("kucing.gif")
if gif_
    st.markdown(f"""
        <div style="text-align:center; margin-bottom:10px;" class="cat-container">
            <img src="image/gif;base64,{gif_data}">
            <h1 style="margin:5px 0 0 0;">🤖 Djamantara AI</h1>
            <p class="moto-text">"Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Oréng od i' jhâ' alako jhubâ'. Lebbi bhagus nyaré élmo."</p>
        </div>""", unsafe_allow_html=True)

# Tampilkan Chat History
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# --- PANEL KONTROL (MELENGKET DI ATAS CHAT) ---
# ==========================================
with st.container():
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    
    with col1:
        uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"], label_visibility="collapsed", help="Upload foto untuk dianalisa")
        if uploaded_file:
            st.session_state.current_image = uploaded_file
            st.success("✅ Foto siap dianalisa!", icon="📷")
            st.image(uploaded_file, caption="Preview Foto", use_container_width=True)
        elif "current_image" in st.session_state:
            st.success("✅ Foto tersimpan di memori!", icon="💾")
            st.image(st.session_state.current_image, caption="Preview Foto", use_container_width=True)
            uploaded_file = st.session_state.current_image
            
    with col2:
        if st.button("🗑️ Hapus Chat", use_container_width=True, type="secondary"):
            conn = sqlite3.connect('djamantara_memory.db')
            conn.cursor().execute("DELETE FROM chat_history")
            conn.commit(); conn.close()
            st.session_state.messages = []
            if "current_image" in st.session_state: del st.session_state.current_image
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# --- INPUT CHAT ---
# ==========================================
if prompt := st.chat_input("Ngobrol moso Djamantara, Bos..."):
    if not client:
        st.error("⚠️ API Key belum disetting!"); st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi ngintip..."):
            try:
                # Ambil gambar dari session state (aman saat rerun)
                img_to_use = st.session_state.get("current_image")
                
                if img_to_use:
                    b64_img = encode_image(img_to_use)
                    # ✅ PAKAI MODEL VISION GROQ YANG VALID
                    resp = client.chat.completions.create(
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura. Panggil 'Bos'. Analisa gambar ini: {prompt}"},
                            {"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{b64_img}"}}
                        ]}],
                        model="llama-3.2-11b-vision-preview"
                    )
                    full_response = resp.choices[0].message.content
                else:
                    ctx = st.session_state.messages[-5:]
                    resp = client.chat.completions.create(
                        messages=[{"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Bahasa santai Indonesia-Madura."}, *ctx],
                        model="llama-3.3-70b-versatile"
                    )
                    full_response = resp.choices[0].message.content
                
                # Typing effect
                ph = st.empty(); txt = ""
                for c in full_response:
                    txt += c; ph.markdown(txt + "▌"); time.sleep(0.01)
                ph.markdown(full_response)
                
                run_async_safe(generate_voice, full_response)
                autoplay_audio("temp_voice.mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_chat("assistant", full_response)
                
            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {str(e)}")

# Cleanup
if os.path.exists("temp_voice.mp3"):
    try: time.sleep(3); os.remove("temp_voice.mp3")
    except: pass