import streamlit as st
import pandas as pd
import numpy as np
import os,json,re,datetime
from datetime import timedelta
import altair as alt

# session = st.session_state
# for k in session.keys():
#     session[k] = session[k]


def render_metric_tab(tab, metric_name, df, config, supabase_client=None):
    with tab:
        col1, col2 = st.columns([4, 2])
        col1.header(f"{config.get('daily_icon','📆')} Daily {config['title']} Chart")

        # Initialize session key for filtered data
        if f"df_{metric_name}_filtered" not in st.session_state:
            st.session_state[f"df_{metric_name}_filtered"] = pd.DataFrame()

        # ---------- Date Filter ----------
        date_filter = col2.date_input(
            f"{metric_name}_Date",
            key=f"{metric_name}_date_filter",
            label_visibility="hidden"
        )

        # If a date is selected, filter; otherwise reuse persisted data
        if date_filter:
            df_filtered = df[df[config["localized_time"]].dt.date == pd.to_datetime(date_filter).date()].copy()
            if not df_filtered.empty:
                st.session_state[f"df_{metric_name}_filtered"] = df_filtered
        else:
            df_filtered = st.session_state.get(f"df_{metric_name}_filtered", pd.DataFrame())

        # Use the last known filtered data if the new one is empty
        if df_filtered.empty and f"df_{metric_name}_filtered" in st.session_state:
            df_filtered = st.session_state[f"df_{metric_name}_filtered"]

        # ---------- Daily Chart ----------
        chart_type_map = {
            "hr": "hr",
            "stress": "stress",
            "spo2": "spo2",
            "steps": "steps",
            "calorie": "calorie"
        }

        chart_daily = chartTimeData(
            df_filtered,
            config["localized_time"],
            config["value"],
            "Time/Date",
            config["y_label"],
            f"{config.get('daily_icon','📆')} {config['title']} over Time",
            chart_type=chart_type_map.get(metric_name, "line")
        )
        st.altair_chart(chart_daily, use_container_width=True)

        # ----------  Adv Chart ----------
        adv_chart_displayed = False
        if metric_name == "steps":
            # advanced visualizations for steps dataframe
            if df_filtered.empty:
                st.info("No step data for selected date to show advanced charts.")
            else:
                adv_chart_displayed = True
                df_steps = df_filtered.copy()
                # ensure datetime
                df_steps[config["localized_time"]] = pd.to_datetime(df_steps[config["localized_time"]], errors="coerce")
                df_steps = df_steps.sort_values(config["localized_time"])
                # daily aggregates (resample by day)
                try:
                    daily = df_steps.set_index(config["localized_time"]).resample("D").agg({
                        config["value"]: "sum",
                        "run_step": "sum" if "run_step" in df_steps.columns else "mean",
                        "walk_step": "sum" if "walk_step" in df_steps.columns else "mean",
                        "step_count_speed": "mean" if "step_count_speed" in df_steps.columns else "mean",
                        "step_count_distance": "sum" if "step_count_distance" in df_steps.columns else "sum",
                        "step_count_calorie": "sum" if "step_count_calorie" in df_steps.columns else "sum",
                    }).reset_index()
                except Exception:
                    # fallback simple groupby day
                    df_steps["day"] = df_steps[config["localized_time"]].dt.date
                    daily = df_steps.groupby("day").agg({
                        config["value"]: "sum",
                        "run_step": "sum" if "run_step" in df_steps.columns else "mean",
                        "walk_step": "sum" if "walk_step" in df_steps.columns else "mean",
                        "step_count_speed": "mean" if "step_count_speed" in df_steps.columns else "mean",
                        "step_count_distance": "sum" if "step_count_distance" in df_steps.columns else "sum",
                        "step_count_calorie": "sum" if "step_count_calorie" in df_steps.columns else "sum",
                    }).reset_index().rename(columns={"day": config["localized_time"]})

                with st.expander("Advanced charts — detailed steps features", expanded=True):
                    # summary metrics
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    mcol1.metric("Total steps (day)", int(daily[config["value"]].sum()))
                    mcol2.metric("Total Calories Burned (day)", int(daily[config["step_count_calorie"]].sum()))
                    mcol3.metric("Avg speed (day)", int(daily[config["step_count_speed"]].mean()))
                    mcol4.metric("Total distance (m)", round(daily.get("step_count_distance", pd.Series([0])).sum(), 2))

                    # Row 1: stacked run/walk per day + rolling steps line
                    r1c1, r1c2 = st.columns([2,3])
                    # stacked run/walk
                    if {"run_step","walk_step"}.issubset(df_steps.columns):
                        # fold in pandas so Altair has concrete dtypes
                        folded = daily[[config["localized_time"], "run_step", "walk_step"]].melt(
                            id_vars=[config["localized_time"]],
                            value_vars=["run_step", "walk_step"],
                            var_name="type",
                            value_name="count"
                        ).dropna(subset=["count"])
                        folded["type"] = folded["type"].astype(str)
                        folded["count"] = pd.to_numeric(folded["count"], errors="coerce").fillna(0)

                        stacked = alt.Chart(folded).mark_bar().encode(
                            x=alt.X(config["localized_time"], title="Date", axis=alt.Axis(format="%Y-%m-%d")),
                            y=alt.Y("count:Q", title="Count"),
                            color=alt.Color("type:N"),
                            tooltip=[config["localized_time"], alt.Tooltip("type:N"), alt.Tooltip("count:Q")]
                        ).properties(title="Run vs Walk counts per day")
                        r1c1.altair_chart(stacked, use_container_width=True)
                    else:
                        r1c1.info("run_step / walk_step not available in this dataset")

                    # steps with rolling mean
                    df_steps_time = df_steps[[config["localized_time"], config["value"]]].dropna().copy()
                    if not df_steps_time.empty:
                        df_steps_time = df_steps_time.set_index(config["localized_time"]).resample("h").sum().reset_index()
                        df_steps_time["rolling_3h"] = df_steps_time[config["value"]].rolling(3, min_periods=1).mean()
                        steps_line = alt.Chart(df_steps_time).encode(
                            x=alt.X(config["localized_time"], title="Time"),
                        )
                        line = steps_line.mark_line(color="purple").encode(
                            y=alt.Y(config["value"], title="Steps"),
                            tooltip=[config["localized_time"], config["value"]]
                        )
                        rolling = steps_line.mark_line(strokeDash=[4,4], color="black").encode(
                            y=alt.Y("rolling_3h:Q", title="Rolling mean")
                        )
                        r1c2.altair_chart((line + rolling).properties(title="Steps over time (hourly) with rolling mean"), use_container_width=True)
                    else:
                        r1c2.info("Not enough time series data for rolling chart.")

                    # Row 2: scatter speed vs distance and histogram of steps
                    r2c1, r2c2 = st.columns(2)
                    if {"step_count_speed","step_count_distance"}.issubset(df_steps.columns):
                        scatter = alt.Chart(df_steps.dropna(subset=["step_count_speed","step_count_distance"])).mark_circle(size=60).encode(
                            x=alt.X("step_count_speed:Q", title="Speed"),
                            y=alt.Y("step_count_distance:Q", title="Distance"),
                            color=alt.Color("run_step:N", title="Run vs Walk") if "run_step" in df_steps.columns else alt.value("steelblue"),
                            tooltip=[config["localized_time"], "step_count_speed", "step_count_distance", config["value"]]
                        ).interactive().properties(title="Speed vs Distance (points colored by run_step if available)")
                        r2c1.altair_chart(scatter, use_container_width=True)
                    else:
                        r2c1.info("Speed/distance data not available.")

                    # histogram of step counts
                    hist = alt.Chart(df_steps.dropna(subset=[config["value"]])).mark_bar().encode(
                        x=alt.X(f"{config['value']}:Q", bin=alt.Bin(maxbins=40), title="Step count"),
                        y=alt.Y("count()", title="Frequency"),
                        tooltip=[alt.Tooltip(f"{config['value']}:Q")]
                    ).properties(title="Distribution of Step Counts")
                    r2c2.altair_chart(hist, use_container_width=True)

                    # Row 3: boxplot calories and scatter steps vs calories
                    r3c1, r3c2 = st.columns(2)
                    if "step_count_calorie" in df_steps.columns:
                        box = alt.Chart(df_steps.dropna(subset=["step_count_calorie"])).mark_boxplot().encode(
                            x=alt.X("step_count_calorie:Q", title="Calories"),
                            tooltip=["step_count_calorie"]
                        ).properties(title="Calories distribution")
                        r3c1.altair_chart(box, use_container_width=True)
                    else:
                        r3c1.info("Calories not available.")

                    if config["value"] in df_steps.columns and "step_count_calorie" in df_steps.columns:
                        scatter2 = alt.Chart(df_steps.dropna(subset=[config["value"], "step_count_calorie"])).mark_circle().encode(
                            x=alt.X(config["value"], title="Steps"),
                            y=alt.Y("step_count_calorie", title="Calories"),
                            tooltip=[config["localized_time"], config["value"], "step_count_calorie"]
                        ).properties(title="Steps vs Calories")
                        r3c2.altair_chart(scatter2, use_container_width=True)
                    else:
                        r3c2.info("Cannot plot Steps vs Calories (missing columns).")
            

        # ---------- Hourly / binning chart ----------
        # Skip hourly chart if adv chart is displayed
        if not (metric_name == "steps" and adv_chart_displayed):
            # Huurly chart
            if "jsonPath" in df_filtered.columns:            
                # Huurly chart
                col3, col4 = st.columns([4, 2])
                col3.header(f"{config['hourly_icon']}  Hourly {config['title']} Chart")
                time_filter = col4.time_input(
                    f"{metric_name}_Time",
                    key=f"{metric_name}_time_filter",
                    step=3600,
                    label_visibility="hidden"
                )

                jsonFilepath = None
                df_bin = None
                chartBin = pd.DataFrame()

                


                if not df_filtered.empty and time_filter != datetime.time(0, 0):
                    df_copy = df_filtered
                    # df_copy['start_time'] = df_copy.apply(lambda row: apply_offset(row, config['time_offset'], config['start_time']), axis=1)
                    match = df_copy.loc[df_copy["localized_time"].dt.time == time_filter]
                    if not match.empty:
                        jsonFilepath = match.iloc[0]['jsonPath']
                        # cache json
                        json_cache = st.session_state.setdefault("json_cache", {})
                        if jsonFilepath in json_cache:
                            df_bin = json_cache[jsonFilepath]
                        else:
                            with st.spinner(f"Fetching {config['title']} details..."):
                                df_bin = loadBinningjsons(df[config["time_offset"]], jsonFilepath, supabase_client)
                                json_cache[jsonFilepath] = df_bin

                        st.session_state[f"last_{metric_name}_bin_df"] = df_bin
                        chartBin = chartBinningjsons(
                            df_bin,
                            "start_time",
                            "Time",
                            config["value_bin"],
                            config["y_label"],
                            config["min"],
                            config["max"]
                        )
                    else:
                        st.info("No Data found for the selected time.")
                else:
                    st.info("Please select a date & time")

                # Session state save
                if f"{metric_name}_chartBin" not in st.session_state:
                    st.session_state[f"{metric_name}_chartBin"] = pd.DataFrame()

                st.session_state[f"{metric_name}_chartBin"] = chartBin
                st.altair_chart(st.session_state[f"{metric_name}_chartBin"], use_container_width=True)
            else:
                st.info("No binning data available")

