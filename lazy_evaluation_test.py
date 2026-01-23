call_counts = 0


def myfunc():
    global call_counts
    print('       Calling function')
    call_counts = call_counts + 1
    return call_counts

my_dict = {
    'a':myfunc, 
    'b':myfunc
    }

y = (str(fnc()) for fnc in my_dict.values())

print("Starting the code")
print("About to check y")
print('   y=',y)
print("about to check the values inside y")
print('  Values (first  round) are:',','.join(y))
print('  Values (second round) are:',','.join(y))
