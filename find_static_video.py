import av
import numpy as np
import sys

def detect_static_regions(filename,  window_seconds:float=5.0, threshold=0.05):
    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]
    stream = container.streams.video[0]
    time_base = stream.time_base if stream.time_base else 1.0 / 25.0  # Default to 25 fps if no time base is set
    if time_base <= 0:
        raise ValueError("Invalid time base for the video stream.") 
    stream.thread_type = "AUTO"
    # Initialize lists to store frame sizes and presentation timestamps
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

    # Merge overlapping or adjacent windows
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

def is_frozen_frame(frame1, frame2, pixel_diff_threshold=2.0):
    arr1 = frame1.to_ndarray(format='gray')
    arr2 = frame2.to_ndarray(format='gray')
    diff = np.abs(arr1.astype(np.int16) - arr2.astype(np.int16))
    mean_diff = np.mean(diff)
    return mean_diff < pixel_diff_threshold

def validate_frozen_regions(filename, regions, sample_every=1.0, frozen_ratio=0.9):
    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]
    stream = container.streams.video[0]
    time_base = stream.time_base
    stream.thread_type = "AUTO"

    frozen_segments = []

    for start, end in regions:
        container.seek(int(start / time_base), stream=stream)
        last_frame = None
        frozen_count = 0
        total_pairs = 0
        last_pts_sec = None

        for frame in container.decode(stream):
            if frame.pts is None:
                continue

            pts_sec = float(frame.pts * time_base)
            if pts_sec > end:
                break
            if pts_sec < start:
                continue

            if last_pts_sec is not None and pts_sec - last_pts_sec < sample_every:
                continue
            last_pts_sec = pts_sec

            if last_frame is not None:
                total_pairs += 1
                if is_frozen_frame(last_frame, frame):
                    frozen_count += 1
            last_frame = frame

        if total_pairs > 0 and (frozen_count / total_pairs) >= frozen_ratio:
            frozen_segments.append((start, end))

    return frozen_segments

def print_regions(regions,headline):
    print(f"\n{headline}:")
    if not regions:
        print("  No regions found.")
        return
    for start, end in regions:
        print(f"  {start:.2f}s to {end:.2f}s")

def main():
    if len(sys.argv) < 2:
        print("Usage: python find_static_frozen_video.py <video_file>")
        sys.exit(1)

    filename = sys.argv[1]
    print(f"Analyzing: {filename}")

    static_regions = detect_static_regions(filename, window_seconds=0.5, threshold=0.95)
    print_regions(static_regions,"Candidate static regions (based on encoded size):")

    frozen_regions = validate_frozen_regions(filename, static_regions, sample_every=0.25, frozen_ratio=0.85)
    print_regions(static_regions,"Confirmed frozen video regions (decoded content):")



if __name__ == "__main__":
    main()
