import streamlit as st
import os
from dotenv import load_dotenv
from google.genai import Client
import time


def show_coach():
    load_dotenv()

    model = os.getenv("g_llm_model")
    g_client = Client(api_key=os.getenv("google_ai_studio_key"))

    st.title("🏋️ AI Coach")
    st.caption("Ask anything about your fitness, health, training, or recovery.")

    # ---- FITNESS CONTEXT ----
    def get_fitness_context():
        return {
            "last_sync": "2025-11-17",
            "steps": {"7_day_avg": 7850, "trend": "up"},
            "sleep": {"avg": "6h 41m", "trend": "down"},
            "rhr": 64,
            "stress": {"peak_hours": ["7pm-10pm"]},
            "workouts": [
                {"type": "running", "duration": 34, "date": "2025-11-12"},
                {"type": "strength", "duration": 42, "date": "2025-11-14"},
            ],
        }

    # ------ Token speed ----
    
    def measure_speed(generate_func, prompt):
        start = time.time()
        reply = generate_func(prompt)
        end = time.time()

        num_tokens = len(reply.split()) * 1.3   # approximate token count
        tok_per_sec = num_tokens / max(end - start, 0.001)

        return reply, tok_per_sec
    
    # ---- LLM CALL ----
    def call_ai(prompt):
        context = get_fitness_context()
        final_prompt = (
            f"You are an AI fitness coach. Use the following summary only:\n"
            f"{prompt}\n\n"
            f"Context:\n"
            f"{context}\n\n"
            f"Give a concise, helpful, and complete answer."
        )
        def generate(p):
            resp = g_client.models.generate_content(
                model=model,
                contents=p,
            )
            return resp.text

        reply,speed = measure_speed(generate,final_prompt)

        reply += f"\n\n<sub><sup><span style='color:#999;'>~{speed:.1f} tok/s</span></sup></sub>"
        return reply

    # ---- SESSION MEMORY ----
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ---- DISPLAY PREVIOUS MESSAGES ----
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)
    st.write("")  # spacer between chat and input box



    # ---- CHAT INPUT (Main Loop like example) ----
    if prompt := st.chat_input("Ask something..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate AI message
        with st.chat_message("assistant"):
            ai_reply = call_ai(prompt)
            st.markdown(ai_reply, unsafe_allow_html=True)
        st.write("")  # spacer between chat and input box


        # Save assistant message
        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
