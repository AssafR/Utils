import av
import sys
import numpy as np

def detect_static_regions(filename, callback, window_seconds=5, threshold=0.05):
    container = av.open(filename, mode='r')
    stream = container.streams.video[0]
    time_base = stream.time_base

    frame_sizes = []
    frame_pts = []

    avg_fps = float(stream.average_rate or 25)
    window_size = int(window_seconds * avg_fps)

    static_candidates = []

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
                static_candidates.append((start, end))

            # Move window forward by 1 frame
            frame_sizes.pop(0)
            frame_pts.pop(0)

    # Merge overlapping or adjacent candidates
    merged = []
    for start, end in static_candidates:
        if not merged:
            merged.append([start, end])
        else:
            last_start, last_end = merged[-1]
            if start <= last_end:  # Overlapping or touching
                merged[-1][1] = max(last_end, end)
            else:
                merged.append([start, end])

    # Emit merged regions
    for start, end in merged:
        callback(filename, start, end)

# --- Example callback and runner below ---

def print_static_region(filename, start, end):
    print(f"Static region in {filename}: {start:.2f}s to {end:.2f}s")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python find_static_video.py <video_file>")
        sys.exit(1)

    video_file = sys.argv[1]
    detect_static_regions(video_file, print_static_region, window_seconds=0.5, threshold=0.5)
    print("Static scene detection completed.")
