
sentence = "the hvac ran hvac problems damper the sensor the the stuck failed hvac fan problems pump sensor problems stuck failed crash fire hvac"

alarm_snapshot = [
    ("AHU-1 Supply Air Temp", "normal"),
    ("AHU-1 Filter Alarm", "active"),
    ("VAV-201 Zone Temp", "normal"),
    ("VAV-202 Damper Fault", "active"),
    ("Boiler-1 Low Water", "normal"),
    ("CH-1 Chilled Water Alarm", "active"),
]

fault_counts = {
    "high_supply_temp": 4,
    "filter_alarm": 2,
    "static_pressure_low": 7,
}