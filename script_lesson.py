
"""

Given schedule = {'Mon': ['8am', '5pm'], 'Tue': ['9am', '6pm']}, loop through the dictionary and print the day along with the start and end times.
"""



schedule = {'Mon': ['8am', '5pm'], 'Tue': ['9am', '6pm']}

# Use .items() to get key-value pairs
for day, times in schedule.items():
    print(f"{day}: Start {times[0]}, End {times[1]}")