def cal_tab(tab, metric_name, df, config, supabase_client=None):
    with tab:
        st.header(f"{config['daily_icon']} {config['title']} Dashboard")
        
        # Create main layout columns
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # View selector
            view_option = st.radio(
                "View Mode:",
                ["Week View", "Month View"],
                horizontal=True,
                key=f"{metric_name}_view_selector"
            )
        
        with col2:
            # Timezone info
            st.caption(f"Timezone: {config['time_offset']}")
        
        # Data preprocessing
        if not df.empty:
            # Convert timestamp columns
            df[config['localized_time']] = pd.to_datetime(df[config['localized_time']], unit='ms', errors='coerce')
            df[config['date']] = pd.to_datetime(df[config['date']], unit='ms', errors='coerce')
            
            # Apply timezone offset
            # Apply timezone offset locally (no apply_offset needed)
            offset_str = config['time_offset']  # e.g. "+5:30" or "-7:00"
            sign = 1 if offset_str.startswith("+") else -1
            hours, minutes = map(int, offset_str[1:].split(":"))
            offset = pd.Timedelta(hours=sign * hours, minutes=sign * minutes)

            df[config['localized_time']] = df[config['localized_time']] + offset
            df[config['date']] = df[config['date']] + offset

        
        # Available calorie metrics for toggling
        calorie_metrics = {
            'Active Calories': config['calories_burned_active_calorie'],
            'Rest Calories': config['calories_burned_rest_calorie'], 
            'Exercise Calories': config['total_exercise_calories'],
            'TEF Calories': config['calories_burned_tef_calorie'],
            'Goal Calories': config['goal_calories']
        }
        
        # Metric
        selected_metrics = [(display_name, col_name) for display_name, col_name in calorie_metrics.items() if col_name in df.columns]        
        # Main chart based on view mode
        if not df.empty:
            if view_option == "Week View":
                chart_data = prepare_weekly_data(df, config, selected_metrics)
                chart,chrtdf = create_weekly_chart(chart_data, config,selected_metrics)
                summary_label = 'Week'
            else:
                chart_data = prepare_monthly_data(df, config, selected_metrics)
                chart,chrtdf = create_monthly_chart(chart_data, config,selected_metrics)
                summary_label = 'Month'
            
            if chart:
                colchrt,coldf = st.columns([4,2]) 
                colchrt.altair_chart(chart, use_container_width=True)
                with coldf.expander(f'{summary_label} Summary'):
                    st.dataframe(chrtdf.style.format("{:.2f}"))
        
        # Expandable calendar and daily stats
        with st.expander("📅 Daily Calorie Details", expanded=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Calendar date picker
                if not df.empty:
                    min_date = df[config['date']].min().date()
                    max_date = df[config['date']].max().date()
                    selected_date = st.date_input(
                        "Select Date:",
                        value=min_date,
                        min_value=min_date,
                        max_value=max_date,
                        key="calorie_date_picker"
                    )
                else:
                    selected_date = st.date_input("Select Date:", key="calorie_date_picker")
            
            with col2:
                st.write("")  # Spacer
                if st.button("Refresh Day Stats", key="refresh_cal_stats"):
                    st.rerun()
            
            # Display daily stats
            if not df.empty and selected_date:
                daily_data = df[df[config['date']].dt.date == selected_date]
                
                if not daily_data.empty:
                    display_daily_stats(daily_data, config, selected_date)
                    display_daily_charts(daily_data, config, selected_metrics)
                else:
                    st.info(f"No calorie data available for {selected_date}")
            else:
                st.info("Please select a date to view daily stats")



def prepare_weekly_data(df, config, selected_metrics):
    """
    Prepare daily data for weekly/monthly charting.
    Adds:
    - week_start (Monday of the week)
    - month_start (first day of month)
    - week_number within the month
    """
    df_prepared = df.copy()
    df_prepared[config['date']] = pd.to_datetime(df_prepared[config['date']])

    # Month and week info
    df_prepared['month_start'] = df_prepared[config['date']].dt.to_period('M').apply(lambda r: r.start_time )
    df_prepared['week_start'] = df_prepared[config['date']].dt.to_period('W').apply(lambda r: r.start_time)

    # Compute week number within month
    df_prepared['week_number'] = df_prepared.groupby('month_start')['week_start'].rank(method='dense').astype(int)

    # Rename metric columns for display
    for display_name, col_name in selected_metrics:
        if col_name in df_prepared.columns:
            df_prepared[display_name] = df_prepared[col_name]

    # Return daily-level data with extra columns
    return df_prepared[['month_start', 'week_start', 'week_number', config['date']] +
                       [name for name, _ in selected_metrics]]

def create_weekly_chart(df, config, selected_metrics):
    import altair as alt
    import pandas as pd
    import streamlit as st

    if df.empty:
        st.info("No data available")
        return None

    # Ensure datetime
    df[config['date']] = pd.to_datetime(df[config['date']])

    # --- Month & Week Columns ---
    if 'month_start' not in df.columns:
        df['month_start'] = df[config['date']].dt.to_period('M').apply(lambda r: r.start_time)
    if 'week_number' not in df.columns:
        df['week_number'] = df[config['date']].dt.isocalendar().week

    # --- Initialize session state ---
    if 'current_month_idx' not in st.session_state:
        st.session_state.current_month_idx = 0
    if 'current_week' not in st.session_state:
        st.session_state.current_week = None

    unique_months = sorted(df['month_start'].unique())
    current_month_idx = st.session_state.current_month_idx
    current_month = unique_months[current_month_idx]

    # --- Month Navigation ---
    col1, col2, col3 = st.columns([1, 2, 1],gap='small')
    with col1:
        if st.button("⬅️ Prev Month",use_container_width=True) and current_month_idx > 0:
            st.session_state.current_month_idx -= 1
            st.session_state.current_week = None
    with col2:
        if st.button(f"{current_month.strftime('%B %Y')}",use_container_width=True):
            st.session_state.current_month_idx = len(unique_months) - 1
            st.session_state.current_week = None
    with col3:
        if st.button("Next Month ➡️",use_container_width=True) and current_month_idx < len(unique_months) - 1:
            st.session_state.current_month_idx += 1
            st.session_state.current_week = None

    # --- Week Buttons ---
    weeks_in_month = sorted(df[df['month_start'] == current_month]['week_number'].unique())
    if st.session_state.current_week not in weeks_in_month:
        st.session_state.current_week = weeks_in_month[0]

    week_cols = st.columns(len(weeks_in_month),gap='small')
    
    for i, wk in enumerate(weeks_in_month):
        # Highlight active week
        if wk == st.session_state.current_week:
            if week_cols[i].button(f"**Week {i+1}** 🔹",use_container_width=True):
                st.session_state.current_week = wk
        else:
            if week_cols[i].button(f"Week {i+1}",use_container_width=True):
                st.session_state.current_week = wk

    # Filter data for current week
    week_data = df[(df['month_start'] == current_month) & (df['week_number'] == st.session_state.current_week)]
    if week_data.empty:
        st.warning("No data for selected week")
        return None

    week_start = week_data[config['date']].min()
    week_end = week_data[config['date']].max()
    st.markdown(f"### Week {weeks_in_month.index(st.session_state.current_week)+1}: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}")

    # --- Metric Selection ---
    metrics_display = [name for name, _ in selected_metrics]
    selected_metrics_ui = st.multiselect("Select Metrics to Show", metrics_display, default=metrics_display)

    # Melt data for Altair
    melted_data = week_data.melt(
        id_vars=[config['date']],
        value_vars=selected_metrics_ui,
        var_name='metric',
        value_name='value'
    )

    # Fixed color mapping
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1',
              '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF']
    color_scale = alt.Scale(domain=metrics_display, range=colors[:len(metrics_display)])

    # --- Altair Chart ---
    chart = (
        alt.Chart(melted_data)
        .mark_line(point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=alt.X(f"{config['date']}:T", title="Day", axis=alt.Axis(format="%a %d")),
            y=alt.Y("value:Q", title="Value"),
            color=alt.Color("metric:N", scale=color_scale, legend=alt.Legend(title="Metric")),
            tooltip=[config['date'], "metric", "value"]
        )
        .properties(height=400, title="Daily Metrics")
        .interactive()
    )

    # --- Summary Stats ---
    summary = week_data[selected_metrics_ui].agg(['sum', 'mean', 'max']).T
    summary.columns = ['Total', 'Average', 'Max']

    return chart,summary

