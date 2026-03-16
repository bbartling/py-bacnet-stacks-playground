


"""

Write a function all_in_range(readings, low, high) that returns True if every reading is between low and high inclusive.
Write a function any_alarm(readings, threshold) that returns True if any reading exceeds the threshold.

"""


def any_alarm(readings, high):

    is_between_low_and_high = False
    for i in range(len(readings)):
        if readings[i] >= high:
            is_between_low_and_high = True
    return is_between_low_and_high


temperatures = [42.4, 422.34, 45.3, 43.2]
ALARM = 50.0

check = any_alarm(temperatures, ALARM)

print(check)