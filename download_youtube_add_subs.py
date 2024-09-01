# Description: Download a youtube video and add subtitles to it
#   The subtitles are downloaded from the youtube video and added to the video
#   The video is downloaded to a destination folder
#   The subtitles are downloaded to the same destination folder
#   The video and subtitles are combined into a new video with the subtitles
#   The new video is saved to the destination folder


from pytube import YouTube
from pytube.helpers import safe_filename, deprecated
from pathlib import Path, PureWindowsPath
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter
from pytube import extract

import ffmpeg

from captions import Caption

# URL = 'https://www.youtube.com/watch?v=t4vrx9Z0oL0'
URL = 'https://www.youtube.com/watch?v=h46WcligwCo'
DESTINATION_FOLDER = r'C:\Users\Assaf\Desktop\Temporary'


def get_pytube_caption_by_language(captions, language):
    caption = captions.get(language, captions.get('a.' + language, None))
    return caption


@deprecated("Use get_srt_captions_with_transcript_api instead, due to bug in pytube, until it's fixed")
def get_srt_captions_with_pytube(youtube_url, languages=['en']):
    # cap = get_pytube_caption_by_language(youtube_obj.captions, 'en')
    # youtube_obj.set_filename(target_vid_filename)
    # caption = Caption(cap)
    # downloading the subtitles
    # target_srt_filename = caption.download(
    #     title=title,
    #     srt=True,
    #     output_path=DESTINATION_FOLDER
    # )
    return None


def get_srt_captions_with_transcript_api(youtube_url, languages=['en']):
    try:
        # Get the transcript
        youtube_id = extract.video_id(youtube_url)
        srt = YouTubeTranscriptApi.get_transcript(youtube_id, languages=languages)

        formatter = SRTFormatter()
        srt_output = formatter.format_transcript(srt)
        return srt_output
    except Exception as e:
        print(f"Error in getting the captions for {youtube_url}")
        return None


# noinspection PyBroadException
def download_youtube_add_subs(url, destination_folder):
    try:
        # creating YouTube object using YouTube
        youtube_obj = YouTube(url)
    except Exception as e:
        print(f"Connection Error - cannot download video for url {url}")  # to handle exception
        return None, None

    # filters out all the files with "mp4" extension
    mp4files = (youtube_obj.streams
                .filter(file_extension='mp4')
                .filter(progressive=True)
                )
    # to set the name of the file
    title = safe_filename(youtube_obj.title)
    target_vid_filename = title + '.mp4'
    target_srt_filename = title + '.srt'
    dest_path = Path(destination_folder)
    full_name_video = str(dest_path / target_vid_filename)
    full_name_srt = str(dest_path / target_srt_filename)

    print(youtube_obj.thumbnail_url)
    # get the video with the extension and
    # resolution passed in the get() function
    # d_video = youtube_obj.get(mp4files[-1].extension, mp4files[-1].resolution)
    version_to_download = mp4files.get_by_resolution('720p')
    try:
        # downloading the video
        target_vid_filename = version_to_download.download(
            output_path=dest_path,
            filename=target_vid_filename
        )
        print('Task is Completed! File saved at:  ' + full_name_video)
    except Exception as e:
        print("Error in download stage!")
        full_name_video = None

    try:
        srt_subs = get_srt_captions_with_transcript_api(url)
        with open(full_name_srt, 'w') as f:
            f.write(srt_subs)
        print('Task is Completed! File saved at:  ' + full_name_srt)
    except Exception as e:
        print(f"Error in writing subtitles to file {full_name_srt}!")
        full_name_srt = None
    return full_name_video, full_name_srt

