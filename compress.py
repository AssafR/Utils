import sys;
import os;
import glob;
import subprocess;

batch = r"C:\Users\Razon\Desktop\mkv_to_Same.bat"
rootdir = "G:\\ToRecode\\"


def get_files_by_file_size(dirname, reverse=False):
    """ Return list of file paths in directory sorted by file size """

    # Get list of files
    filepaths = []
    for basename in os.listdir(dirname):
        filename = os.path.join(dirname, basename)
        if os.path.isfile(filename):
            filepaths.append(filename)

    # Re-populate list with filename, size tuples
    for i in xrange(len(filepaths)):
        filepaths[i] = (filepaths[i], os.path.getsize(filepaths[i]))

    # Sort list by file size
    # If reverse=True sort from largest to smallest
    # If reverse=False sort from smallest to largest
    filepaths.sort(key=lambda filename: filename[1], reverse=reverse)

    # Re-populate list with just filenames
    for i in xrange(len(filepaths)):
        filepaths[i] = filepaths[i][0]

    return filepaths
	
print("Start")

all_files = (os.path.join(basedir, filename) for basedir, dirs, files in os.walk(rootdir) for filename in files   )
sorted_files = sorted(all_files, key = os.path.getsize, reverse=True)

	
for file in sorted_files:
    if file.endswith(".ts"):
        command = batch + " " + "\"" + os.path.join(rootdir,"\\", file) + "\"";
        print("Executing " + command);
        subprocess.call(command);
		
		
	
