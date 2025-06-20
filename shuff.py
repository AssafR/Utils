import random
import itertools;
from datetime import datetime


#from random import shuffle
class MyList(list):
	def __init__(self, *args):
		super(MyList, self).__init__(args)

	def __sub__(self, other):
		return self.__class__(*[item for item in self if item not in other])
		

random.seed(datetime.now())
people = [
['\u05D0\u05D5\u05E8 \u05E8\u05D5\u05D6\u05E0\u05E9\u05D8\u05D9\u05D9\u05DF','\u05E7','warlordkittens@yahoo.com'], 	#1 OR
['\u05D4\u05D3\u05E8 \u05E4\u05E8\u05D1\u05E8\u05DE\u05DF','\u05D5','hadar0123@gmail.com'], 						#2 Hadar Farberman
['\u05E9\u05E8\u05D5\u05E0\u05D4 \u05E8\u05D0\u05D5\u05D1\u05E0\u05D9','\u05D1','raisinlike@gmail.com'],   			#3 Sharona
['\u05D0\u05D9\u05D4 \u05E8\u05D5\u05D6\u05DF','\u05E8','ayarosen@gmail.com'],  									#4 Aya
['\u05E8\u05D5\u05EA\u05D9 \u05D3\u05DF','\u05D8','rutiledan@gmail.com'], 											#5 Ruti
['\u05E8\u05D7\u05DC\u05D9 \u05D0\u05D4\u05E8\u05D5\u05E0\u05D5\u05E3','\u05D7','rachea02@gmail.com'],				#6 Racheli
['\u05E2\u05D3\u05D9 \u05D0\u05DC\u05E7\u05D9\u05DF','\u05DC','Angwen@gmail.com'],									#7 # Adi Elkin
['\u05E2\u05D3\u05D9 \u05DC\u05D5\u05D9\u05D4','\u05DB','falcore42@gmail.com'],										#8 # Adi L
#['\u05EA\u05DE\u05E8 \u05E0\u05D5\u05D9\u05D2\u05E8\u05D8\u05DF \u05E4\u05D5\u05DC\u05D2\u05E8','\u05E0','tamari@gmail.com'], # 9 Tamar
#['Hila','saintlola@gmail.com'],																					#12 Hila
['Maayan Arbel', 'maayan.moo@gmail.com'], 																			#14 Maayan Arbel
#['Dafna Rosencwyg', 'doollik@gmail.com'] 																			#15 Dafna Rosencwyg
]


MAX_EQUALS = 2
lastId = 15
absent = [9, 10, 11, 12, 13, 15]


# 1 2 3 4 5 6 8 9 13 (Missing: 10,11,12).
# 2016-1:
# Sharona cannot have Aya, Adi Loya, Adi Elkin
# Sharona, Farberman, Racheli , Or, Aya, Tamar, Ruthi Dan, Loya, Elkin
# 1 2 3 4 5 6 7 8 9   
# 2017-06-27
# 1 2 3 4 6 7 8 9 12 15
# Forbidden Pairs:
# 2017-04-29
# 1 2 3 4 5 6 7 8 14
ForbiddenPairs = [
[3,4],
[3,7],
[3,8],
[1,4],
[1,7],
#[1,8],
[14,1] # No Maayan->Or
]


def createpairs():
	number1 = [x+1 for x in range(lastId)] # 1 to 15
	number2 = [item for item in number1 if item not in absent]
	number3 = list(number2)  # Clone list
	random.shuffle(number2)  # Shuffle list 

	pairs = []

	pairs=[ [number3[i] ,number2[i]] for i in range(len(number2))]
	#for i in range(len(number1)):
	 # pairs.append( [number1[i],number2[i]]) # Pair of corresponding elements from both lists
	print("Pairs=",pairs)
	return pairs;

OldPairs = [[10,5],
[9,8],
[7,10],
[5,5],
[6,9],
[4,3],
[3,4],
[8,1],
[10,8],
[1,10],
[3,6],

[8,7], # Loya got Elkin
[5,2], # Ruthi got Farberman
[11,10],
[10,4],
[9,3], # Tamar got Sharona
[7,1],
[4,5],
[6,8],
#[1,6],
[2,11],
[3,9],
# 16/3:
[5,12], #  Ruti got Hila
[8, 5], # Adi L got Ruthi
[7,4], # Adi E got Aya
[10,7],
[9, 8], # Tamar got Adi L
[12,10], # Hila got Hammutal
[3,6],
[6,3],
[4,1],
[1,9],

[1, 5], [2, 1], [3, 2], [4, 6], [5, 8], [6, 4], [8, 9], [9, 13], [13, 3],

#2016-09-20 
[7,3],[8,5], [4,7],[5,6],[12,1],

#2017-01-14
[1, 7], [2, 5], [3, 1], [4, 8], [5, 9], [6, 12], [7, 2], [8, 14], [9, 6], [12, 3], [14, 4],

#2017-06-27
[1, 12], [2, 6], [3, 15], [4, 2], [6, 1], [7, 8], [8, 3], [9, 4], [12, 7], [15, 9],

#2017-04-29
#[[1, 3], [2, 4], [3, 12], [4, 9], [6, 15], [7, 6], [8, 2], [9, 1], [12, 8], [15, 7]],


]
'''
25/4: 
[[1, 5], [2, 1], [3, 2], [4, 6], [5, 8], [6, 4], [8, 9], [9, 13], [13, 3]]




6	1
11	2
9	3
5	4
2	5
8	6
1	7
7	8
3	9
4	10
10	11

[[1, 8], [2, 3], [3, 7], [4, 9], [5, 6], [6, 2], [7, 5], [8, 4], [9, 1]]


'''

equals = 0
foundequal=True
while(foundequal):
	foundequal=False
	pairs = createpairs()
	for pair in pairs:
		for oldpair in (OldPairs + ForbiddenPairs):
			if ((pair == oldpair) or (pair[0] == pair[1])):
				print("equality!",pair,oldpair, " equals=",equals)
				equals = equals +1 
				if (equals>=MAX_EQUALS):
					foundequal=True
					equals = 0;
					print("Starting over")
					continue


print("Found pairs!")
print(pairs)
for pair in pairs:
	print(pair)
	print(people[pair[1]])