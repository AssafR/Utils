from subprocess import Popen, PIPE
import sys
import re
import string
import time

def log(f,message):
   if f:
       f.write(message+ "\n");
       print(message+ "\n");

       
def parseTime(time):
    if (":" in time):
        hours, minutes = time.split(':')
        return int(hours) * 60 + int(minutes);
    return int(time);    

def send(command):
  log(f,"Going to send: " + command);
  pipe = Popen(command, stdout=PIPE, stderr=PIPE)
  while True:
     line = pipe.stdout.readline()
     if not line:
        break
     log(f,"Result=" + str(line) );

     
f = open('E:\\DriveE\\Downloads\\PVR\\code2.log','a') # Log file, to disable replace with: f=None
# "C:\Program Files (x86)\NPVR\schedule" -channel 3 -start now -seconds 60 -name "Max" -pre 0 -post 0
scheduler = "\"C:\\Program Files (x86)\\NPVR\\schedule\""
params = " -start now -name \"Max\" -pre 0 -post 0"
channelParam = " -channel "
lengthParam  = " -seconds "

args = sys.argv[1:] # Input parameter
with open(args[0]) as input:
    content = input.readlines()
content = [x.strip() for x in content]
times   = [parseTime(x) for x in content]

first_one = True;
for t in times:
  print("Time=" + str(t) + " min");
  if (t==0):
    channel=996
  else:
    if first_one:
        first_one = False;
        channel = 995;
    else:
        channel=997
  seconds = (t+2)*60
  len  = lengthParam  + str(seconds)
  chan = channelParam + str(channel)
  command = scheduler + params + chan + len
  send(command);
  wait_time = (seconds+90)
  print("Waiting " + str(wait_time))
  time.sleep(wait_time)
  