def prepare_monthly_data(df, config, selected_metrics):
    """
    Prepare daily data for monthly charting.
    Adds:
    - month_start (first day of month)
    - Renames metric columns for display
    """
    df_prepared = df.copy()
    df_prepared[config['date']] = pd.to_datetime(df_prepared[config['date']])

    # Month info
    df_prepared['month_start'] = df_prepared[config['date']].dt.to_period('M').apply(lambda r: r.start_time)

    # Rename metric columns for display
    for display_name, col_name in selected_metrics:
        if col_name in df_prepared.columns:
            df_prepared[display_name] = df_prepared[col_name]

    # Return daily-level data with month column
    return df_prepared[['month_start', config['date']] + [name for name, _ in selected_metrics]]

def create_monthly_chart(df, config, selected_metrics):
    import altair as alt
    import pandas as pd
    import streamlit as st

    if df.empty:
        st.info("No data available")
        return None

    # Ensure datetime
    df[config['date']] = pd.to_datetime(df[config['date']])
    if 'month_start' not in df.columns:
        df['month_start'] = df[config['date']].dt.to_period('M').apply(lambda r: r.start_time)

    # --- Initialize session state ---
    if 'current_month_idx' not in st.session_state:
        st.session_state.current_month_idx = 0

    unique_months = sorted(df['month_start'].unique())
    current_month_idx = st.session_state.current_month_idx
    current_month = unique_months[current_month_idx]

    # --- Month Navigation ---
    col1, col2, col3 = st.columns([1, 2, 1], gap='small')
    with col1:
        if st.button("⬅️ Prev Month", use_container_width=True) and current_month_idx > 0:
            st.session_state.current_month_idx -= 1
    with col2:
        st.button(f"{current_month.strftime('%B %Y')}", use_container_width=True)
    with col3:
        if st.button("Next Month ➡️", use_container_width=True) and current_month_idx < len(unique_months) - 1:
            st.session_state.current_month_idx += 1

    # Filter data for current month
    month_data = df[df['month_start'] == current_month]
    if month_data.empty:
        st.warning("No data for selected month")
        return None

    month_start = month_data[config['date']].min()
    month_end = month_data[config['date']].max()
    st.markdown(f"### {current_month.strftime('%B %Y')} ({month_start.strftime('%b %d')} - {month_end.strftime('%b %d')})")

    # --- Metric Selection ---
    metrics_display = [name for name, _ in selected_metrics]
    selected_metrics_ui = st.multiselect("Select Metrics to Show", metrics_display, default=metrics_display)

    # Melt data for Altair
    melted_data = month_data.melt(
        id_vars=[config['date']],
        value_vars=selected_metrics_ui,
        var_name='metric',
        value_name='value'
    )

    # Fixed color mapping
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1',
              '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF']
    color_scale = alt.Scale(domain=metrics_display, range=colors[:len(metrics_display)])

    # --- Altair Chart ---
    chart = (
        alt.Chart(melted_data)
        .mark_line(point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=alt.X(f"{config['date']}:T", title="Day", axis=alt.Axis(format="%d")),
            y=alt.Y("value:Q", title="Value"),
            color=alt.Color("metric:N", scale=color_scale, legend=alt.Legend(title="Metric")),
            tooltip=[config['date'], "metric", "value"]
        )
        .properties(height=400, title="Monthly Metrics Trend")
        .interactive()
    )

    # --- Summary Stats ---
    summary = month_data[selected_metrics_ui].agg(['sum', 'mean', 'max']).T
    summary.columns = ['Total', 'Average', 'Max']

    return chart, summary

