import sys
import re
pattern = re.compile(r'(.*)(success[ ]*)([0-9]+)')  #re.compile(r'(.*)(Results:[ ]*)([0-9]+)') #'
start_pattern = 'General Queries Summary' # '*** Results Summary ***'
end_pattern = 'End General Queries Summary-' # '-----'

def only_lines(log):
	inside=False;
	for line in log:
		if (start_pattern in line):
			inside=True;
			continue;
		if (inside and end_pattern in line):
			inside=False;
			continue;
		if inside:
			match = pattern.search(line)
			if not match:
				continue;
			groups = match.groups();
			if (groups and len(groups)> 2):
				yield (groups[0] + groups[1] + groups[2])
			
def lines_as_integer(lines):
	for line in lines:
		match = pattern.search(line).groups()
		if (len(match)> 2):
			yield int(match[2])
			
args = sys.argv[1:] # Input parameter
with open(args[0]) as input:
    content = [line.rstrip() for line in input.readlines()]

if (len(args)>1 and args[1]=='-o'):
	for line in only_lines(content):
		print(line)
elif (len(args)>1 and args[1]=='-os'):
	for line in sorted(only_lines(content)):
		print(line)
else:
	print("Sum="+ str(sum(lines_as_integer(only_lines(content)))))