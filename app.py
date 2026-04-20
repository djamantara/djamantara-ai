import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
from groq import Groq

# --- KONFIGURASI API ---
# Disarankan pakai st.secrets jika dideploy ke internet agar aman
GROQ_API_KEY = "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"

# --- SETTING LAYAR MOBILE ---
st.set_page_config(
    page_title="Djamantara AI", 
    page_icon="🐱", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS INJECTION ---
st.markdown("""
    <style>
    .main .block-container { padding: 2rem 1rem 5rem 1rem; }
    .cat-container img { max-width: 100px; height: auto; border-radius: 50%; }
    .moto-text { font-size: 0.85rem !important; color: #888; font-style: italic; text-align: center; }
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    .stChatInputContainer { padding-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# Klien API
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Waduh Bos, Groq-nya bermasalah: {e}")

# --- 1. SISTEM INGATAN (SQLITE) ---
def init_db():
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn

conn = init_db()

def save_chat(role, content):
    try:
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
    except: pass

def load_chat():
    try:
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        return [{"role": r, "content": c} for r, c in c.fetchall()]
    except: return []

# --- 2. FUNGSI PENDUKUNG ---
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

async def generate_voice(text):
    # Bersihkan teks dari markdown agar suara tts tidak aneh
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

def autoplay_audio(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data_b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{data_b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

# --- 3. TAMPILAN UTAMA ---
gif_base64 = get_local_gif("kucing.gif")
if gif_base64:
    st.markdown(f"""
        <div style="text-align: center; margin-top: -20px;" class="cat-container">
            <img src="data:image/gif;base64,{gif_base64}">
            <h2 style="margin-bottom:0;">🤖 Djamantara AI</h2>
            <p class="moto-text">"Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Oréng od i' jhâ' alako jhubâ'. Lebbi bhagus nyaré élmo."</p>
        </div>
    """, unsafe_allow_html=True)

# Sidebar untuk upload foto
with st.sidebar:
    st.header("👁️ Mata Kocheng")
    up_file = st.file_uploader("Kirim foto...", type=["jpg", "png", "jpeg"])
    if up_file:
        st.image(up_file, caption="Foto Siap!", use_container_width=True)
    
    if st.button("Hapus Ingatan"):
        conn.cursor().execute("DELETE FROM chat_history")
        conn.commit()
        st.session_state.messages = []
        st.rerun()

# State management
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. LOGIKA CHAT ---
if prompt := st.chat_input("Ngobrol moso Djamantara, Bos..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi mikir..."):
            try:
                # Jika ada gambar, gunakan model Vision
                if up_file:
                    b64_img = encode_image(up_file)
                    resp = client.chat.completions.create(
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura sedikit. Panggil 'Bos'. Analisa ini: {prompt}"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                            ]
                        }],
                        model="llama-3.2-11b-vision-preview", # Model Vision yang benar
                    )
                else:
                    # Chat teks biasa
                    msgs = [{"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Gunakan bahasa santai Indonesia-Madura."}]
                    msgs.extend(st.session_state.messages[-6:]) # Ambil konteks terakhir
                    resp = client.chat.completions.create(
                        messages=msgs,
                        model="llama-3.3-70b-versatile",
                    )
                
                full_resp = resp.choices[0].message.content
                
                # Animasi ngetik
                ph = st.empty()
                txt = ""
                for char in full_resp:
                    txt += char
                    ph.markdown(txt + "▌")
                    time.sleep(0.005)
                ph.markdown(full_resp)

                # Suara
                asyncio.run(generate_voice(full_resp))
                autoplay_audio("temp_voice.mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": full_resp})
                save_chat("assistant", full_resp)
                
            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {str(e)}")
