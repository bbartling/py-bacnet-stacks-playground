
"""

Write a formatted string that prints the filename and size (in kilobytes) of a file using variables name and size.
"""



import os

# The filename
name = "site_scan.csv"

try:
    size_bytes = os.path.getsize(name)
    # Convert bytes to kilobytes (1 KB = 1024 bytes)
    size_kb = size_bytes / 1024
    formatted_string = f"Filename: {name}, Size: {size_kb:.2f} KB"

    # Print the formatted string
    print(formatted_string)
    
except FileNotFoundError:
    print(f"Error: The file '{name}' was not found.")
except PermissionError:
    print(f"Error: Insufficient permissions to access '{name}'.")

