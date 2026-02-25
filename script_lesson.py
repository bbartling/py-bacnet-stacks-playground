


"""
Create a text file notes.txt and append a new timestamped note each time the script runs.
Read a configuration file line by line and ignore blank lines or lines starting with # (comments).
"""


with open('site_scan.csv', 'r', newline='', encoding='utf-8') as f:
    count = 0
    for line in f:
        if count == 5:
            break
        print(line.strip())
        count += 1


