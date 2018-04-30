from subprocess import Popen, PIPE
import sys
import time

# Script to read a series of lines containing:
#  RecordingTime(hh:mm) Recording_Name(str)
# And sequentially send to a channel-change script + record using NPVR

CHANNEL_FOR_SKIPPING = 996
MINS_IN_HOUR = 60
CHANNEL_FOR_OTHER_RECORDINGS = 997
CHANNEL_FOR_FIRST_RECORDING = 995
EXTRA_MINUTES_RECORD = 2
DEFAULT_RECORDING_NAME = "Max"
DEFAULT_WAIT_EXTRA = 90
SCHEDULER_COMMAND = "\"C:\\Program Files (x86)\\NPVR\\schedule\""
SCHEDULER_PARAMS = " -start now -name \"%s\" -pre 0 -post 0"
CHANNEL_PARAMS = " -channel %d"
LENGTH_PARAMS = " -seconds %d"


def log(f, message):
    if f:
        f.write(message + "\n");
        print(message + "\n");


def parse_time_and_name(line):
    split_line = line.split()
    time = split_line[0]


    if (":" in time):
        hours, minutes = time.split(':')
        time_sec = int(hours) * MINS_IN_HOUR + int(minutes)
    else:
        time_sec = int(time)

    split_line[0] = time_sec
    return split_line;


def send(command):
    log(f, "Going to send: " + command);
    pipe = Popen(command, stdout=PIPE, stderr=PIPE)
    while True:
        line = pipe.stdout.readline()
        if not line:
            break
        log(f, "Result=" + str(line));


f = open('E:\\DriveE\\Downloads\\PVR\\code2.log', 'a')  # Log file, to disable replace with: f=None
# "C:\Program Files (x86)\NPVR\schedule" -channel 3 -start now -seconds 60 -name "Max" -pre 0 -post 0

args = sys.argv[1:]  # Input parameter
with open(args[0]) as input:
    content = input.readlines()
content = [x.strip() for x in content if x and (not x.isspace())]
times = [parse_time_and_name(x) for x in content]

first_one = True;
for time_name in times:
    recording_time = time_name[0]
    if (len(time_name) < 2):
        name = DEFAULT_RECORDING_NAME
    else:
        name = time_name[1]

    if first_one:
        first_one = False;
        channel = CHANNEL_FOR_FIRST_RECORDING
    else:
        channel = CHANNEL_FOR_OTHER_RECORDINGS

    seconds = (recording_time + EXTRA_MINUTES_RECORD) * MINS_IN_HOUR

    if (recording_time == 0):
        channel = CHANNEL_FOR_SKIPPING
        seconds = 10
        

    command = (SCHEDULER_COMMAND + SCHEDULER_PARAMS + CHANNEL_PARAMS + LENGTH_PARAMS) % (name, channel, seconds)
    print("Command=[" + command + "]")
    send(command);
    wait_time = (seconds + DEFAULT_WAIT_EXTRA)
    print("Waiting " + str(wait_time))
    time.sleep(wait_time)