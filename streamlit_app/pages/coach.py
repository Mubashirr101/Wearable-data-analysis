import streamlit as st
import os
from dotenv import load_dotenv
from google.genai import Client
import time
import spacy
import dateparser
from dateparser.search import search_dates
import re
from datetime import datetime
import pandas as pd
import json

def show_coach(df_stress,df_hr,df_spo2,df_steps,df_calorie,df_exercise,df_exercise_routine,df_custom_exercise,df_inbuilt_exercises,supabase_client):
    load_dotenv()

    dfs = {
        'stress':df_stress,
        'hr': df_hr,
        'spo2':df_spo2,
        'steps':df_steps,
        'calorie':df_calorie,
        'exercise':df_exercise,
        'exercise_routine':df_exercise_routine,
        'custom_exercise':df_custom_exercise,
        'inbuilt_exercises':df_inbuilt_exercises
    }

    g_client = Client(api_key=os.getenv("google_ai_studio_key"))
    nlp = spacy.load("en_core_web_sm")

    # ---- LLM PROVIDER CONFIG ----
    PROVIDER_MODELS = {
        "Gemini": [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro",
        ],
        "OpenRouter": [
            "meta-llama/llama-3.3-70b-instruct",
            "mistralai/mistral-7b-instruct",
            "google/gemma-3-27b-it:free",
            "deepseek/deepseek-r1:free",
        ],
        "Groq": [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
            "mixtral-8x7b-32768",
        ],
    }

    # ---- TOP BAR: Title left, dropdowns top-right ----
    title_col, spacer, provider_col, model_col = st.columns([3, 1, 1.2, 2])

    with title_col:
        st.title("🏋️ AI Coach")
        st.caption("Ask anything about your fitness, health, training, or recovery.")

    with provider_col:
        st.write("")
        st.write("")
        selected_provider = st.selectbox(
            "Provider",
            options=list(PROVIDER_MODELS.keys()),
            index=list(PROVIDER_MODELS.keys()).index("Groq"),
            label_visibility="collapsed",
        )

    with model_col:
        st.write("")
        st.write("")
        selected_model = st.selectbox(
            "Model",
            options=PROVIDER_MODELS[selected_provider],
            index=PROVIDER_MODELS[selected_provider].index("llama-3.1-8b-instant") if selected_provider == "Groq" else 0,
            label_visibility="collapsed",
        )

    st.divider()

    # ---- FITNESS CONTEXT ----
    def detect_tables_n_dates(nlp, text):
        Keywords_Table = {
            "stress": ["stress", "stress level", "stress score", "tension", "anxiety", "strain", "mental load", "stress pattern", "stress zones", "stress chart", "vitals"],
            "hr": ["heart rate", "hr", "bpm", "resting heart rate", "max heart rate", "pulse", "cardio", "hr zone", "heart beat", "heart-rate", "heart", "vitals"],
            "spo2": ["spo2", "oxygen", "blood oxygen", "oxygen saturation", "o2 level", "breathing", "respiration", "air levels", "oxygen dips", "oxygen score", "vitals"],
            "steps": ["steps", "step count", "walking", "walk", "daily steps", "distance walked", "movement", "stride", "pedometer", "step goal"],
            "calorie": ["calories", "calorie burn", "energy burn", "burned", "metabolism", "active calories", "basal calories", "kcal", "energy expenditure", "fat burn", "cal", "vitals"],
            "exercise": ["exercise", "workout", "training", "session", "sports", "activity", "reps", "sets", "routine", "intensity", "activities"],
        }
        text = text.lower()
        doc = nlp(text)
        words_to_dates = {}
        table_list = []
        table_word = ""
        for word in text.split(" "):
            for table, keys in Keywords_Table.items():
                for k in keys:
                    if k in word:
                        table_list.append(table)
                        table_word = word

        for ent in doc.ents:
            if ent.label_ == "DATE":
                parsed = dateparser.parse(ent.text)
                if parsed and ent.text not in table_word:
                    words_to_dates[ent.text] = parsed

        dp_res = search_dates(text, languages=["en"])
        if dp_res:
            for phrase, dt in dp_res:
                if phrase not in table_word:
                    words_to_dates[phrase] = dt

        MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        patterns = [
            r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b",
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",
            rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\s+\d{{4}}\b",
            rf"\b{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?\s+\d{{4}}\b",
            rf"\b{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,\s+\d{{4}}\b",
            rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\b",
            rf"\b{MONTHS}\b",
        ]
        found = []
        for p in patterns:
            for m in re.findall(p, text):
                found.append(m.strip())
        filtered = [f for f in found if not any(f != o and f in o for o in found)]
        dates_regex = list(dict.fromkeys(filtered))

        seen_dates = set()
        new_words_2_date_dict = {}
        for k, v in words_to_dates.items():
            date_only = v.date()
            if date_only not in seen_dates:
                new_words_2_date_dict[k] = v
                seen_dates.add(date_only)

        return table_list, dates_regex, new_words_2_date_dict

    def standardize_date(date_str, current_year=None):
        MONTHS = {
            "jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,
            "apr":4,"april":4,"may":5,"jun":6,"june":6,"jul":7,"july":7,
            "aug":8,"august":8,"sep":9,"sept":9,"september":9,"oct":10,
            "october":10,"nov":11,"november":11,"dec":12,"december":12,
        }
        if isinstance(date_str, datetime):
            return f"{date_str.year:04d}-{date_str.month:02d}-{date_str.day:02d}"
        date_str = date_str.lower().strip()
        if current_year is None:
            current_year = datetime.now().year
        date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_str):
            y, m, d = map(int, date_str.split("-"))
            return f"{y:04d}-{m:02d}-{d:02d}"
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100: y += 2000
                return f"{y:04d}-{m:02d}-{d:02d}"
        if "." in date_str:
            parts = date_str.split(".")
            if len(parts) == 3:
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100: y += 2000
                return f"{y:04d}-{m:02d}-{d:02d}"
        if "-" in date_str:
            parts = date_str.split("-")
            if len(parts) == 3 and not re.match(r"^\d{4}-", date_str):
                d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                if y < 100: y += 2000
                return f"{y:04d}-{m:02d}-{d:02d}"
        tokens = date_str.replace(",", "").split()
        month = next((MONTHS[t] for t in tokens if t in MONTHS), None)
        if month:
            day = next((int(t) for t in tokens if t.isdigit() and 1 <= int(t) <= 31), None)
            year = next((int(t) for t in tokens if t.isdigit() and int(t) > 31), current_year)
            if year < 100: year += 2000
            if day:
                return f"{year:04d}-{month:02d}-{day:02d}"
        if date_str in MONTHS:
            return f"{current_year:04d}-{MONTHS[date_str]:02d}-01"
        return None

    def parse_prompt(nlp, Prompt):
        tables, dates2dates, words2dates = detect_tables_n_dates(nlp, Prompt)
        final_dates = {
            **{t: standardize_date(t) for t in dates2dates},
            **{k: standardize_date(v) for k, v in words2dates.items()},
        }
        return tables, final_dates

    def clean_raw_df(raw_dataframes):
        df = raw_dataframes
        for key, value in df.items():
            for col_pattern in ["start_time", "time_offset", "jsonPath", "binning", "uuid", "live_data"]:
                value = value.loc[:, ~value.columns.str.contains(col_pattern)]
            value = value.rename(columns=lambda c: "start_time" if "localized_time" in c else c)
            cols = value.columns.tolist()
            if "start_time" in cols:
                cols.insert(0, cols.pop(cols.index("start_time")))
                value = value[cols]
            df[key] = value
        return df

    def filter_df(dfs, type, date=None, start_date=None, end_date=None):
        filtered_dfs = {}
        if date:
            target_date = pd.to_datetime(date).date()
            target_iso_year, target_iso_week, _ = target_date.isocalendar()
        for table_name, table in dfs.items():
            if type == "range":
                df_filtered = table[(table["start_time"] >= start_date) & (table["start_time"] <= end_date)]
            elif type == "day":
                df_filtered = table[table["start_time"].dt.date == target_date]
            elif type == "week":
                df_filtered = table[(table["start_time"].dt.isocalendar().year == target_iso_year) & (table["start_time"].dt.isocalendar().week == target_iso_week)]
            elif type == "month":
                df_filtered = table[(table["start_time"].dt.year == target_date.year) & (table["start_time"].dt.month == target_date.month)]
            filtered_dfs[table_name] = df_filtered
        return filtered_dfs

    def fetch_dfs(df, Prompt, tables, phrase_date_pair):
        pattern = r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b|\b\d{1,2}-\d{1,2}-\d{4}\b"
        phrases = ["yesterday", "today"]
        month_patterns = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        range_pattern = rf"from\s+((?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{month_patterns})\s+to\s+((?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{month_patterns})"

        specified_dfs = {table: df[table] for table in tables if table in df}
        filtered_dfs = {}
        r = re.search(range_pattern, Prompt, re.IGNORECASE)
        if r:
            filtered_dfs = filter_df(specified_dfs, "range", start_date=phrase_date_pair[r.group(1)], end_date=phrase_date_pair[r.group(2)])
        else:
            for key, value in phrase_date_pair.items():
                if re.fullmatch(pattern, key.lower()) or key in phrases:
                    filtered_dfs = filter_df(specified_dfs, "day", date=value)
                elif 'week' in key:
                    filtered_dfs = filter_df(specified_dfs, "week", date=value)
                elif 'month' in key or re.fullmatch(month_patterns, key.lower()):
                    filtered_dfs = filter_df(specified_dfs, "month", date=value)
        return filtered_dfs

    def jsonify_dfs(dfs):
        result = {}
        for name, df in dfs.items():
            clean_df = df.copy()
            for col in clean_df.columns:
                if pd.api.types.is_datetime64_any_dtype(clean_df[col]):
                    clean_df[col] = clean_df[col].astype(str)
            result[name] = clean_df.to_dict(orient="records")
        return json.dumps(result, separators=(',', ':'))

    def get_fitness_context(prompt, dataframes):
        tables, phrase_date_pair = parse_prompt(nlp, prompt)
        cleaned_dfs = clean_raw_df(dataframes)
        context_data = fetch_dfs(cleaned_dfs, prompt, tables, phrase_date_pair)
        jsoned_data = jsonify_dfs(context_data)
        print(jsoned_data)
        return jsoned_data

    def chat_history_tostr(history, limit=5):
        trimmed = history[-limit * 2:]
        lines = []
        for msg in trimmed:
            who = "User" if msg["role"] == "user" else "Coach"
            lines.append(f"{who}: {msg['content']}")
        return "\n".join(lines)

    def measure_speed(generate_func, prompt):
        start = time.time()
        reply = generate_func(prompt)
        end = time.time()
        num_tokens = len(reply.split()) * 1.3
        tok_per_sec = num_tokens / max(end - start, 0.001)
        return reply, tok_per_sec

    # ---- PROVIDER GENERATE FUNCTIONS ----
    def gemini_generate(prompt, model):
        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = g_client.models.generate_content(model=model, contents=prompt)
                return resp.text
            except Exception as e:
                if "503" in str(e):
                    wait = 2 ** attempt
                    print(f"Gemini overloaded. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise e

    def openrouter_generate(prompt, model):
        import requests
        headers = {"Authorization": f"Bearer {os.getenv('openrouter_key')}", "Content-Type": "application/json"}
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=40)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def groq_generate(prompt, model):
        import requests
        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY is not set in your .env file.")
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=40
        )
        if not r.ok:
            # Surface the actual Groq error message instead of a generic HTTP error
            try:
                err = r.json()
                msg = err.get("error", {}).get("message", r.text)
            except Exception:
                msg = r.text
            raise RuntimeError(f"Groq API error {r.status_code}: {msg}")
        return r.json()["choices"][0]["message"]["content"]

    # ---- MAIN LLM CALL ----
    def call_ai(prompt, dataframes, provider, model):
        print(f"[LLM] Provider: {provider} | Model: {model}")
        context = get_fitness_context(prompt, dataframes)
        history_str = chat_history_tostr(st.session_state.messages, limit=5)

        if not context:
            final_prompt = f"""You are an AI fitness coach.

Conversation so far:
{history_str}

Current user message:
{prompt}

Give a concise, helpful, and complete answer."""
        else:
            final_prompt = f"""You are an AI fitness coach.

Conversation so far:
{history_str}

Current user message:
{prompt}

Context data:
{context}

Give a concise, helpful, and complete answer.
Explain any noticeable outliers or patterns using the context."""

        SPEED_THRESHOLD = 2.0

        if provider == "Gemini":
            reply, speed = measure_speed(lambda p: gemini_generate(p, model), final_prompt)
            if speed < SPEED_THRESHOLD:
                print(f"Gemini speed {speed:.1f} tok/s → falling back to OpenRouter...")
                or_model = os.getenv("openrouter_model", "meta-llama/llama-3.3-70b-instruct")
                reply, speed = measure_speed(lambda p: openrouter_generate(p, or_model), final_prompt)
        elif provider == "OpenRouter":
            reply, speed = measure_speed(lambda p: openrouter_generate(p, model), final_prompt)
        elif provider == "Groq":
            reply, speed = measure_speed(lambda p: groq_generate(p, model), final_prompt)
        else:
            reply, speed = "Unknown provider selected.", 0.0

        reply += f"\n\n<sub><sup><span style='color:#999;'>~{speed:.1f} tok/s · {provider} · {model}</span></sup></sub>"
        return reply

    # ---- SESSION MEMORY ----
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ---- DISPLAY PREVIOUS MESSAGES ----
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)
    st.write("")

    # ---- FRIENDLY ERROR MESSAGES ----
    PROVIDER_TIPS = {
        "Groq":       "Try switching to a different Groq model, or swap to Gemini / OpenRouter above.",
        "Gemini":     "Try switching to a lighter Gemini model (e.g. Flash), or swap to Groq above.",
        "OpenRouter": "Try a different OpenRouter model, or swap to Groq above.",
    }

    def friendly_error(e, provider):
        msg = str(e).lower()
        tip = PROVIDER_TIPS.get(provider, "Try switching providers above.")

        if "rate limit" in msg or "429" in msg or "quota" in msg:
            return f"⚠️ **Rate limit hit on {provider}.** You've sent too many requests too quickly. Wait a moment, then try again — or {tip}"
        elif "decommissioned" in msg or "deprecated" in msg or "no longer supported" in msg:
            return f"⚠️ **Model no longer available.** This model was retired by {provider}. {tip}"
        elif "503" in msg or "502" in msg or "service unavailable" in msg or "overloaded" in msg:
            return f"⚠️ **{provider} is temporarily overloaded.** Their servers are busy right now. Wait a few seconds and retry — or {tip}"
        elif "401" in msg or "unauthorized" in msg or "invalid api key" in msg or "api key" in msg:
            return f"⚠️ **API key issue with {provider}.** Check that your key is set correctly in `.env`. {tip}"
        elif "timeout" in msg or "timed out" in msg:
            return f"⚠️ **{provider} took too long to respond.** The request timed out. Try again or {tip}"
        elif "400" in msg or "bad request" in msg:
            return f"⚠️ **Bad request sent to {provider}.** This usually means an unsupported model or malformed input. {tip}"
        else:
            return f"⚠️ **Something went wrong with {provider}.** {tip}\n\n_Details: {str(e)}_"

    # ---- CHAT INPUT ----
    if prompt := st.chat_input("Ask something..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                ai_reply = call_ai(prompt, dfs, selected_provider, selected_model)
                st.markdown(ai_reply, unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            except Exception as e:
                err_msg = friendly_error(e, selected_provider)
                st.warning(err_msg)
                print(f"[LLM ERROR] {e}")
        st.write("")

    print(st.session_state.messages)