def display_daily_stats(daily_data, config, selected_date):
    """Display daily statistics in metric cards"""
    st.subheader(f"📈 Daily Stats for {selected_date}")
    
    # Calculate metrics
    metrics_data = {}
    for col in [config['calories_burned_active_calorie'], 
                config['calories_burned_rest_calorie'],
                config['total_exercise_calories'],
                config['calories_burned_tef_calorie'],
                config['goal_calories']]:
        if col in daily_data.columns:
            metrics_data[col] = daily_data[col].sum()
    
    # Create metric cards
    cols = st.columns(len(metrics_data))
    
    metric_config = {
        config['calories_burned_active_calorie']: {'name': 'Active Calories', 'icon': '🔥'},
        config['calories_burned_rest_calorie']: {'name': 'Rest Calories', 'icon': '😴'},
        config['total_exercise_calories']: {'name': 'Exercise Calories', 'icon': '💪'},
        config['calories_burned_tef_calorie']: {'name': 'TEF Calories', 'icon': '🍽️'},
        config['goal_calories']: {'name': 'Goal Calories', 'icon': '🎯'}
    }
    
    for i, (col, value) in enumerate(metrics_data.items()):
        with cols[i]:
            config_info = metric_config.get(col, {'name': col, 'icon': '📊'})
            st.metric(
                label=f"{config_info['icon']} {config_info['name']}",
                value=f"{int(value):,}",
                help=f"Total {config_info['name'].lower()} for the day"
            )

