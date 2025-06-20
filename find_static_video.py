import av
import numpy as np
import sys
from typing import Callable, List, Optional, Union
import matplotlib.pyplot as plt

from vid_utils import Frame, Region, all_tasks, detection_tasks, display_thumbnails, merge_overlapping_regions, print_regions, static_task

def iterate_frames(container, stream, time_base, region: Region, sample_every: float):
    container.seek(int(region.start / time_base), stream=stream)
    last_pts_sec = None
    last_frame = None

    for packet in container.demux(stream):
        for frame in packet.decode():
            if frame.pts is None:
                continue
            pts_sec = float(frame.pts * time_base)
            if pts_sec < region.start:
                continue
            if pts_sec > region.end:
                return
            if last_pts_sec is not None and pts_sec - last_pts_sec < sample_every:
                continue
            last_pts_sec = pts_sec
            yield frame, last_frame
            last_frame = frame

def process_regions(
    filename: str,
    regions: Optional[List[Region]] = None,
    packet_level: bool = False,
    stat_func: Optional[Callable[..., float]] = None,
    mode: str = "single",  # "single" or "pairwise"
    threshold: float = 0.95,
    sample_every: float = 1.0,
    verbose: bool = False,
    keep_if: str = "lt"  # "lt" for score < threshold, "gt" for score > threshold
) -> List[Region]:
    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]
    stream = container.streams.video[0]
    time_base = stream.time_base if stream.time_base else 1.0 / 25.0
    stream.thread_type = "AUTO"

    def keep(score: float) -> bool:
        return (keep_if == "lt" and score < threshold) or (keep_if == "gt" and score > threshold)

    results = []

    if packet_level:
        avg_fps = float(stream.average_rate or 25)
        window_size = int(sample_every * avg_fps)
        sizes = []
        pts = []

        for packet in container.demux(stream):
            if packet.dts is None:
                continue
            sizes.append(packet.size)
            pts.append(float(packet.dts * time_base))

            if len(sizes) >= window_size:
                window = sizes[-window_size:]
                score = stat_func(window) if stat_func else 0.0
                if keep(score):
                    start = pts[-window_size]
                    end = pts[-1]
                    results.append(Region(start, end, score))
                sizes.pop(0)
                pts.pop(0)

        final_merged = merge_overlapping_regions(results)
        return final_merged

    if not regions:
        raise ValueError("Frame-level validation requires input regions")

    for region_no, region in enumerate(regions):
        start, end = region.start, region.end
        if end <= start:
            if verbose:
                print(f"Skipping invalid region {region_no + 1}: {start:.2f}s to {end:.2f}s")
            continue
        if verbose:
            print(f"Validating region {region_no + 1}: {start:.2f}s to {end:.2f}s")

        scores = []
        for frame, last_frame in iterate_frames(container, stream, time_base, region, sample_every):
            if mode == "single" and stat_func is not None:
                scores.append(stat_func(frame))
            elif mode == "pairwise" and stat_func is not None and last_frame is not None:
                scores.append(stat_func(last_frame, frame))

        if scores:
            avg_score = float(np.mean(scores))
            if keep(avg_score):
                results.append(Region(start, end, avg_score))

    return results

def run_region_process(config: dict) -> List[Region]:
    return process_regions(
        filename=config["filename"],
        regions=config.get("regions"),
        packet_level=config.get("packet_level", False),
        stat_func=config["stat_func"],
        mode=config.get("mode", "single"),
        threshold=config.get("threshold", 0.95),
        sample_every=config.get("sample_every", 1.0),
        verbose=config.get("verbose", False),
        keep_if=config.get("keep_if", "lt")
    )

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <video_file>")
        sys.exit(1)

    filename = sys.argv[1]
    print(f"Analyzing: {filename}")

    task_results = {}

    for task in all_tasks:
        task["filename"] = filename

        if task["name"] == "Static Regions":
            task["regions"] = None
        else:
            task["regions"] = task_results.get("Static Regions")

        print(f"Running task: {task['name']}")
        regions = run_region_process(task)
        task_results[task["name"]] = regions

        print(f"Found {len(regions)} regions for task '{task['name']}'")
        print_regions(regions, task["name"] + ":")
        display_thumbnails(task["name"], filename, regions)

if __name__ == "__main__":
    main()
