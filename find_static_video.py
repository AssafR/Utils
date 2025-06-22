import av
import av.container, av.packet, av.stream
import numpy as np
import sys
from typing import Callable, List, Optional, Union, Iterator, Tuple
from fractions import Fraction
import matplotlib.pyplot as plt

from vid_utils import Frame, Region, all_tasks, display_thumbnails, merge_overlapping_regions, print_regions, static_task

def in_region(pts_sec, regions):
    # Check if pts_sec is within any of the specified regions
    # If no regions are specified, return True (i.e., include all pts_sec)
    if not regions:
        return True
    return any(r.start <= pts_sec <= r.end for r in regions)


def iterate_video_return_packets(
    container:av.container.InputContainer,
    time_base,
    regions: Optional[List[Region]] = None,
)->Iterator[Tuple[float, av.packet.Packet, int]]:
    missing_counter = 0
    for packet in container.demux(container.streams.video[0]): 
        if packet.dts is None:
            continue
        pts_sec = float(packet.dts * time_base)
        if in_region(pts_sec,regions):
            yield pts_sec, packet, missing_counter
            missing_counter = 0
        else:
            missing_counter += 1

def create_regions_from_packets_by_size_filter(
    packet_data: Iterator[Tuple[float, av.packet.Packet, int]],
    time_base: Fraction |float,
    min_size: int = 1000,
) -> Iterator[Region]:

    regions = []
    current_start = None
    current_end = None
    current_size = 0
    num_packets = 0

    for pts_sec, packet, missing_counter in packet_data:
        current_start = pts_sec if current_start is None else current_start      
        current_end = pts_sec if current_end is None else current_end
        if packet.size < min_size: # Accumulate packets that are smaller than the minimum size
            current_size += packet.size
            num_packets += 1
            continue

        print(f"# If we have a packet that violates the size requirement, size={packet.size}, finalize the current region")
        if current_size > 0:
            print(f"** Yielding region from {current_start} to {current_end}, size={current_size}, num_packets={num_packets}")
            yield Region(current_start, current_end, current_size / num_packets)
        else:
            print(f"  Warning: No packets in region {current_start} - {current_end} with size {current_size}")
        # Reset for the next region
        current_start = pts_sec 
        current_end = None
        current_size = 0
        num_packets = 0

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


    for packet in container.demux(stream):
        if not decode:
            if packet.dts is None:
                continue
            pts_sec = float(packet.dts * time_base)
            if in_region(pts_sec,regions):
                pts.append(pts_sec)
                sizes.append(packet.size)
                yield (pts, sizes, None, None)  # Dummy return for uniformity
            continue

        for frame in packet.decode():
            if frame.pts is None:
                continue
            pts_sec = float(frame.pts * time_base)
            if not in_region(pts_sec,regions):
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
        pts = frame.pts if frame is not None else 1/25.0
        pts_sec = float(pts * time_base)
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

    container: av.container.InputContainer = av.open(filename, mode='r')  # type: ignore[assignment]
    container_stream = container.streams.video[0]
    time_base = container_stream.time_base if container_stream.time_base else 1.0 / 25.0
    regions = [Region(1,1.3, 0.0), Region(4.0, 4.2, 0.0)]  # Example regions

    print(f"Using regions: {regions}")

    # for (pts_sec, packet,missing_counter) in iterate_video_return_packets(container,time_base,regions):
    #     print(f"Packet PTS: {pts_sec}, Size: {packet.size}, Missing Counter: {missing_counter}")

    container: av.container.InputContainer = av.open(filename, mode='r')  # Reopening stream and container
    print(f"Using regions again: {regions}") # Doesn't work if container is exhausted ?
    frame_iterator = iterate_video_return_packets(container,time_base,regions)

    for region in create_regions_from_packets_by_size_filter(frame_iterator, time_base, min_size=100):
        print(f"Region: {region.start} - {region.end}, Size: {region.score}")
    

    # for task in all_tasks:
    #     task["filename"] = filename

    #     if task["name"] == "Static Regions":
    #         task["regions"] = None
    #     else:
    #         task["regions"] = task_results.get("Static Regions")

    #     print(f"Running task: {task['name']}")
    #     regions = run_region_process(task)
    #     task_results[task["name"]] = regions

    #     print(f"Found {len(regions)} regions for task '{task['name']}'")
    #     print_regions(regions, task["name"] + ":")
    #     display_thumbnails(task["name"], filename, regions)

if __name__ == "__main__":
    main()