def display_daily_charts(daily_data, config, selected_metrics):
    """Display daily breakdown charts"""
    st.subheader("📊 Daily Breakdown")
    
    # Prepare data for charts
    chart_data = []
    for _, row in daily_data.iterrows():
        for display_name, col_name in selected_metrics:
            if col_name in row and pd.notna(row[col_name]):
                chart_data.append({
                    'metric': display_name,
                    'calories': row[col_name],
                    'time': row[config['localized_time']]
                })
    
    if not chart_data:
        st.info("No detailed calorie data available for selected metrics")
        return
    
    df_chart = pd.DataFrame(chart_data)
    
    # Create two chart views
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart for calorie distribution
        pie_chart = alt.Chart(df_chart).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(field='calories', type='quantitative', stack=True),
            color=alt.Color(field='metric', type='nominal', 
                          legend=alt.Legend(title="Calorie Type")),
            tooltip=['metric', 'calories']
        ).properties(
            title='Calorie Distribution',
            height=300
        )
        
        st.altair_chart(pie_chart, use_container_width=True)
    
    with col2:
        # Bar chart by metric
        bar_chart = alt.Chart(df_chart).mark_bar().encode(
            x=alt.X('metric:N', title='Metric', axis=alt.Axis(labelAngle=0)),
            y=alt.Y('calories:Q', title='Calories'),
            color=alt.Color('metric:N', legend=None),
            tooltip=['metric', 'calories']
        ).properties(
            title='Calories by Type',
            height=300
        )
        
        st.altair_chart(bar_chart, use_container_width=True)
    
    # Time-based chart if we have multiple time points
    if len(daily_data) > 1:
        st.subheader("🕒 Hourly Calorie Burn")
        
        time_chart_data = []
        for _, row in daily_data.iterrows():
            for display_name, col_name in selected_metrics:
                if col_name in row and pd.notna(row[col_name]):
                    time_chart_data.append({
                        'metric': display_name,
                        'calories': row[col_name],
                        'hour': row[config['localized_time']].hour
                    })
        
        if time_chart_data:
            df_time = pd.DataFrame(time_chart_data)
            
            line_chart = alt.Chart(df_time).mark_line(point=True).encode(
                x=alt.X('hour:O', title='Hour of Day'),
                y=alt.Y('calories:Q', title='Calories'),
                color=alt.Color('metric:N', legend=alt.Legend(title="Metric")),
                tooltip=['hour', 'metric', 'calories']
            ).properties(
                height=300
            ).interactive()
            
            st.altair_chart(line_chart, use_container_width=True)

       
    
