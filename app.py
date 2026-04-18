import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
from groq import Groq

# --- KONFIGURASI API ---
GROQ_API_KEY = "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"

st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="centered")

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ API Groq error: {e}")
    st.stop()

# ==========================================
# 1. LOAD GIF & CSS LAYOUT (RAPAT & TENGAH)
# ==========================================
def get_gif_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

gif_b64 = get_gif_base64("kucing.gif")

st.markdown("""
<style>
    /* 1. HILANGKAN MENU STREAMLIT (POJOK KANAN ATAS & FOOTER) */
    header, #MainMenu, footer { display: none !important; visibility: hidden !important; }
    .main .block-container { padding-top: 1rem; padding-bottom: 2rem; }

    /* 2. CENTERING PASTI & JARAK RAPAT */
    .header-box { 
        display: flex; 
        flex-direction: column; 
        align-items: center; 
        justify-content: center; 
        width: 100%; 
        margin: 0; 
        padding: 0; 
    }
    .cat-gif { width: 110px; height: auto; margin-bottom: 1px; }
    .app-title { font-size: 1.6rem; font-weight: bold; margin: 0; padding: 0; line-height: 1.1; }
    .app-subtitle { color: gray; font-style: italic; margin-top: 3px; font-size: 0.85rem; }
</style>""", unsafe_allow_html=True)

st.markdown('<div class="header-box">', unsafe_allow_html=True)
if gif_b64:
    st.markdown(f'<img src="data:image/gif;base64,{gif_b64}" class="cat-gif">', unsafe_allow_html=True)
st.markdown('<h1 class="app-title">🤖 Djamantara AI</h1>', unsafe_allow_html=True)
st.markdown('<p class="app-subtitle">Halo Bos! Ngobrol santai aja.</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 2. FUNGSI AUTO-PLAY VOICE (TTS)
# ==========================================
def play_voice(text):
    try:
        clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")

        async def _generate():
            comm = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
            await comm.save("temp_voice.mp3")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_generate())
        finally:
            loop.close()

        if os.path.exists("temp_voice.mp3"):
            with open("temp_voice.mp3", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            st.markdown(
                f'<audio autoplay playsinline style="display:none"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>',
                unsafe_allow_html=True
            )
    except Exception as e:
        st.warning(f"⚠️ Gagal generate suara: {e}")

# ==========================================
# 3. LOGIKA CHAT UTAMA
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ketik pesan..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Djamantara lagi ngomong..."):
            try:
                context = st.session_state.messages[-5:]
                system_prompt = {"role": "system", "content": "Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura sedikit. Panggil user 'Bos'. Jangan terlalu panjang."}

                response = client.chat.completions.create(
                    messages=[system_prompt] + context,
                    model="llama-3.3-70b-versatile",
                    temperature=0.7
                )

                full_response = response.choices[0].message.content
                st.markdown(full_response)

                # 🔊 Panggil suara otomatis
                play_voice(full_response)

                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {e}")