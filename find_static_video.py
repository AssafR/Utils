import av
import numpy as np
import sys
from typing import Callable, List, Optional, Union
import matplotlib.pyplot as plt

from vid_utils import Frame, Region, all_tasks, display_thumbnails, merge_overlapping_regions, print_regions, static_task

def iterate_video(
    container,
    stream,
    time_base,
    regions: Optional[List[Region]] = None,
    sample_every: float = 1.0,
    decode: bool = True
):
    last_pts_sec = None
    last_frame = None
    pts = []
    sizes = []

    def in_region(pts_sec):
        if not regions:
            return True
        return any(r.start <= pts_sec <= r.end for r in regions)

    for packet in container.demux(stream):
        if not decode:
            if packet.dts is None:
                continue
            pts_sec = float(packet.dts * time_base)
            if in_region(pts_sec):
                pts.append(pts_sec)
                sizes.append(packet.size)
                yield (pts, sizes, None, None)  # Dummy return for uniformity
            continue

        for frame in packet.decode():
            if frame.pts is None:
                continue
            pts_sec = float(frame.pts * time_base)
            if not in_region(pts_sec):
                continue
            if last_pts_sec is not None and pts_sec - last_pts_sec < sample_every:
                continue
            last_pts_sec = pts_sec
            yield (None, None, frame, last_frame)
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
        all_pts = []
        all_sizes = []

        for pts, sizes, _, _ in iterate_video(container, stream, time_base, decode=False):
            if pts is None or sizes is None:
                continue
            all_pts.extend(pts)
            all_sizes.extend(sizes)

            if len(all_sizes) >= window_size:
                window = all_sizes[-window_size:]
                score = stat_func(window) if stat_func else 0.0
                if keep(score):
                    start = all_pts[-window_size]
                    end = all_pts[-1]
                    results.append(Region(start, end, score))
                all_sizes.pop(0)
                all_pts.pop(0)

        return merge_overlapping_regions(results)

    if not regions:
        raise ValueError("Frame-level validation requires input regions")

    region_map = {region: [] for region in regions}

    for _, _, frame, last_frame in iterate_video(container, stream, time_base, regions=regions, sample_every=sample_every, decode=True):
        pts_sec = float(frame.pts * time_base)
        for region in regions:
            if region.start <= pts_sec <= region.end:
                if mode == "single" and stat_func is not None:
                    region_map[region].append(stat_func(frame))
                elif mode == "pairwise" and stat_func is not None and last_frame is not None:
                    region_map[region].append(stat_func(last_frame, frame))
                break

    for region, scores in region_map.items():
        if scores:
            avg_score = float(np.mean(scores))
            if keep(avg_score):
                results.append(Region(region.start, region.end, avg_score))

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
