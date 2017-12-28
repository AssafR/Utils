import sys;
import os;

rootdir = u'D:\\mp3'
dirs = [dir for dir in os.listdir(rootdir) if os.path.isdir(os.path.join(rootdir,dir))];
for dir in dirs:
    #print(unicode(dir, "utf-8", errors="ignore"))
        num = [ord(c) for c in dir]
        asc = [chr(n) for n in num]
        str = ''.join(chr(i) for i in num)
        sys.stdout.buffer.write((bytes(str,'iso-8859-8'))) # .decode('UTF-8'))
        #sys.stdout.buffer.write   print(' '.join(asc))
        #print(str)
        print('------------')    
        