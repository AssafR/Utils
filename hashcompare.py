import hashlib
import os, os.path
import sys
import time
import shutil
h
from threading import Thread

def hashfile(fileName, hasher, result, index, blocksize=65536):
	try:
		print("Calculating hash for index=%d, file=%s " % (index,encodefix(fileName)))
		afile = open(fileName, 'rb')
		buf = afile.read(blocksize)
		while len(buf) > 0:
			hasher.update(buf)
			buf = afile.read(blocksize)
		result[index] = hasher.hexdigest()
		print("Calculated  hash for index=%d, file=%s rseult=%s" % (index,encodefix(fileName),result[index]))
	except OSError as ex:
		print("Error in hashing file ",encodefix(fileName))
		time.sleep(5)
		result[index] = 0

def hashfiles(files):
	threads = [None] * len(files)
	results = [None] * len(files)

	for i in range(len(threads)):
		threads[i] = Thread(target=hashfile, args=(files[i], hashlib.md5(),results, i))
		threads[i].start()
	for i in range(len(threads)):
		threads[i].join()
	return results
		
def encodefix(filename):
	return filename.encode(sys.stdout.encoding, errors='replace')

def hashequal(srcFile):
	print("Comparing file",encodefix(srcFile));
	if not (os.path.isfile(srcFile)):
		print("Not path for file=",encodefix(srcFile));	
		return 0 
		
	dstFile = str.replace(srcFile,srcDir,dstDir)
	#if not (os.path.isfile(dstFile)):
		#print("Not file or exist for file=",encodefix(dstFile));	
		#return 0 
		
	hash1=0
	hash2=0
	print("\n\n")
	try:
		tries = 1
		hash1=0
		hash2=1
		while (tries<3 and ((not os.path.isfile(dstFile)) or (hash1 != hash2))):
			print("tries=",tries)
			if not os.path.exists(os.path.dirname(dstFile)):
				print("Creating directory")
				os.makedirs(os.path.dirname(dstFile))			
			print("Copying file ",encodefix(srcFile))
			#if (not os.path.isfile(dstFile)):
			#	shutil.copyfile(srcFile, dstFile)
			shutil.copyfile(srcFile, dstFile)
			shutil.copystat(srcFile, dstFile)
			print("Copied    ",encodefix(srcFile),"->",encodefix(dstFile))
			print("Comparing ",encodefix(srcFile),"| ",encodefix(dstFile))
			(hash1,hash2) = hashfiles([dstFile,srcFile])			
			tries= tries+1
	except OSError as ex:
		print("Filename: [" + encodefix(srcFile) + "->" + encodefix(dstFile) + "] ,Error in hash =",ex.strerror)
		time.sleep(5)
		return 0
	if  hash1!=0:
		if hash1==hash2:
			print("Same hash in files %s and %s [%s,%s]" % (encodefix(srcFile),encodefix(dstFile),hash1,hash2))
			return hash1
		print("Different hashes for file %s and %s [%s,%s]" % (encodefix(srcFile),encodefix(dstFile),hash1,hash2));
		return 0
	print("Hash = 0 file=",encodefix(srcFile));
	return 0;
	
def del_small_files(smallfileiter):
	for small in smallfileiter:
		try:
			os.remove(small)	
			print("Deleted file",encodefix(small))
		except OSError:
			print("Error deleting file",encodefix(small))
			time.sleep(5)

def delete_empty_and_stack(diriter):
	stack = []
	for dir in diriter:
		try:
			if not os.listdir(dir): # Empty dir
				os.rmdir(dir)
				print("deleted empty directory ", encodefix(dir))
			else:
				stack.append(dir)
				print("directory ", encodefix(dir)," not empty")
		except OSError as ex:
			if ex.errno == errno.ENOTEMPTY:
				print("directory ", encodefix(dir)," not empty")
	return stack

	
def filefilter(filename):
	print("Checking filename:*" + "*" +  "result=" + str(os.path.isfile(filename)));
	print(encodefix(filename));
	if os.path.isfile(filename):
		if os.path.getsize(filename) < 150000000 * 1024 * 1024:
			print("*** OK  size for file:",encodefix(filename))
			return True;
		else:
			print("file size too large, size=",os.path.getsize(filename));
	else:
		print("Not exist, file=",filename)
	print("*** BAD size for file:",encodefix(filename))
	return False;
				
def remove_files_in_iter(identical_files_iter):
	for f in identical_files_iter:
		try:
			os.remove(f)
			print("*** Removed file",encodefix(f))
		except OSError:
			print("Error Removing file",encodefix(f))
			time.sleep(5)
			
def delete_stack_order(stack):
	while stack:
		dir = stack.pop()
		try:
			if not os.listdir(dir):
				os.rmdir(dir)
				print("stack-delete directory ", encodefix(dir))
			else:
				print("directory ", encodefix(dir)," not empty")
		except OSError:
			print("Error stack-delete directory",encodefix(dir))
			time.sleep(5)
		
# U:\ -> E:\Drive_RAID\Volume_1\	
#def samefile(filename)	


#srcDir = r'E:\\Drive_RAID\\Volume_1\\'
srcDir = r'F:\\'
dstDir = r'X:\\'

# Usage: SrcDir, DstDir
srcDir,dstDir = sys.argv[1],sys.argv[2]
print("Moving from %s to %s  " % (srcDir, dstDir))

dirtocheck = srcDir
fileiter = (os.path.join(root, f)
	for root, _, files in os.walk(dirtocheck)
	for f in files)

	
smallfileiter = (f for f in fileiter if filefilter(f))
#del_small_files(smallfileiter)
identical_files_iter = (f for f in smallfileiter if hashequal(f))

remove_files_in_iter(identical_files_iter)

diriter = (os.path.join(root, d)
	for root, dirs , _ in os.walk(dirtocheck,topdown=False)
	for d in dirs)
stack = delete_empty_and_stack(diriter)
delete_stack_order(stack)
	
#fn = r'U:\assaf\20013.strip.print'
#fn2 = str.replace(fn,'U:\\','E:\\Drive_RAID\\Volume_1\\')
#fnamelst = [fn, fn2]
#print(fnamelst)

#hashes = [(fname,fname) for fname in fnamelst]	
#hash = hashfile(open(fn, 'rb'), hashlib.md5())
#hashes = [(fname, hashfile(open(fn, 'rb'), hashlib.md5())) for fname in fnamelst]

#print(hashes)