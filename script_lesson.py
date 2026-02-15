


"""

Combine split() and join() to reverse the order of words in a sentence.

"""



line = 'and observe the empty strings in the result'
fields = line.split()
fields.reverse()
final = " ".join(fields)
print(final)