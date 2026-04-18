import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
import threading
from groq import Groq

# --- KONFIGURASI API ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

st.set_page_config(
    page_title="Djamantara AI",
    page_icon="🐱",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS MINIMAL & RESPONSIF ---
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; padding-bottom: 4rem; }
    .moto-text { font-size: 0.9rem; color: gray; font-style: italic; line-height: 1.4; }
    footer, #MainMenu { visibility: hidden; }
    .stChatInputContainer { padding-bottom: 15px; }
    @media (max-width: 600px) { h1 { font-size: 1.6rem !important; } }
</style>
""", unsafe_allow_html=True)

# --- INISIALISASI GROQ ---
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Waduh Bos, Groq bermasalah: {e}")
    st.stop()

# ==========================================
# 1. DATABASE (INGATAN)
# ==========================================
def init_db():
    conn = sqlite3.connect("djamantara_memory.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                    (id INTEGER PRIMARY KEY, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    conn = sqlite3.connect("djamantara_memory.db")    conn.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
    conn.commit()
    conn.close()

def load_chat(limit=50):
    conn = sqlite3.connect("djamantara_memory.db")
    cur = conn.cursor()
    cur.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in rows]

init_db()

# ==========================================
# 2. MEDIA & TTS (RINGAN)
# ==========================================
def get_local_gif(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def encode_image(file_obj):
    file_obj.seek(0)
    mime = file_obj.type or "image/jpeg"
    b64 = base64.b64encode(file_obj.read()).decode()
    return b64, mime

def run_tts_background(text):
    async def _gen():
        clean = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")
        comm = edge_tts.Communicate(clean, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
        await comm.save("temp_voice.mp3")
    threading.Thread(target=lambda: asyncio.run(_gen()), daemon=True).start()

def play_audio(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(f'<audio autoplay playsinline style="display:none"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

# ==========================================
# 3. TAMPILAN UI
# ==========================================
gif_b64 = get_local_gif("kucing.gif")
if gif_b64:
    st.markdown(f"""
    <div style="text-align:center; margin-top:-20px">
        <img src="data:image/gif;base64,{gif_b64}" style="max-width:100px; height:auto">        <h1 style="margin:5px 0">🤖 Djamantara AI</h1>
        <p class="moto-text">"Entar kon obâ'. É tengnga jhâlân pas mu-nemmu."</p>
    </div>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.title("👁️ Mata Kocheng")
    uploaded = st.file_uploader("Kirim foto...", type=["jpg", "jpeg", "png"])
    if uploaded:
        st.session_state.current_image = uploaded
        st.image(uploaded, caption="Foto Siap!", use_container_width=True)
    elif "current_image" in st.session_state:
        st.image(st.session_state.current_image, caption="Foto Siap!", use_container_width=True)

    st.divider()
    if st.button("🗑️ Hapus Ingatan"):
        conn = sqlite3.connect("djamantara_memory.db")
        conn.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        st.session_state.messages = []
        st.session_state.pop("current_image", None)
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = load_chat()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# 4. LOGIKA CHAT
# ==========================================
if prompt := st.chat_input("Ngobrol moso Djamantara, Bos..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi ngintip..."):
            try:
                img = st.session_state.get("current_image")
                
                if img:
                    b64_img, mime = encode_image(img)
                    res = client.chat.completions.create(
                        messages=[{"role": "user", "content": [                            {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, Indonesia-Madura. Panggil 'Bos'. Analisa: {prompt}"},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_img}"}}
                        ]}],
                        model="llama-3.2-90b-vision-preview"
                    )
                else:
                    ctx = st.session_state.messages[-5:]
                    sys_msg = {"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Bahasa santai Indonesia-Madura."}
                    res = client.chat.completions.create(
                        messages=[sys_msg] + ctx,
                        model="llama-3.3-70b-versatile"
                    )
                
                reply = res.choices[0].message.content

                # Efek mengetik ringan
                ph = st.empty()
                txt = ""
                for c in reply:
                    txt += c
                    ph.markdown(txt + "▌")
                    time.sleep(0.01)
                ph.markdown(reply)

                # TTS Background
                if reply.strip():
                    run_tts_background(reply)
                    time.sleep(1.2)
                    play_audio("temp_voice.mp3")

                st.session_state.messages.append({"role": "assistant", "content": reply})
                save_chat("assistant", reply)

            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {e}")