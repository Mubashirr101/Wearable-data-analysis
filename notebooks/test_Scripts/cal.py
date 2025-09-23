# def cal_tab(tab, metric_name, df, config, supabase_client=None):
#     with tab:
#         st.header(f"{config.get('daily_icon','📆')} {config['title']} Dashboard")
        
#         # ---------- View Toggle (Week/Month) ----------
#         col1, col2 = st.columns([3, 1])
#         with col2:
#             view_type = st.radio(
#                 "View Type",
#                 ["Week View", "Month View"],
#                 horizontal=True,
#                 key=f"{metric_name}_view_type"
#             )
        
#         # ---------- Prepare Data ----------
#         df_cal = df.copy()
#         if not df_cal.empty:
#             # Convert to datetime and apply offset
#             df_cal[config["start_time"]] = pd.to_datetime(df_cal[config["start_time"]], errors="coerce")
#             df_cal[config["date"]] = pd.to_datetime(df_cal[config["date"]], errors="coerce")
            
#             # Apply time offset
#             df_cal[config["start_time"]] = df_cal.apply(
#                 lambda row: apply_offset(row, config['time_offset'], config['start_time']), 
#                 axis=1
#             )
#             df_cal[config["date"]] = df_cal.apply(
#                 lambda row: apply_offset(row, config['time_offset'], config['date"]), 
#                 axis=1
#             )
        
#         # ---------- Chart Section ----------
#         st.subheader("Calorie Trends")
        
#         # Available calorie features for toggling
#         calorie_features = [
#             "calories_burned_rest_calorie",
#             "calories_burned_active_calorie", 
#             "total_exercise_calories",
#             "calories_burned_tef_calories",
#             "goal_calories"
#         ]
        
#         # Filter to only include features that exist in dataframe
#         available_features = [f for f in calorie_features if f in df_cal.columns]
        
#         # Feature selection
#         col3, col4 = st.columns([2, 1])
#         with col4:
#             selected_features = st.multiselect(
#                 "Select Calorie Metrics to Display",
#                 options=available_features,
#                 default=available_features[:2] if len(available_features) >= 2 else available_features,
#                 key=f"{metric_name}_feature_select"
#             )
        
#         if not df_cal.empty and selected_features:
#             # Aggregate data based on view type
#             if view_type == "Week View":
#                 df_agg = df_cal.set_index(config["date"]).resample('W').sum(numeric_only=True).reset_index()
#                 x_title = "Week"
#             else:  # Month View
#                 df_agg = df_cal.set_index(config["date"]).resample('M').sum(numeric_only=True).reset_index()
#                 x_title = "Month"
            
#             # Create interactive line chart with selected features
#             chart_data = df_agg.melt(
#                 id_vars=[config["date"]],
#                 value_vars=selected_features,
#                 var_name='Calorie Type',
#                 value_name='Calories'
#             )
            
#             # Color scheme for different calorie types
#             color_scheme = alt.Scale(
#                 domain=selected_features,
#                 range=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57']
#             )
            
#             line_chart = alt.Chart(chart_data).mark_line(point=True, strokeWidth=3).encode(
#                 x=alt.X(f'{config["date"]}:T', title=x_title, axis=alt.Axis(format='%b %Y')),
#                 y=alt.Y('Calories:Q', title='Calories', scale=alt.Scale(zero=False)),
#                 color=alt.Color('Calorie Type:N', scale=color_scheme, legend=alt.Legend(title="Calorie Types")),
#                 tooltip=[
#                     alt.Tooltip(f'{config["date"]}:T', title=x_title, format='%b %Y'),
#                     'Calorie Type:N',
#                     alt.Tooltip('Calories:Q', format='.0f')
#                 ]
#             ).properties(
#                 width='container',
#                 height=400,
#                 title=f"Calorie Trends - {view_type}"
#             ).interactive()
            
#             st.altair_chart(line_chart, use_container_width=True)
            
#             # ---------- Summary Statistics ----------
#             st.subheader("Summary Statistics")
#             if view_type == "Week View":
#                 latest_data = df_agg.iloc[-1] if len(df_agg) > 0 else None
#                 if latest_data is not None:
#                     col5, col6, col7, col8 = st.columns(4)
#                     with col5:
#                         st.metric("Total Weekly Calories", f"{latest_data[selected_features].sum():.0f}")
#                     with col6:
#                         st.metric("Active Calories", f"{latest_data.get('calories_burned_active_calorie', 0):.0f}")
#                     with col7:
#                         st.metric("Resting Calories", f"{latest_data.get('calories_burned_rest_calorie', 0):.0f}")
#                     with col8:
#                         goal = latest_data.get('goal_calories', 0)
#                         actual = latest_data[selected_features].sum()
#                         progress = min((actual / goal) * 100, 100) if goal > 0 else 0
#                         st.metric("Goal Progress", f"{progress:.1f}%")
        
#         # ---------- Expandable Calendar Section ----------
#         with st.expander("📅 Daily Calorie Details", expanded=True):
#             st.subheader("Daily Calorie Analysis")
            
#             # Calendar date selection
#             col9, col10 = st.columns([1, 2])
#             with col9:
#                 if not df_cal.empty:
#                     min_date = df_cal[config["date"]].min().date()
#                     max_date = df_cal[config["date"]].max().date()
#                     selected_date = st.date_input(
#                         "Select Date",
#                         value=max_date,
#                         min_value=min_date,
#                         max_value=max_date,
#                         key=f"{metric_name}_calendar"
#                     )
#                 else:
#                     selected_date = st.date_input("Select Date", key=f"{metric_name}_calendar")
            
