


"""

Modify a list of numbers by replacing all negative values with 0 using continue.
"""


numbers = [0,4,2,1,-1,4,-6]

for number in numbers:
    if number < 0:
        continue
    print(number)