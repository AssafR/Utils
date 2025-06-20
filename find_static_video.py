import av
import sys
import numpy as np

def detect_static_regions(filename, callback, window_seconds=5, threshold=0.05):
    container = av.open(filename,mode='r')
    stream = container.streams.video[0]
    time_base = stream.time_base

    frame_sizes = []
    frame_pts = []

    avg_fps = float(stream.average_rate or 25)
    window_size = int(window_seconds * avg_fps)

    for packet in container.demux(stream):
        if packet.dts is None:
            continue

        frame_sizes.append(packet.size)
        frame_pts.append(float(packet.dts * time_base))

        if len(frame_sizes) >= window_size:
            window = frame_sizes[-window_size:]
            std_dev = np.std(window) / np.mean(window)
            if std_dev < threshold:
                start = frame_pts[-window_size]
                end = frame_pts[-1]
                callback(filename, start, end)

            frame_sizes.pop(0)
            frame_pts.pop(0)

# --- Example callback and runner below ---

def print_static_region(filename, start, end):
    print(f"Static region in {filename}: {start:.2f}s to {end:.2f}s")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python static_scene_detector.py <video_file>")
        sys.exit(1)

    video_file = sys.argv[1]
    detect_static_regions(video_file, print_static_region, window_seconds=1, threshold=0.5)
    print("Static scene detection completed."   )
