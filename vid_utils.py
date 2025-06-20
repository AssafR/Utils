from typing import NamedTuple, List, Optional
import av
from matplotlib import pyplot as plt

class Region(NamedTuple):
    start: float
    end: float
    score: Optional[float] = None

Frame = av.VideoFrame
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


