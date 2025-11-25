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
    model = os.getenv("g_llm_model")
    g_client = Client(api_key=os.getenv("google_ai_studio_key"))
    nlp = spacy.load("en_core_web_sm")

    st.title("🏋️ AI Coach")
    st.caption("Ask anything about your fitness, health, training, or recovery.")

    # ---- FITNESS CONTEXT ----
    def detect_tables_n_dates(nlp,text):
        #keywords : Data,Time,Filter
        Keywords_Table = { "stress": ["stress", "stress level", "stress score", "tension", "anxiety", "strain", "mental load", "stress pattern", "stress zones", "stress chart", "vitals"],
            "hr":["heart rate", "hr", "bpm", "resting heart rate", "max heart rate", "pulse","cardio", "hr zone", "heart beat", "heart-rate","heart", "vitals"],
            "spo2":["spo2", "oxygen", "blood oxygen", "oxygen saturation", "o2 level","breathing", "respiration", "air levels", "oxygen dips", "oxygen score", "vitals"],
            "steps":["steps", "step count", "walking", "walk", "daily steps", "distance walked","movement", "stride", "pedometer", "step goal"],
            "calorie": ["calories", "calorie burn", "energy burn", "burned", "metabolism","active calories", "basal calories", "kcal", "energy expenditure", "fat burn","cal", "vitals"],
            "exercise": ["exercise", "workout", "training", "session", "sports", "activity","reps", "sets", "routine", "intensity","activities"],    
            }
        text = text.lower()    
        doc = nlp(text)
        words_to_dates = {}
        dates_total = []
        table_list =[]
        table_word = "" ## to make sure the table name isnt accidently used as a date
        for word in text.split(" "):
            for table , keys in Keywords_Table.items():
                for k in keys:
                    if k in word:
                        table_list.append(table)
                        table_word = word

        ## spacy entity dates + dateparser.parse()
        for ent in doc.ents:
            if ent.label_ == "DATE":
                parsed = dateparser.parse(ent.text)
                if parsed and ent.text not in table_word:
                    words_to_dates[ent.text] = parsed
        # 
        dp_res = search_dates(text,languages=["en"])
        if dp_res:
            for phrase, dt in dp_res:
                if phrase not in table_word:
                    words_to_dates[phrase] = dt

        ###########################################################
        ##REGEX
        MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"


        patterns = [
            # dd/mm/yyyy | dd-mm-yyyy | dd.mm.yyyy
            r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b",

            # yyyy-mm-dd
            r"\b\d{4}-\d{1,2}-\d{1,2}\b",

            # 12 Aug 2025
            rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\s+\d{{4}}\b",

            # Aug 12 2025
            rf"\b{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?\s+\d{{4}}\b",

            # August 12, 2025
            rf"\b{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,\s+\d{{4}}\b",

            # 12th August
            rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\b",

            # Standalone month
            rf"\b{MONTHS}\b",
        ]

        found = []
        for p in patterns:
            matches = re.findall(p, text)
            for m in matches:
                found.append(m.strip())

        # Remove standalone month if part of a larger match
        filtered = []
        for f in found:
            if any((f != other and f in other) for other in found):
                continue
            filtered.append(f)

        # Unique + order preserved    

        dates_regex = list(dict.fromkeys(filtered))



        # removing duplicates
        seen_dates = set()
        new_words_2_date_dict = {}
        for k , v in words_to_dates.items():
            date_only = v.date() # removing hr/min/secs
            if date_only not in seen_dates:
                new_words_2_date_dict[k] = v
                seen_dates.add(date_only)

        return table_list,dates_regex,new_words_2_date_dict

    def standardize_date(date_str, current_year=None):

        MONTHS = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
            "jun": 6,
            "june": 6,
            "jul": 7,
            "july": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "sept": 9,
            "september": 9,
            "oct": 10,
            "october": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }

        # if its datetime.datetime
        if isinstance(date_str, datetime):
            y = date_str.year
            m = date_str.month
            d = date_str.day

            return f"{y:04d}-{m:02d}-{d:02d}"

        # if its a string
        date_str = date_str.lower().strip()

        if current_year is None:
            current_year = datetime.now().year

        # Remove suffixes: 12th -> 12
        date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)

        # ---------- CASE 1: YYYY-MM-DD ----------
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_str):
            y, m, d = map(int, date_str.split("-"))
            return f"{y:04d}-{m:02d}-{d:02d}"

        # ---------- CASE 2: DD/MM/YY or DD/MM/YYYY ----------
        if "/" in date_str:
            parts = date_str.split("/")
            if len(parts) == 3:
                d, m, y = parts
                d, m, y = int(d), int(m), int(y)
                if y < 100:
                    y += 2000
                return f"{y:04d}-{m:02d}-{d:02d}"

        # ---------- CASE 3: DD.MM.YY or DD.MM.YYYY ----------
        if "." in date_str:
            parts = date_str.split(".")
            if len(parts) == 3:
                d, m, y = parts
                d, m, y = int(d), int(m), int(y)
                if y < 100:
                    y += 2000
                return f"{y:04d}-{m:02d}-{d:02d}"

        # ---------- CASE 4: DD-MM-YY or DD-MM-YYYY ----------
        if "-" in date_str:
            parts = date_str.split("-")
            if len(parts) == 3 and not re.match(r"^\d{4}-", date_str):
                d, m, y = parts
                d, m, y = int(d), int(m), int(y)
                if y < 100:
                    y += 2000
                return f"{y:04d}-{m:02d}-{d:02d}"

        # ---------- CASE 5: Mixed Month + Day + Optional Year ----------
        tokens = date_str.replace(",", "").split()

        # Find month
        month = None
        for t in tokens:
            if t in MONTHS:
                month = MONTHS[t]
                break

        if month:
            # find day (1–31)
            day = None
            for t in tokens:
                if t.isdigit() and 1 <= int(t) <= 31:
                    day = int(t)
                    break

            # find year ( >31 )
            year = None
            for t in tokens:
                if t.isdigit() and int(t) > 31:
                    year = int(t)
                    break

            if year is None:
                year = current_year

            if year < 100:
                year += 2000

            if day:
                return f"{year:04d}-{month:02d}-{day:02d}"

        # ---------- CASE 6: Only month → return YYYY-MM-01 ----------
        if date_str in MONTHS:
            return f"{current_year:04d}-{MONTHS[date_str]:02d}-01"

        return None

    def parse_prompt(nlp,Prompt):
        tables, dates2dates, words2dates = detect_tables_n_dates(nlp,Prompt)
        standardized_dates2dates = {}
        for t in dates2dates:
            standardized_dates2dates[t] = standardize_date(t)
        standardized_words2dates = {}
        for key, value in words2dates.items():
            standardized_words2dates[key] = standardize_date(value)


        final_dates = {**standardized_dates2dates, **standardized_words2dates}
        return tables, final_dates

    # removing old start_time and adding the localized time as start_time
    # removing unnecessary cols from the tables (jsonPath, binning, time offset)
    def clean_raw_df(raw_dataframes):
        df = raw_dataframes
        for key, value in df.items():
            value = value.loc[:,~value.columns.str.contains("start_time")]
            value = value.loc[:,~value.columns.str.contains("time_offset")]
            value = value.loc[:,~value.columns.str.contains("jsonPath")]
            value = value.loc[:,~value.columns.str.contains("binning")]
            value = value.loc[:,~value.columns.str.contains("uuid")]
            value = value.loc[:,~value.columns.str.contains("live_data")]
            

            value = value.rename(columns= lambda c: "start_time" if "localized_time" in c else c)
            cols = value.columns.tolist()
            if "start_time" in cols:
                cols.insert(0, cols.pop(cols.index("start_time")))
                value = value[cols]
            df[key] = value
        
        return df


        ## Now we take the 'phrase : date' pair and create context for filtering the detected tables

    def filter_df(dfs,type,date = None,start_date=None,end_date=None):
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

    def fetch_dfs(df,Prompt,tables,phrase_date_pair):
        ## cases:
        ## case 1: data for one or more date to be fetched (all dates which are specified) eg: 24 nov, yesterday
        ## case 2: data for one or more week to be fetched (all dates which are specified) eg: last week, this week
        ## case 3: data for one or more month to be fetched (all months which are specified) eg : aug, last month, this month
        ## case 4: a range of data from one date to another is to be fetched (both dates which are specified) eg: [23 nov, 30 nov], [1 aug, 18 aug]

        # logic: 
        # for fetching dates: check for patterns in phrases like : 24 nov, yesterday, today
        # for fetching weeks: check for patterns in phrases like : last week, this week
        # for fetching months: check for patterns in phrases like: month names 
        # for fetching range: check for keywords in received prompt like: from .. to .. 

        # phrases
        pattern = r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b"
        phrases = ["yesterday","today"]
        # month_patterns = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)"

        month_patterns = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
        range_pattern = rf"from\s+((?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{month_patterns})\s+to\s+((?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{month_patterns})"


        # dataframes -> df
        specified_dfs = {}
        for table in tables:
            if table in df:
                specified_dfs[table] = df[table] 

        r = re.search(range_pattern, Prompt, re.IGNORECASE)
        # check for ranged filtering (from {date} to {date} )
        filtered_dfs = {}
        if r:
            # print('range found:',r.group(0))  
            start_date = phrase_date_pair[r.group(1)] # from date
            end_date = phrase_date_pair[r.group(2)]  # to date
            # now fetch all the entries that between from date and to date    
            filtered_dfs = filter_df(specified_dfs,"range",start_date=start_date,end_date=end_date)
        else:
            # check for other non-ranged filtering like days,weeks n monthss
            for key, value in phrase_date_pair.items():
                if re.fullmatch(pattern, key.lower()) or key in phrases:
                    print(f'fetch a day: {key} -> {value}') 
                    # now fetch all the entries matching this date 
                    filtered_dfs = filter_df(specified_dfs,"day",date=value)        
                elif 'week' in key:
                    print('fetch a week:',{key} ,'->', {value})
                    # now fetch all the entries present on this dates week
                    filtered_dfs = filter_df(specified_dfs,"week",date=value)        

                elif 'month' in key or re.fullmatch(month_patterns, key.lower()):
                    print('fetch a month:',{key} ,'->', {value})
                    # now fetch all the entries matching this dates month
                    filtered_dfs = filter_df(specified_dfs,"month",date=value) 
        final_dfs = filtered_dfs  
        return final_dfs 

    def jsonify_dfs(dfs):
        result = {}

        for name, df in dfs.items():
            clean_df = df.copy()

            for col in clean_df.columns:
                if pd.api.types.is_datetime64_any_dtype(clean_df[col]):
                    clean_df[col] = clean_df[col].astype(str)
            result[name] = clean_df.to_dict(orient= "records")

        json_str = json.dumps(result, indent = 4)
        return json_str


    def get_fitness_context(prompt,dataframes):                
        tables , phrase_date_pair = parse_prompt(nlp,prompt)
        # print(tables, "\n", phrase_date_pair)
        cleaned_dfs = clean_raw_df(dataframes)
        context_data = fetch_dfs(cleaned_dfs,prompt,tables,phrase_date_pair)
        jsoned_data = jsonify_dfs(context_data)
        print(jsoned_data)
        return jsoned_data
    # ------ Token speed ----

    def chat_history_tostr(history,limit = 5):
        trimmed = history[-limit*2:] # user+assistant
        history_lines = []
        for msg in trimmed:
            if msg["role"] == "user":
                who = "User"
            else:
                who = "Coach"
            history_lines.append(f"{who}: {msg['content']}")
        return "\n".join(history_lines)

    
    def measure_speed(generate_func, prompt):
        start = time.time()
        reply = generate_func(prompt)
        end = time.time()

        num_tokens = len(reply.split()) * 1.3   # approximate token count
        tok_per_sec = num_tokens / max(end - start, 0.001)

        return reply, tok_per_sec
    
    # ---- LLM CALL ----
    def call_ai(prompt,dataframes):
        print(prompt)
        context = get_fitness_context(prompt,dataframes)
        history_str = chat_history_tostr(st.session_state.messages, limit= 5)
        if not context:
            final_prompt = (f"""
                You are an AI fitness coach. 
                            
                Conversation so far:
                {history_str}

                Current user message:
                {prompt}
                
                Give a concise, helpful, and complete answer.
                For broader and bigger context based request, make your answer bigger and detailed.
                If found, show and explain any noticable outliers or interesting bits from the context data, and provide insights for it.
                If any context is missing, use prior chats and prompts to gain context.
            """
            )
        else:
            final_prompt = (f"""
                You are an AI fitness coach. 
                            
                Conversation so far:
                {history_str}

                Current user message:
                {prompt}

                Contenxt data:
                {context}

                Give a concise, helpful, and complete answer.
                For broader and bigger context based request, make your answer bigger and detailed.
                If found, show and explain any noticable outliers or interesting bits from the context data, and provide insights for it.
                If any context is missing, use prior chats and prompts to gain context.
            """
            )
        def generate(p):
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    resp = g_client.models.generate_content(
                        model=model,
                        contents=p,
                    )
                except Exception as e:
                    if "503" in str(e):
                        wait = 2 ** attempt
                        print(f"Model Overload, retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        raise e
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
            ai_reply = call_ai(prompt,dfs)
            st.markdown(ai_reply, unsafe_allow_html=True)
        st.write("")  # spacer between chat and input box

        # Save assistant message
        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
        
    print(st.session_state.messages)