############ MAIN DASHBOARD #############
def show_dashboard(df_stress,df_hr,df_spo2,df_steps,df_calorie,supabase_client):
    p1_tab1,p1_tab2,p1_tab3,p1_tab4,p1_tab5 = st.tabs(['Stress Graph','Heart-Rate Graph','SpO2 Graph','Steps Graph','Calorie Graph'])

    configs = {
        "stress": {
            "title": "Stress",
            "daily_icon": "📆🧠",
            "hourly_icon": "⌚🧠",
            "localized_time": "localized_time",
            "time_offset": "time_offset",
            "value": "score",
            "value_bin": "score",
            "y_label": "Stress Level",
            "min": "score_min",
            "max": "score_max"
        },
        "hr": {
            "title": "Heart Rate",
            "daily_icon": "📆🫀",
            "hourly_icon": "⌚🫀",
            "localized_time": "localized_time",
            "time_offset": "heart_rate_time_offset",
            "value": "heart_rate_heart_rate",
            "value_bin": "heart_rate",
            "y_label": "Heart Rate",
            "min": "heart_rate_min",
            "max": "heart_rate_max"
        },
        "spo2": {
            "title": "SpO₂",
            "daily_icon": "📆🩸",
            "hourly_icon": "⌚🩸",
            "localized_time": "localized_time",
            "time_offset": "oxygen_saturation_time_offset",
            "value": "oxygen_saturation_spo2",
            "value_bin": "spo2",
            "y_label": "SpO₂",
            "min": "spo2_min",
            "max": "spo2_max"
        },
        "steps":{
            "title": "Steps",
            "daily_icon": "📆👟",
            "summary_icon": "📊👟",
            "hourly_icon": "⌚👟",
            "localized_time": "localized_time",
            "time_offset": "step_count_time_offset",
            "value": "step_count_count",
            "value_bin": "steps",
            "y_label": "Steps",
            "min": "steps_min",
            "max": "steps_max",
            "step_count_calorie":"step_count_calorie",
            "step_count_speed":"step_count_speed",
            "step_count_distance":"step_count_distance",
            "run_step":"run_step",
            "walk_step":"walk_step",
        },
        "calorie":{
            "title": "Calories",
            "daily_icon": "📆🍎",
            "localized_time": "localized_time",
            "date":"calories_burned_day_time",
            "time_offset": "+05:30",
            "y_label": "Calories",
            "goal_calories":"active_calories_goal",
            "total_exercise_calories":"total_exercise_calories",
            "calories_burned_tef_calorie":"calories_burned_tef_calorie",
            "calories_burned_active_time":"calories_burned_active_time",
            "calories_burned_rest_calorie":"calories_burned_rest_calorie",
            "calories_burned_active_calorie":"calories_burned_active_calorie",             
        }
    }

    render_metric_tab(p1_tab1,"stress",df_stress,configs["stress"],supabase_client)
    render_metric_tab(p1_tab2,"hr",df_hr,configs["hr"],supabase_client)
    render_metric_tab(p1_tab3,"spo2",df_spo2,configs["spo2"],supabase_client)
    render_metric_tab(p1_tab4,"steps",df_steps,configs["steps"],supabase_client)
    cal_tab(p1_tab5, "calorie", df_calorie, configs["calorie"], supabase_client)