def create_video_with_subtitles_using_ffmpeg(video_filename, subtitles_filename):
    pass
    # srt_filename_encoded = str(Path(PureWindowsPath(srt_filename)))
    # srt_filename_encoded = f'"{srt_filename_encoded}"'
    #
    # # stream = ffmpeg.input(vid_filename)
    # # a1 = stream.audio
    # # # stream = ffmpeg.hflip(stream)
    # #
    # # print(srt_filename_encoded)
    # # #stream = stream.filter('subtitles', 'Trump Claims Hes Been Treated Worse Than Abraham Lincoln.srt')
    # # # x = 'C\:\\\\Users\\\\Assaf\\\\Desktop\\\\Temporary\\\\Trump Claims Hes Been Treated Worse Than Abraham Lincoln_flipped.mp4'
    # # print(PureWindowsPath(srt_filename))
    # # # C\\:\\\\Python27\\\\lib\\\\site-packages\\\\efesto_review\\\\resource\\\\luts\\\\Cineon-to-SLog.3dl
    # srt_filename = r'C:\t.srt'
    # # stream = stream.filter('subtitles', srt_filename)
    # # stream = ffmpeg.output(stream, a1, vid_filename.replace('.mp4', '_flipped.mp4'))
    # # ffmpeg.run(stream)
    #
    # path_converter = lambda path: (path
    #                                .replace("\\", "/")
    #                                # .replace(":", "\:/")
    #                                # .replace(" ", "\\ ")
    #                                # .replace("(", "\\(")
    #                                # .replace(")", "\\)")
    #                                # .replace("[", "\\[")
    #                                # .replace("]", "\\]")
    #                                # .replace("'", "'\\''")
    #                                )
    #
    # x = "C:/Users/Assaf/Desktop/Temporary/Trump Claims Hes Been Treated Worse Than Abraham Lincoln.srt"
    # unix_like_srt_filename = f"'{x}'"
    #
    # # r'''C:/Users/Assaf/Desktop/Temporary/Trump Claims Hes Been Treated Worse Than Abraham Lincoln.srt'''
    # print(unix_like_srt_filename)
    # output_with_subs = vid_filename.replace('.mp4', '_subs.mp4')
    #
    # print(srt_filename)
    # # ffmpeg_command = (
    # #     ffmpeg.input(vid_filename)
    # #     .video.filter('subtitles', srt_filename)
    # #     .output(vid_filename.replace('.mp4', '_subs.mp4'))
    # #  )
    #
    #
    # input = ffmpeg.input(vid_filename)
    # video = input.video.filter_('subtitles', path_converter(unix_like_srt_filename))
    # audio = input.audio
    # ffmpeg_command = ffmpeg.concat(video, audio, v=1, a=1).output(output_with_subs)
    #
    # args = ffmpeg_command.get_args()
    # args_str = '    ' + '\n    '.join(args)
    # try:
    #     ffmpeg_command.run()
    # finally:
    #     print(f'----\nArgs:\n {args_str}\n------')


    # ffmpeg -i input.mp4 -vf subtitles=subtitle.srt output_srt.mp4


# Command line:
#   ffmpeg -i video.avi -vf subtitles=subtitle.srt out.avi
#   ffmpeg -i input.mp4 -vf subtitles=subtitle.srt output_srt.mp4
create = False
if create:
    vid_filename, srt_filename = download_youtube_add_subs(URL, DESTINATION_FOLDER)
else:
    # vid_filename = r'C:\Users\Assaf\Desktop\Temporary\Trump Claims Hes Been Treated Worse Than Abraham Lincoln.mp4'
    # srt_filename = r'C:\Users\Assaf\Desktop\Temporary\Trump Claims Hes Been Treated Worse Than Abraham Lincoln.srt'
    vid_filename = r'C:\Users\Assaf\Desktop\Temporary\Taylor Swift Urges Fans To Vote  Michelle Obama Isn’t Running  Bezos Is Richer Than Musk.mp4'
    srt_filename = r'C:\Users\Assaf\Desktop\Temporary\Taylor Swift Urges Fans To Vote  Michelle Obama Isn’t Running  Bezos Is Richer Than Musk.srt'

print(f'{vid_filename}\n{srt_filename}')
create_video_with_subtitles_using_ffmpeg(vid_filename, srt_filename)