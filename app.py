import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
from groq import Groq

# ==========================================
# --- KONFIGURASI API AMAN ---
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("⚠️ API Key belum disetting di Secrets!")
    st.stop()

client = None
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Gagal koneksi ke Groq: {e}")

# ==========================================
# --- PAGE CONFIG ---
# ==========================================
st.set_page_config(
    page_title="Djamantara AI",
    page_icon="🐱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==========================================
# ✅ CSS: HIDE BRANDING + STYLING RAPI (TANPA STICKY BUG)
# ==========================================
st.markdown("""
    <style>
    /* Hide Streamlit UI */
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .stAppDeployButton, [data-testid="stFooter"], .stDeployButton, [data-testid="stToolbar"] {display: none !important;}
    
    /* Layout */
    .main .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 100%; }
    .cat-container img { max-width: 80px; height: auto; margin-bottom: 5px; }
    h1 { text-align: center; margin: 0; font-size: 1.8rem; }
    .moto { text-align: center; color: #888; font-style: italic; font-size: 0.85rem; margin-bottom: 15px; }
    
    /* Control bar styling */
    .control-bar {
        background: rgba(255,255,255,0.05);
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 8px;
    }
    .stFileUploader { margin: 0 !important; padding: 0 !important; }
    .stFileUploader > div { margin: 0 !important; padding: 0 !important; }
    
    /* Mobile */
    @media (max-width: 600px) {
        .control-bar { flex-direction: column; gap: 8px; }
        h1 { font-size: 1.6rem !important; }
        .moto { font-size: 0.75rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# --- DATABASE ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db')
    conn.cursor().execute('''CREATE TABLE IF NOT EXISTS chat_history (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
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
        res = [{"role": r, "content": c} for r, c in c.fetchall()]
        conn.close(); return res
    except: return []

init_db()

# ==========================================
# --- FUNGSI BANTUAN ---
# ==========================================
def get_gif(path):
    if os.path.exists(path):
        with open(path, "rb") as f: return base64.b64encode(f.read()).decode()
    return None

def encode_img(file_obj):
    file_obj.seek(0)
    return base64.b64encode(file_obj.read()).decode()

def run_async(func, *args):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import threading
            res = [None]
            def _run():
                nl = asyncio.new_event_loop(); asyncio.set_event_loop(nl)
                res[0] = nl.run_until_complete(func(*args)); nl.close()
            threading.Thread(target=_run).start()
            while res[0] is None: time.sleep(0.05)
            return res[0]
        return loop.run_until_complete(func(*args))
    except:
        nl = asyncio.new_event_loop(); asyncio.set_event_loop(nl)
        r = nl.run_until_complete(func(*args)); nl.close(); return r

async def gen_voice(text):
    clean = text.replace("*","").replace("#","").replace("`","").replace("-"," ")
    await edge_tts.Communicate(clean, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%").save("temp_voice.mp3")

def play_audio(path):
    if os.path.exists(path):
        with open(path, "rb") as f: b64 = base64.b64encode(f.read()).decode()
        st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

# ==========================================
# --- UI HEADER ---
# ==========================================
gif_data = get_gif("kucing.gif")
if gif_
    st.markdown(f"""
        <div class="cat-container" style="text-align:center;">
            <img src="data:image/gif;base64,{gif_data}">
            <h1>🤖 Djamantara AI</h1>
            <p class="moto">"Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Oréng od i' jhâ' alako jhubâ'. Lebbi bhagus nyaré élmo."</p>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# --- CHAT HISTORY ---
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# --- CONTROL BAR (UPLOAD + HAPUS) ---
# ==========================================
with st.container():
    st.markdown('<div class="control-bar">', unsafe_allow_html=True)
    c1, c2 = st.columns([4, 1])
    with c1:
        uploaded_file = st.file_uploader("", type=["jpg","jpeg","png"], label_visibility="collapsed", help="Upload foto untuk dianalisa", key="upload_img")
        if uploaded_file:
            st.session_state.current_image = uploaded_file
            st.success("✅ Foto siap dianalisa!", icon="📷")
            st.image(uploaded_file, caption="Preview", use_container_width=True)
        elif "current_image" in st.session_state:
            st.success("✅ Foto tersimpan di memori!", icon="💾")
            st.image(st.session_state.current_image, caption="Preview", use_container_width=True)
            uploaded_file = st.session_state.current_image
    with c2:
        if st.button("🗑️ Hapus", use_container_width=True, type="secondary", key="btn_delete"):
            conn = sqlite3.connect('djamantara_memory.db')
            conn.cursor().execute("DELETE FROM chat_history"); conn.commit(); conn.close()
            st.session_state.messages = []
            if "current_image" in st.session_state: del st.session_state.current_image
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# --- CHAT INPUT (NATIVE STREAMLIT) ---
# ==========================================
prompt = st.chat_input("Ngobrol moso Djamantara, Bos...", key="chat_input")

# ==========================================
# --- CHAT LOGIC ---
# ==========================================
if prompt:
    if not client: st.error("⚠️ API Key error!"); st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi ngintip..."):
            try:
                img = st.session_state.get("current_image")
                
                if img:
                    b64 = encode_img(img)
                    resp = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{"role": "user", "content": [
                            {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura. Panggil 'Bos'. Analisa gambar ini: {prompt}"},
                            {"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{b64}"}}
                        ]}],
                        temperature=0.7,
                        max_completion_tokens=1024
                    )
                    full = resp.choices[0].message.content
                else:
                    ctx = st.session_state.messages[-5:]
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Bahasa santai Indonesia-Madura."}, *ctx]
                    )
                    full = resp.choices[0].message.content
                
                ph = st.empty(); txt = ""
                for c in full:
                    txt += c; ph.markdown(txt + "▌"); time.sleep(0.01)
                ph.markdown(full)
                
                run_async(gen_voice, full)
                play_audio("temp_voice.mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": full})
                save_chat("assistant", full)
            except Exception as e:
                st.error(f"⚠️ Error: {str(e)}")

# ==========================================
# ✅ AUTO-SCROLL KE BAWAH (FIX)
# ==========================================
st.markdown("""
    <script>
        setTimeout(function() {
            window.scrollTo(0, document.body.scrollHeight);
        }, 200);
    </script>
    """, unsafe_allow_html=True)

# ==========================================
# --- CLEANUP ---
# ==========================================
if os.path.exists("temp_voice.mp3"):
    try: time.sleep(3); os.remove("temp_voice.mp3")
    except: pass