
"""


"""


while True:
    data = input("What numbers do you want to divide? (or type 'q' to quit): ")
    if data.lower() == 'q':
        break
    
    string_split = data.split()
    
    # Ensure we have enough input
    if len(string_split) < 2:
        print("Please enter two numbers separated by a space.")
        continue

    try:
        num1 = float(string_split[0]) # Use float for decimal support
        num2 = float(string_split[1])
        result = num1 / num2
        print(f"Result: {result}")
    except ValueError:
        print("These are not parsable numbers.")
    except ZeroDivisionError:
        print("Divide by zero error!")
