import streamlit as st
import streamlit as st
import pandas as pd
import numpy as np
import os,json
import datetime
import re
from datetime import timedelta
import altair as alt

session = st.session_state
for k in session.keys():
    session[k] = session[k]


def render_metric_tab(tab, metric_name, df, config, supabase_client=None):
    ## Renders the metric tab including daily and hourly charts.
    ## For 'steps', also renders summary chart from steps_summary.source_info JSON.
    ## Skips hourly chart for steps if summary is displayed.    
    with tab:
        col1, col2 = st.columns([4, 2])
        col1.header(f"{config.get('daily_icon','📆')} Daily {config['title']} Chart")

        # ---------- Date filter ----------
        date_filter = col2.date_input(
            f'{metric_name}_Date',
            key=f"{metric_name}_date_filter",
            label_visibility="hidden"
        )

        if date_filter:
            df_filtered = df[df[config["start_time"]].dt.date == pd.to_datetime(date_filter).date()].copy()
            st.session_state[f"df_{metric_name}_filtered"] = df_filtered
        else:
            df_filtered = df.iloc[0:0]

        # ---------- Daily chart ----------
        chart_type_map = {
            'hr': 'hr',
            'stress': 'stress',
            'spo2': 'spo2',
            'steps': 'steps',
            'calorie': 'calorie'
        }
    


        chart_daily = chartTimeData(
            df_filtered,
            config["start_time"],
            config["value"],
            "Time/Date",
            config["y_label"],
            f"{config.get('daily_icon','📆')} {config['title']} over Time",
            chart_type=chart_type_map.get(metric_name, 'line')
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
                df_steps[config["start_time"]] = pd.to_datetime(df_steps[config["start_time"]], errors="coerce")
                df_steps = df_steps.sort_values(config["start_time"])
                # daily aggregates (resample by day)
                try:
                    daily = df_steps.set_index(config["start_time"]).resample("D").agg({
                        config["value"]: "sum",
                        "run_step": "sum" if "run_step" in df_steps.columns else "mean",
                        "walk_step": "sum" if "walk_step" in df_steps.columns else "mean",
                        "step_count_speed": "mean" if "step_count_speed" in df_steps.columns else "mean",
                        "step_count_distance": "sum" if "step_count_distance" in df_steps.columns else "sum",
                        "step_count_calorie": "sum" if "step_count_calorie" in df_steps.columns else "sum",
                    }).reset_index()
                except Exception:
                    # fallback simple groupby day
                    df_steps["day"] = df_steps[config["start_time"]].dt.date
                    daily = df_steps.groupby("day").agg({
                        config["value"]: "sum",
                        "run_step": "sum" if "run_step" in df_steps.columns else "mean",
                        "walk_step": "sum" if "walk_step" in df_steps.columns else "mean",
                        "step_count_speed": "mean" if "step_count_speed" in df_steps.columns else "mean",
                        "step_count_distance": "sum" if "step_count_distance" in df_steps.columns else "sum",
                        "step_count_calorie": "sum" if "step_count_calorie" in df_steps.columns else "sum",
                    }).reset_index().rename(columns={"day": config["start_time"]})

                with st.expander("Advanced charts — detailed steps features", expanded=True):
                    # summary metrics
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    mcol1.metric("Total steps (day)", int(daily[config["value"]].sum()))
                    mcol2.metric("Total Calories Burnt (day)", int(daily[config["step_count_calorie"]].sum()))
                    mcol3.metric("Avg speed (day)", int(daily[config["step_count_speed"]].mean()))
                    mcol4.metric("Total distance (m)", round(daily.get("step_count_distance", pd.Series([0])).sum(), 2))

                    # Row 1: stacked run/walk per day + rolling steps line
                    r1c1, r1c2 = st.columns([2,3])
                    # stacked run/walk
                    if {"run_step","walk_step"}.issubset(df_steps.columns):
                        # fold in pandas so Altair has concrete dtypes
                        folded = daily[[config["start_time"], "run_step", "walk_step"]].melt(
                            id_vars=[config["start_time"]],
                            value_vars=["run_step", "walk_step"],
                            var_name="type",
                            value_name="count"
                        ).dropna(subset=["count"])
                        folded["type"] = folded["type"].astype(str)
                        folded["count"] = pd.to_numeric(folded["count"], errors="coerce").fillna(0)

                        stacked = alt.Chart(folded).mark_bar().encode(
                            x=alt.X(config["start_time"], title="Date", axis=alt.Axis(format="%Y-%m-%d")),
                            y=alt.Y("count:Q", title="Count"),
                            color=alt.Color("type:N"),
                            tooltip=[config["start_time"], alt.Tooltip("type:N"), alt.Tooltip("count:Q")]
                        ).properties(title="Run vs Walk counts per day")
                        r1c1.altair_chart(stacked, use_container_width=True)
                    else:
                        r1c1.info("run_step / walk_step not available in this dataset")

                    # steps with rolling mean
                    df_steps_time = df_steps[[config["start_time"], config["value"]]].dropna().copy()
                    if not df_steps_time.empty:
                        df_steps_time = df_steps_time.set_index(config["start_time"]).resample("h").sum().reset_index()
                        df_steps_time["rolling_3h"] = df_steps_time[config["value"]].rolling(3, min_periods=1).mean()
                        steps_line = alt.Chart(df_steps_time).encode(
                            x=alt.X(config["start_time"], title="Time"),
                        )
                        line = steps_line.mark_line(color="purple").encode(
                            y=alt.Y(config["value"], title="Steps"),
                            tooltip=[config["start_time"], config["value"]]
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
                            tooltip=[config["start_time"], "step_count_speed", "step_count_distance", config["value"]]
                        ).interactive().properties(title="Speed vs Distance (points colored by run_step if available)")
                        r2c1.altair_chart(scatter, use_container_width=True)
                    else:
                        r2c1.info("Speed/distance data not available.")

                    # histogram of step counts
                    hist = alt.Chart(df_steps.dropna(subset=[config["value"]])).mark_bar().encode(
                        x=alt.X(f"{config['value']}:Q", bin=alt.Bin(maxbins=40), title="Step count"),
                        y=alt.Y("count()", title="Frequency"),
                        tooltip=[alt.Tooltip(f"{config['value']}:Q")]
                    ).properties(title="Distribution of step_count_count")
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
                            tooltip=[config["start_time"], config["value"], "step_count_calorie"]
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
                    df_copy['start_time'] = df_copy.apply(lambda row: apply_offset(row, config['time_offset'], config['start_time']), axis=1)
                    match = df_copy.loc[df_copy["start_time"].dt.time == time_filter]
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



        
    
############ MAIN DASHBOARD #############
def show_dashboard(df_stress,df_hr,df_spo2,df_steps,supabase_client):
    p1_tab1,p1_tab2,p1_tab3,p1_tab4,p1_tab5 = st.tabs(['Stress Graph','Heart-Rate Graph','SpO2 Graph','Steps Graph','Calorie Graph'])

    configs = {
        "stress": {
            "title": "Stress",
            "daily_icon": "📆🧠",
            "hourly_icon": "⌚🧠",
            "start_time": "start_time",
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
            "start_time": "heart_rate_start_time",
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
            "start_time": "oxygen_saturation_start_time",
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
            "start_time": "step_count_start_time",
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
        }
        # to add steps, calorie later with same structure
    }

    render_metric_tab(p1_tab1,"stress",df_stress,configs["stress"],supabase_client)
    render_metric_tab(p1_tab2,"hr",df_hr,configs["hr"],supabase_client)
    render_metric_tab(p1_tab3,"spo2",df_spo2,configs["spo2"],supabase_client)
    render_metric_tab(p1_tab4,"steps",df_steps,configs["steps"],supabase_client)


def chartTimeData(df,xval,yval,xtitle,ytitle,chart_title,chart_type="line"):
    # defensive copy
    df = df.copy() if not df.empty else pd.DataFrame({xval: [], yval: []})

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
    if offset_col and not df.empty:
        df[xval] = df.apply(lambda row: apply_offset(row, offset_col, xval), axis=1)

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

def apply_offset(row,offset_col,time_col):
    ## extract offset from the offset feature
    offset_val = row[offset_col]
    if pd.isnull(offset_val):
        return row[offset_col]
    offset_str = str(offset_val)
    match = re.match(r"UTC([+-])(\d{2})(\d{2})",offset_str)
    if match:
        sign,hh,mm = match.groups()
        hours,minutes = int(hh),int(mm)
        delta = timedelta(hours=hours,minutes=minutes)
        if sign == "-":
            delta = -delta
        ## shift time
        return row[time_col]+delta
    return row[time_col]

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
