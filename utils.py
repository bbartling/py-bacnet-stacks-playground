





data = ['ZoneTemp,72', 'ZoneFlow,450', 'ZoneHumidity,45']

with open('sensors.csv', 'w', encoding='utf-8') as f:
    for line in data:
        f.write(line + '\n')


with open('sensors.csv', 'r', encoding='utf-8') as f:
    contents = f.read()
print(contents)

with open('sensors.csv', 'r', encoding='utf-8') as f:
    for line in f:
        print(line.strip())


with open('sensors.csv', 'a', encoding='utf-8') as f:
    f.write('ZonePressure,1.2\n')


import csv
from datetime import date

filename = 'sensors_' + str(date.today()) + '.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['point', 'value', 'units'])
    writer.writerow(['ZoneTemp', 72.4, 'degF'])