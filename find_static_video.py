import av
import av.container
import sys
import numpy as np

def detect_static_regions(filename, window_seconds:float=5, threshold=0.05):
    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]
    stream = container.streams.video[0]
    time_base = stream.time_base if stream.time_base else 1.0 / 25.0  # Default to 25 fps if no time base is set
    if time_base <= 0:
        raise ValueError("Invalid time base for the video stream.") 

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

            frame_sizes.pop(0)
            frame_pts.pop(0)

    # Merge overlapping windows
    merged = []
    for start, end in static_candidates:
        if not merged:
            merged.append([start, end])
        else:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1][1] = max(last_end, end)
            else:
                merged.append([start, end])

    return merged


# --- Example callback and runner below ---
def is_black_frame(frame, threshold=10):
    gray = frame.to_ndarray(format='gray')  # convert to grayscale
    return np.mean(gray) < threshold


def validate_black_regions(filename, regions, sample_every=1.0, black_ratio=0.95):
    
    # container = av.open(filename)
    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]

    stream = container.streams.video[0]
    stream.thread_type = "AUTO"
    time_base = stream.time_base

    black_segments = []

    for region_no,(start, end) in enumerate(regions):
        print(f"Validating region {region_no + 1}: {start:.2f}s to {end:.2f}s")
        if end <= start:
            print(f"Skipping invalid region {region_no + 1}: {start:.2f}s to {end:.2f}s")
            continue    
        container.seek(int(start / time_base), stream=stream)
        total_frames = 0
        black_frames = 0
        last_pts_sec = None

        for frame in container.decode(stream):
            if frame.pts is None:
                continue

            pts_sec = float(frame.pts * time_base)
            if pts_sec > end:
                break
            if pts_sec < start:
                continue

            # Avoid oversampling
            if last_pts_sec is not None and pts_sec - last_pts_sec < sample_every:
                continue
            last_pts_sec = pts_sec

            total_frames += 1
            if is_black_frame(frame):
                black_frames += 1

        if total_frames > 0 and (black_frames / total_frames) >= black_ratio:
            black_segments.append((start, end))

    return black_segments


def print_static_region(filename, start, end):
    print(f"Static region in {filename}: {start:.2f}s to {end:.2f}s")

if __name__ == "__main__":
    video_file = sys.argv[1]

    static_regions = detect_static_regions(video_file, window_seconds=1.0, threshold=0.85)
    black_regions = validate_black_regions(video_file, static_regions, sample_every=0.25, black_ratio=0.95)

    for start, end in black_regions:
        print(f"Black static region in {video_file}: {start:.2f}s to {end:.2f}s")