#             # Filter data for selected date
#             if not df_cal.empty and selected_date:
#                 daily_data = df_cal[df_cal[config["date"]].dt.date == selected_date]
                
#                 if not daily_data.empty:
#                     # ---------- Daily Metrics Row ----------
#                     st.subheader(f"Daily Summary - {selected_date}")
                    
#                     # Calculate daily totals
#                     daily_totals = {}
#                     for feature in available_features:
#                         if feature in daily_data.columns:
#                             daily_totals[feature] = daily_data[feature].sum()
                    
#                     total_calories = sum(daily_totals.values())
#                     goal_calories = daily_totals.get('goal_calories', 0)
                    
#                     # Display metrics in columns
#                     metric_cols = st.columns(4)
#                     with metric_cols[0]:
#                         st.metric("Total Calories", f"{total_calories:.0f}")
#                     with metric_cols[1]:
#                         active_cals = daily_totals.get('calories_burned_active_calorie', 0)
#                         st.metric("Active Calories", f"{active_cals:.0f}")
#                     with metric_cols[2]:
#                         rest_cals = daily_totals.get('calories_burned_rest_calorie', 0)
#                         st.metric("Resting Calories", f"{rest_cals:.0f}")
#                     with metric_cols[3]:
#                         if goal_calories > 0:
#                             progress = min((total_calories / goal_calories) * 100, 100)
#                             st.metric("Daily Goal", f"{progress:.1f}%")
#                         else:
#                             st.metric("Daily Goal", "N/A")
                    
#                     # ---------- Daily Charts ----------
#                     st.subheader("Daily Breakdown")
                    
#                     # Pie chart for calorie distribution
#                     if len(daily_totals) > 1:
#                         pie_data = pd.DataFrame([
#                             {'Type': 'Active', 'Calories': daily_totals.get('calories_burned_active_calorie', 0)},
#                             {'Type': 'Resting', 'Calories': daily_totals.get('calories_burned_rest_calorie', 0)},
#                             {'Type': 'Exercise', 'Calories': daily_totals.get('total_exercise_calories', 0)},
#                             {'Type': 'TEF', 'Calories': daily_totals.get('calories_burned_tef_calories', 0)}
#                         ])
                        
#                         pie_chart = alt.Chart(pie_data[pie_data['Calories'] > 0]).mark_arc().encode(
#                             theta=alt.Theta(field="Calories", type="quantitative"),
#                             color=alt.Color(field="Type", type="nominal", 
#                                          scale=alt.Scale(range=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])),
#                             tooltip=['Type', 'Calories']
#                         ).properties(
#                             title="Calorie Distribution",
#                             width=300,
#                             height=300
#                         )
                        
#                         # Bar chart for comparison
#                         bar_chart = alt.Chart(pie_data[pie_data['Calories'] > 0]).mark_bar().encode(
#                             x=alt.X('Type:N', title='Calorie Type'),
#                             y=alt.Y('Calories:Q', title='Calories'),
#                             color=alt.Color('Type:N', 
#                                          scale=alt.Scale(range=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4'])),
#                             tooltip=['Type', 'Calories']
#                         ).properties(
#                             title="Calorie Breakdown",
#                             width=400,
#                             height=300
#                         )
                        
#                         chart_col1, chart_col2 = st.columns([1, 2])
#                         with chart_col1:
#                             st.altair_chart(pie_chart, use_container_width=True)
#                         with chart_col2:
#                             st.altair_chart(bar_chart, use_container_width=True)
                    
#                     # ---------- Time-based calorie data if available ----------
#                     if config["start_time"] in daily_data.columns:
#                         st.subheader("Hourly Calorie Trends")
                        
#                         # Prepare hourly data
#                         hourly_data = daily_data.set_index(config["start_time"]).resample('H').sum(numeric_only=True).reset_index()
                        
#                         if not hourly_data.empty:
#                             # Create area chart for hourly trends
#                             area_chart = alt.Chart(hourly_data).transform_fold(
#                                 selected_features,
#                                 as_=['Calorie Type', 'Calories']
#                             ).mark_area(opacity=0.7).encode(
#                                 x=alt.X(f'{config["start_time"]}:T', title='Time', axis=alt.Axis(format='%H:%M')),
#                                 y=alt.Y('Calories:Q', title='Calories', stack=True),
#                                 color=alt.Color('Calorie Type:N', scale=color_scheme),
#                                 tooltip=[
#                                     alt.Tooltip(f'{config["start_time"]}:T', title='Time', format='%H:%M'),
#                                     'Calorie Type:N',
#                                     alt.Tooltip('Calories:Q', format='.0f')
#                                 ]
#                             ).properties(
#                                 width='container',
#                                 height=400,
#                                 title="Hourly Calorie Burn"
#                             ).interactive()
                            
#                             st.altair_chart(area_chart, use_container_width=True)
                    
#                     # ---------- Detailed Data Table ----------
#                     with st.expander("📊 Detailed Data"):
#                         display_cols = [config["date"]] + available_features
#                         display_df = daily_data[display_cols].copy()
#                         st.dataframe(display_df.style.format({
#                             col: "{:.0f}" for col in available_features if col in display_df.columns
#                         }))
                
#                 else:
#                     st.info(f"No calorie data available for {selected_date}")
#             else:
#                 st.info("Please select a date to view daily details")
        
#         if df_cal.empty:
#             st.info("No calorie data available for the selected period")