def chartTimeData(df_og,xval,yval,xtitle,ytitle,chart_title,chart_type="line"):
    # defensive copy
    df = df_og.copy() if not df_og.empty else pd.DataFrame({xval: [], yval: []})

    # add metric title column for tooltip
    df["_metric_title"] = chart_title

    # datetime conversion
    df[xval] = pd.to_datetime(df[xval], errors="coerce")

    # apply offset if present
    offset_col = None
    for col in df.columns:
        if "time_offset" in col:
            offset_col = col
            break
    # if offset_col and not df.empty:
    #     df[xval] = df.apply(lambda row: apply_offset(row, offset_col, xval), axis=1)

    # base_date and forced x-domain for single-day view
    if df[xval].notna().any():
        base_date = df[xval].dt.date.min()
    else:
        base_date = datetime.date.today()
    x_domain = [
        datetime.datetime.combine(base_date, datetime.time(0, 0)),
        datetime.datetime.combine(base_date, datetime.time(23, 59, 59))
    ]

    # compute y-domain with optional min/max columns (e.g. heart_rate_min/heart_rate_max)
    ymin, ymax = None, None
    # try explicit min/max columns
    min_col = None
    max_col = None
    for c in df.columns:
        if c.endswith("_min") and c.startswith(yval.split("_")[0]):
            min_col = c
        if c.endswith("_max") and c.startswith(yval.split("_")[0]):
            max_col = c
    try:
        if min_col and max_col:
            ymin = float(df[min_col].min())
            ymax = float(df[max_col].max())
        else:
            ymin = float(df[yval].min()) if yval in df.columns and not df[yval].dropna().empty else None
            ymax = float(df[yval].max()) if yval in df.columns and not df[yval].dropna().empty else None
    except Exception:
        ymin, ymax = None, None

    if ymin is None or ymax is None or ymax == ymin:
        ymin = df[yval].min() if yval in df.columns and not df[yval].dropna().empty else 0
        ymax = df[yval].max() if yval in df.columns and not df[yval].dropna().empty else 1

    pad = (ymax - ymin) * 0.08 if (ymax - ymin) != 0 else max(abs(ymax), 1) * 0.1
    y_domain = [ymin - pad, ymax + pad]

    base = alt.Chart(df).encode(
        x=alt.X(xval, title=xtitle, scale=alt.Scale(domain=x_domain))
    )

    # build shared tooltip: Metric title, time, value, optional min/max
    tooltip_list = [
        alt.Tooltip(xval, title="Time", type="temporal", format="%I:%M %p"),
    ]
    if yval in df.columns:
        tooltip_list.append(alt.Tooltip(yval, title=ytitle, format=".2f"))
    if min_col in df.columns:
        tooltip_list.append(alt.Tooltip(min_col, title="Min", format=".2f"))
    if max_col in df.columns:
        tooltip_list.append(alt.Tooltip(max_col, title="Max", format=".2f"))

    nearest = alt.selection_point(on="mouseover", nearest=True, empty="none", fields=[xval])

    # choose visuals per chart_type
    if chart_type == "hr":
        band = None
        if min_col and max_col:
            band = base.mark_area(opacity=0.2, color="#c6dbef").encode(
                y=alt.Y(f"{min_col}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
                y2=alt.Y2(f"{max_col}:Q"),
                tooltip=tooltip_list
            )
        line = base.mark_line(interpolate="monotone", strokeWidth=2.5, color="#d62728").encode(
            y=alt.Y(f"{yval}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
            tooltip=tooltip_list
        )
        points = base.mark_circle(size=45, color="#d62728").encode(
            y=alt.Y(f"{yval}:Q"),
            opacity=alt.condition(nearest, alt.value(1.0), alt.value(0.0)),
            tooltip=tooltip_list
        ).add_selection(nearest)
        chart = (band + line + points) if band is not None else (line + points)
        # optional resting line
        if "heart_rate_custom" in df.columns and df["heart_rate_custom"].notna().any():
            resting_val = df["heart_rate_custom"].iloc[0]
            resting = alt.Chart(pd.DataFrame({})).mark_rule(color="green", strokeDash=[4,4]).encode(
                y=alt.Y(value=resting_val)
            )
            chart = chart + resting

    elif chart_type == "stress":
        band = None
        if f"{yval}_min" in df.columns and f"{yval}_max" in df.columns:
            band = base.mark_area(opacity=0.15, color="#fee6ce").encode(
                y=alt.Y(f"{yval}_min:Q", scale=alt.Scale(domain=y_domain)),
                y2=alt.Y2(f"{yval}_max:Q"),
                tooltip=tooltip_list
            )
        line = base.mark_line(interpolate="monotone", strokeWidth=2.2, color="#ff7f0e").encode(
            y=alt.Y(f"{yval}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
            tooltip=tooltip_list
        )
        points = base.mark_circle(size=40, color="#ff7f0e").encode(
            y=alt.Y(f"{yval}:Q"),
            opacity=alt.condition(nearest, alt.value(1.0), alt.value(0.0)),
            tooltip=tooltip_list
        ).add_selection(nearest)
        chart = (band + line + points) if band is not None else (line + points)

    elif chart_type == "spo2":
        line = base.mark_line(interpolate="monotone", strokeWidth=2.2, color="#1f77b4").encode(
            y=alt.Y(f"{yval}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
            tooltip=tooltip_list
        )
        points = base.mark_circle(size=40, color="#1f77b4").encode(
            y=alt.Y(f"{yval}:Q"),
            opacity=alt.condition(nearest, alt.value(1.0), alt.value(0.0)),
            tooltip=tooltip_list
        ).add_selection(nearest)
        chart = line + points

    elif chart_type == "steps":
        # bars + rolling mean line
        bars = base.mark_bar(color="#6a51a3").encode(
            y=alt.Y(f"{yval}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
            tooltip=tooltip_list
        )
        chart = bars.interactive()

    elif chart_type == "calorie":
        chart = base.mark_bar(color="#8c564b").encode(
            y=alt.Y(f"{yval}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
            tooltip=tooltip_list
        )

    else:
        # fallback line
        line = base.mark_line(interpolate="monotone", strokeWidth=2).encode(
            y=alt.Y(f"{yval}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
            tooltip=tooltip_list
        )
        points = base.mark_circle(size=40).encode(
            y=alt.Y(f"{yval}:Q"),
            opacity=alt.condition(nearest, alt.value(1.0), alt.value(0.0)),
            tooltip=tooltip_list
        ).add_selection(nearest)
        chart = line + points

    # add median rule for visual cue (if yval present)
    if yval in df.columns and not df[yval].dropna().empty:
        median_rule = alt.Chart(df).transform_aggregate(
            median_value=f"median({yval})"
        ).mark_rule(color="gray", strokeDash=[4,4]).encode(
            y=alt.Y("median_value:Q"),
            tooltip=[alt.Tooltip("median_value:Q", title="Median", format=".2f")]
        )
        chart = chart + median_rule

    chart = chart.properties(title=chart_title, width="container", height=320).configure_axis(
        labelFontSize=11, titleFontSize=12
    ).configure_title(fontSize=14, anchor="start").interactive()

    return chart

def loadBinningjsons(offset_col,jsonfilepath,supabase):    
    bucket_name = "json-bucket"
    file_path = jsonfilepath
    res = supabase.storage.from_(bucket_name).download(file_path)
    data = json.loads(res.decode("utf-8"))
    dfjson = pd.DataFrame(data)
    dfjson["start_time"] = pd.to_datetime(dfjson["start_time"],unit="ms")
    dfjson["end_time"] = pd.to_datetime(dfjson["end_time"],unit="ms")
    dfjson["offset_time"] = offset_col
    dfjson["start_time"] = dfjson.apply(lambda row: apply_offset(row,"offset_time","start_time"),axis =1)
    dfjson["end_time"] = dfjson.apply(lambda row: apply_offset(row,"offset_time","end_time"),axis =1)
    dfjson = dfjson.sort_values("start_time")
    return dfjson

def chartBinningjsons(dfJson,xval,xtitle,yval,ytitle,yminval,ymaxval):
    ### improved viz: smooth line, shaded band, hover tooltips, median rule, adaptive y-domain
    # compute y-domain safely
    try:
        ymin = float(dfJson[yminval].min()) if yminval in dfJson.columns else float(dfJson[yval].min())
        ymax = float(dfJson[ymaxval].max()) if ymaxval in dfJson.columns else float(dfJson[yval].max())
    except Exception:
        ymin, ymax = None, None

    if ymin is None or ymax is None or ymax == ymin:
        # fallback
        ymin = dfJson[yval].min() if yval in dfJson.columns else 0
        ymax = dfJson[yval].max() if yval in dfJson.columns else 1

    pad = (ymax - ymin) * 0.08 if (ymax - ymin) != 0 else max(abs(ymax),1) * 0.1
    y_domain = [ymin - pad, ymax + pad]

    # base encoding
    base = alt.Chart(dfJson).encode(
        x=alt.X(xval, title=xtitle, axis=alt.Axis(format="%I:%M %p")),
        tooltip=[
            alt.Tooltip(xval, title="Time", type="temporal", format="%I:%M %p"),
            alt.Tooltip(yval, title=ytitle),
            alt.Tooltip(yminval, title="Min"),
            alt.Tooltip(ymaxval, title="Max"),
        ]
    )

    # shaded min-max band
    band = base.mark_area(opacity=0.18, color="#9ecae1").encode(
        y=alt.Y(yminval, title=ytitle, scale=alt.Scale(domain=y_domain)),
        y2=alt.Y2(ymaxval),
        tooltip=[
            alt.Tooltip(xval, title="Time", type="temporal", format="%I:%M %p"),
            alt.Tooltip(yval, title=ytitle),
            alt.Tooltip(yminval, title="Min"),
            alt.Tooltip(ymaxval, title="Max"),
        ]
    )

    # smooth main line
    line = base.mark_line(interpolate="monotone", strokeWidth=2.5, color="#6a51a3").encode(
        y=alt.Y(f"{yval}:Q", title=ytitle, scale=alt.Scale(domain=y_domain)),
        tooltip=[
            alt.Tooltip(xval, title="Time", type="temporal", format="%I:%M %p"),
            alt.Tooltip(yval, title=ytitle),
            alt.Tooltip(yminval, title="Min"),
            alt.Tooltip(ymaxval, title="Max"),
        ]
    )

    # hover selection and highlight points
    nearest = alt.selection_point(on="mouseover", nearest=True, empty="none", fields=[xval])
    points = base.mark_circle(size=70, color="#6a51a3").encode(
        y=alt.Y(f"{yval}:Q"),
        opacity=alt.condition(nearest, alt.value(1.0), alt.value(0.0))
    ).add_selection(nearest)

    # median rule
    median_rule = alt.Chart(dfJson).transform_aggregate(
        median_value=f"median({yval})"
    ).mark_rule(color="gray", strokeDash=[4,4]).encode(
        y=alt.Y("median_value:Q"),
        tooltip=[alt.Tooltip("median_value:Q", title="Median", format=".2f")]
    )

    chartBin = (band + line + points + median_rule).properties(
        width="container",
        height=360,
        title=xtitle + " — " + ytitle
    ).configure_axis(
        labelFontSize=11,
        titleFontSize=12
    ).configure_title(
        fontSize=14,
        anchor="start"
    ).interactive()  # enable pan/zoom

    return chartBin
def apply_offset(row, offset_col, time_col):
    offset_val = row[offset_col]
    if pd.isnull(offset_val):
        return row[time_col]
    offset_str = str(offset_val)
    match = None
    # Accept both "UTC+0530" and "+05:30" formats
    if offset_str.startswith("UTC"):
        match = re.match(r"UTC([+-])(\d{2})(\d{2})", offset_str)
    else:
        match = re.match(r"([+-])(\d{2}):?(\d{2})", offset_str)
    if match:
        sign, hh, mm = match.groups()
        hours, minutes = int(hh), int(mm)
        delta = timedelta(hours=hours, minutes=minutes)
        if sign == "-":
            delta = -delta
        return row[time_col] + delta
    return row[time_col]