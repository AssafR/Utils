import hashlib
import os, os.path
from threading import Thread

def hashfile(fileName, hasher, result, index, blocksize=65536):
	try:
		afile = open(fileName, 'rb')
		buf = afile.read(blocksize)
		while len(buf) > 0:
			hasher.update(buf)
			buf = afile.read(blocksize)
		result[index] = hasher.hexdigest()
	except OSError as ex:
		print("Error in hashing file ",afile)
		time.sleep(5)
		result[index] = 0

		
dirtocheck = r"H:\\0077 - Humor - Mad TV, Smack the pony, Colin Quinn - CD"
fileiter = (os.path.join(root, f)
	for root, _, files in os.walk(dirtocheck)
	for f in files)

for file in fileiter:	
	threads = [None] * 2
	results = [None] * 2

	for i in range(len(threads)):
		threads[i] = Thread(target=hashfile, args=(file, hashlib.md5(),results, i))
		threads[i].start()
	for i in range(len(threads)):
		threads[i].join()
	
	for i in range(len(results)):
		print("file: %d , hash: %s" % (i,results[i]))
