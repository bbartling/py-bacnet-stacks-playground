
import random

random_list = [random.randint(1, 100) for _ in range(50)]
print(random_list)


def find_min_max(data):
    max_val = data[0]
    min_val = data[0]
    min_index = 0
    max_index = 0
    for index,value in enumerate(data):
        if value >= max_val:
            max_val = value
            max_index = index
        if value <= min_val:
            min_val = value
            min_index = index

    return (min_val, min_index, max_val, max_index)
        


print(find_min_max(random_list))
print(max(random_list))
print(min(random_list))

