# from converter import Converter
import moviepy.editor as mp
import pydub
import numpy as np
import scipy.io.wavfile as wav


def read(f, normalized=False):
    """MP3 to numpy array"""
    a = pydub.AudioSegment.from_file(f)
    y = np.array(a.get_array_of_samples())
    if a.channels == 2:
        y = y.reshape((-1, 2))
    if normalized:
        return a.frame_rate, np.float32(y) / 2 ** 15
    else:
        return a.frame_rate, y


input_file = r'T:\Cassettes Customers\Tom\Phase 14\Sample.mkv'

# read the audio from input video file

audio: np.array
rate: int

rate, audio = read(input_file)
print("rate: ", rate)
print("audio: ", audio.mean(axis=0))
b = audio[1:10000,:]
b = b - b.mean(axis=0)
c = abs(b)
