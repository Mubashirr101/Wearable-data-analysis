list1 = ["caffeine_intake", "device_profile", "food_info", "food_intake", "height", "movement", "nutrition", "user_profile", "water_intake", "weight", "activity_day_summary", "activity_level", "badge", "best_records", "breathing", "exercise", "exercise_custom_exercise", "exercise_hr_zone_settings", "exercise_periodization_training_program", "exercise_periodization_training_schedule", "exercise_recovery_heart_rate", "exercise_routine", "exercise_weather", "food_favorite", "food_frequent", "hsp_references", "insight_message_notification", "mood", "preferences", "service_preferences", "sleep", "sleep_goal", "social_leaderboard", "social_public_challenge", "social_public_challenge_history", "social_service_status", "step_daily_trend", "stress", "stress_histogram", "tracker_floors_day_summary", "tracker_heart_rate", "tracker_oxygen_saturation", "tracker_pedometer_day_summary", "tracker_pedometer_step_count"]

list2_raw = [
        "com.samsung.health.caffeine_intake.csv",
        "com.samsung.health.device_profile.csv",
        "com.samsung.health.food_info.csv",
        "com.samsung.health.food_intake.csv",
        "com.samsung.health.height.csv",
        "com.samsung.health.movement.csv",
        "com.samsung.health.nutrition.csv",
        "com.samsung.health.user_profile.csv",
        "com.samsung.health.water_intake.csv",
        "com.samsung.health.weight.csv",
        "com.samsung.shealth.activity.day_summary.csv",
        "com.samsung.shealth.activity_level.csv",
        "com.samsung.shealth.badge.csv",
        "com.samsung.shealth.best_records.csv",
        "com.samsung.shealth.breathing.csv",
        "com.samsung.shealth.exercise.csv",
        "com.samsung.shealth.exercise.custom_exercise.csv",
        "com.samsung.shealth.exercise.hr_zone.settings.csv",
        "com.samsung.shealth.exercise.periodization_training_program.csv",
        "com.samsung.shealth.exercise.periodization_training_schedule.csv",
        "com.samsung.shealth.exercise.recovery_heart_rate.csv",
        "com.samsung.shealth.exercise.routine.csv",
        "com.samsung.shealth.exercise.weather.csv",
        "com.samsung.shealth.food_favorite.csv",
        "com.samsung.shealth.food_frequent.csv",
        "com.samsung.shealth.hsp.references.csv",
        "com.samsung.shealth.insight.message_notification.csv",
        "com.samsung.shealth.mood.csv",
        "com.samsung.shealth.preferences.csv",
        "com.samsung.shealth.service_preferences.csv",
        "com.samsung.shealth.sleep.csv",
        "com.samsung.shealth.sleep_goal.csv",
        "com.samsung.shealth.social.leaderboard.csv",
        "com.samsung.shealth.social.public_challenge.csv",
        "com.samsung.shealth.social.public_challenge.history.csv",
        "com.samsung.shealth.social.service_status.csv",
        "com.samsung.shealth.step_daily_trend.csv",
        "com.samsung.shealth.stress.csv",
        "com.samsung.shealth.stress.histogram.csv",
        "com.samsung.shealth.tracker.floors_day_summary.csv",
        "com.samsung.shealth.tracker.heart_rate.csv",
        "com.samsung.shealth.tracker.oxygen_saturation.csv",
        "com.samsung.shealth.tracker.pedometer_day_summary.csv",
        "com.samsung.shealth.tracker.pedometer_step_count.csv"
    ]

def normalize(entry):
    entry = entry.replace("com.samsung.health.", "")
    entry = entry.replace("com.samsung.shealth.", "")
    entry = entry.replace(".csv", "")
    return entry.replace(".", "_")

# Normalize list2
list2_normalized = set(normalize(item) for item in list2_raw)
list1_set = set(list1)

# print(len(list1))
# print(len(list2_raw))
# # Comparison
# missing_from_list2 = list1_set - list2_normalized
# extra_in_list2 = list2_normalized - list1_set

# print("In list1 but not in list2:", missing_from_list2)
# print("In list2 but not in list1:", extra_in_list2)

for list in sorted(list1):
    print(list)
