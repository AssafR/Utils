import hashlib
import os, os.path
import sys
import time
import shutil

def hashfile(afile, hasher, blocksize=65536):
	try:
		buf = afile.read(blocksize)
		while len(buf) > 0:
			hasher.update(buf)
			buf = afile.read(blocksize)
		return hasher.hexdigest()
	except OSError as ex:
		print("Error in hashing file ",afile)
		time.sleep(5)
		return 0

def encodefix(filename):
	return filename.encode(sys.stdout.encoding, errors='replace')

def hashequal(srcFile):
	if not (os.path.isfile(srcFile)):		
		return 0 
	dstFile = str.replace(srcFile,srcDir,dstDir)
	hash1=0
	hash2=0
	print("\n\n")
	try:	
		if not os.path.isfile(dstFile):
			if not os.path.exists(os.path.dirname(dstFile)):
				os.makedirs(os.path.dirname(dstFile))
			shutil.copyfile(srcFile, dstFile)
			print("Copied    ",encodefix(srcFile),"->",encodefix(dstFile))
			print("Comparing ",encodefix(srcFile),"| ",encodefix(dstFile))
			hash1 = hashfile(open(srcFile, 'rb'), hashlib.md5())
			hash2 = hashfile(open(dstFile, 'rb'), hashlib.md5())
	except OSError as ex:
		print("Error in hash =",ex.strerror)
		time.sleep(5)
		return 0
	if  (hash1!=0 and hash1==hash2):
		print("Same hash in files %s and %s [%s,%s]" % (encodefix(srcFile),encodefix(dstFile),hash1,hash2))
		return hash1 
	print("Different hashes for file %s and %s" % (encodefix(srcFile),encodefix(dstFile)));
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
				
def remove_files_in_iter(identical_files_iter):
	for f in identical_files_iter:
		try:
			os.remove(f)
			print("Removed file",encodefix(f))
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


srcDir = r'E:\\Drive_RAID\\Volume_1\\'
dstDir = r'R:\\'

# Usage: SrcDir, DstDir
srcDir,dstDir = sys.argv[1],sys.argv[2]
print("Moving from %s to %s  " % (srcDir, dstDir))

dirtocheck = srcDir
fileiter = (os.path.join(root, f)
	for root, _, files in os.walk(dirtocheck)
	for f in files)
	
smallfileiter = (f for f in fileiter if os.path.getsize(f) < 150000 * 1024 * 1024)
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