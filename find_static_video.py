import av
import numpy as np
import sys
from typing import Callable, List, Optional, NamedTuple
import matplotlib.pyplot as plt

Frame = av.VideoFrame

class Region(NamedTuple):
    start: float
    end: float
    score: Optional[float] = None

def validate_regions(
    filename: str,
    regions: List[Region],
    test_func: Callable[..., float],
    mode: str = "single",  # "single" or "pairwise"
    threshold: float = 0.95,
    sample_every: float = 1.0,
    verbose: bool = False,
    keep_if: str = "lt"  # "lt" for score < threshold, "gt" for score > threshold
) -> List[Region]:
    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]
    stream = container.streams.video[0]
    stream.thread_type = "AUTO"
    time_base = stream.time_base if stream.time_base else 1.0 / 25.0

    valid_segments = []

    for region_no, region in enumerate(regions):
        start, end = region.start, region.end
        if end <= start:
            if verbose:
                print(f"Skipping invalid region {region_no + 1}: {start:.2f}s to {end:.2f}s")
            continue

        if verbose:
            print(f"Validating region {region_no + 1}: {start:.2f}s to {end:.2f}s")

        container.seek(int(start / time_base), stream=stream)
        last_frame: Optional[Frame] = None
        last_pts_sec: Optional[float] = None

        scores = []

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

            if mode == "single":
                score = test_func(frame)
                scores.append(score)

            elif mode == "pairwise":
                if last_frame is not None:
                    score = test_func(last_frame, frame)
                    scores.append(score)
                last_frame = frame

        if scores:
            avg_score = float(np.mean(scores))
            region_with_score = Region(start, end, avg_score)

            if (keep_if == "lt" and avg_score >= threshold) or (keep_if == "gt" and avg_score <= threshold):
                continue

            valid_segments.append(region_with_score)

    return valid_segments

def validate_black_regions(
    filename: str,
    regions: List[Region],
    sample_every: float = 1.0,
    black_ratio: float = 0.95,
    verbose: bool = False
) -> List[Region]:
    return validate_regions(
        filename=filename,
        regions=regions,
        test_func=is_black_frame,
        mode="single",
        threshold=black_ratio,
        sample_every=sample_every,
        verbose=verbose,
        keep_if="lt"
    )

def is_frozen_frame(frame1: Frame, frame2: Frame, pixel_diff_threshold: float = 2.0) -> float:
    arr1 = frame1.to_ndarray(format='gray')
    arr2 = frame2.to_ndarray(format='gray')
    diff = np.abs(arr1.astype(np.int16) - arr2.astype(np.int16))
    mean_diff = float(np.mean(diff))
    return mean_diff

def validate_frozen_regions(
    filename: str,
    regions: List[Region],
    sample_every: float = 1.0,
    frozen_ratio: float = 0.95,
    verbose: bool = False
) -> List[Region]:
    return validate_regions(
        filename=filename,
        regions=regions,
        test_func=is_frozen_frame,
        mode="pairwise",
        threshold=frozen_ratio,
        sample_every=sample_every,
        verbose=verbose,
        keep_if="lt"
    )

def is_black_frame(frame: Frame, threshold: float = 10.0) -> float:
    gray = frame.to_ndarray(format='gray')
    mean_val = float(np.mean(gray))
    return mean_val

def detect_static_regions(filename, window_seconds=5, threshold=0.05) -> List[Region]:
    def packet_stat_func(packet_sizes: List[int]) -> float:
        return float(np.std(packet_sizes) / np.mean(packet_sizes))

    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]
    stream = container.streams.video[0]
    time_base = stream.time_base if stream.time_base else 1.0 / 25.0

    avg_fps = float(stream.average_rate or 25)
    window_size = int(window_seconds * avg_fps)

    frame_sizes = []
    frame_pts = []
    static_candidates = []

    for packet in container.demux(stream):
        if packet.dts is None:
            continue

        frame_sizes.append(packet.size)
        frame_pts.append(float(packet.dts * time_base))

        if len(frame_sizes) >= window_size:
            window = frame_sizes[-window_size:]
            std_dev = packet_stat_func(window)
            if std_dev < threshold:
                start = frame_pts[-window_size]
                end = frame_pts[-1]
                static_candidates.append(Region(start, end, std_dev))

            frame_sizes.pop(0)
            frame_pts.pop(0)

    merged = []
    for region in static_candidates:
        start, end, score = region
        if not merged:
            merged.append([start, end, score])
        else:
            last_start, last_end, last_score = merged[-1]
            if start <= last_end:
                merged[-1][1] = max(last_end, end)
            else:
                merged.append([start, end, score])

    return [Region(start, end, score) for start, end, score in merged]

def print_regions(regions: List[Region], title: str):
    print(f"\n{title}")
    if not regions:
        print("  (none found)")
    for region in regions:
        if region.score is not None:
            print(f"  {region.start:.2f}s to {region.end:.2f}s (score={region.score:.3f})")
        else:
            print(f"  {region.start:.2f}s to {region.end:.2f}s")

def display_thumbnails(title: str, filename: str, regions: List[Region], thumbs_per_row: int = 10):
    container = av.open(filename, mode='r')
    stream = container.streams.video[0]
    time_base = stream.time_base if stream.time_base else 1.0 / 25.0
    stream.thread_type = "AUTO"

    all_thumbs = []
    labels = []

    for region in regions:
        start, end = region.start, region.end
        score_text = f" ({region.score:.3f})" if region.score is not None else ""
        container.seek(int(start / time_base), stream=stream)
        thumbnails = []
        for frame in container.decode(stream):
            pts_sec = float(frame.pts * time_base)
            if pts_sec > end:
                break
            if pts_sec < start:
                continue
            thumbnails.append(frame.to_image())
            if len(thumbnails) >= thumbs_per_row:
                break
        all_thumbs.append(thumbnails)
        labels.append(f"{start:.2f}s – {end:.2f}s{score_text}")

    rows = len(all_thumbs)
    fig, axes = plt.subplots(rows, thumbs_per_row, figsize=(thumbs_per_row * 1.5, rows * 1.5))
    fig.suptitle(title, fontsize=16)

    for i, row_thumbs in enumerate(all_thumbs):
        for j in range(thumbs_per_row):
            ax = axes[i, j] if rows > 1 else axes[j]
            ax.axis('off')
            if j == 0:
                ax.set_title(labels[i], fontsize=10, loc='left')
            if j < len(row_thumbs):
                ax.imshow(row_thumbs[j])

    plt.tight_layout()
    plt.subplots_adjust(top=0.9)
    plt.show()

def main():
    if len(sys.argv) < 2:
        print("Usage: python find_static_frozen_video.py <video_file>")
        sys.exit(1)

    filename = sys.argv[1]
    print(f"Analyzing: {filename}")

    static_regions = detect_static_regions(filename, window_seconds=0.5, threshold=0.65)
    print_regions(static_regions, "Candidate static regions (based on encoded size):")

    frozen_regions = validate_frozen_regions(filename, static_regions, sample_every=0.25, frozen_ratio=0.85, verbose=True)
    print_regions(frozen_regions, "Confirmed frozen video regions (decoded content):")

    black_regions = validate_black_regions(filename, static_regions, sample_every=0.1, black_ratio=0.45, verbose=True)
    print_regions(black_regions, "Confirmed black static regions (decoded content):")

    display_thumbnails("Frozen regions", filename, frozen_regions, thumbs_per_row=10)
    display_thumbnails("Black regions", filename, black_regions, thumbs_per_row=10)

if __name__ == "__main__":
    main()
