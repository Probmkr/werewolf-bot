from db import DBC

db = DBC()

for i in db.for_test():
    print(i)
    for j in i:
        print(j)
