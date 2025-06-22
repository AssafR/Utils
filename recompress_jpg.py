import sys
import os
import subprocess
from PIL import Image
import tempfile
import shutil


# ==== Configuration ====
CJPEG_PATH = r"E:\DriveE\Downloads\Utils\mozjpeg\mozjpeg_4.1.1_x64\static\tools\cjpeg.exe"        # Use full path if not in system PATH
EXIFTOOL_PATH = r"C:\ProgramData\chocolatey\lib\exiftool\tools\exiftool-13.29_64\exiftool.exe"   # Same here
DEFAULT_QUALITY = 90


def check_tool_exists(exe_path, label):
    """Check if the tool exists (by path or system PATH)"""
    if shutil.which(exe_path) is None:
        print(f"ERROR: {label} executable '{exe_path}' not found in PATH or as a full path.")
        return False
    return True

def recompress_image_with_mozjpeg(input_path, output_path, quality=DEFAULT_QUALITY):
    img = Image.open(input_path)
    width, height = img.size

    use_temp = False
    temp_resized_path = ''

    if width > 8000:
        print(f"  Resizing from {width}x{height}...")
        new_size = (width // 2, height // 2)
        img = img.resize(new_size, Image.LANCZOS)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            temp_resized_path = tmp.name
        img.save(temp_resized_path, "JPEG", quality=100)
        input_for_compression = temp_resized_path
        use_temp = True
    else:
        input_for_compression = input_path

    # Recompress with cjpeg
    subprocess.run([
        CJPEG_PATH,
        "-quality", str(quality),
        "-optimize",
        "-progressive",
        "-outfile", output_path,
        input_for_compression
    ], check=True)

    # Copy metadata using exiftool
    subprocess.run([
        EXIFTOOL_PATH,
        "-overwrite_original",
        "-TagsFromFile", input_path,
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if use_temp and os.path.exists(temp_resized_path):
        os.remove(temp_resized_path)

def process_directory(source_dir):
    output_dir = os.path.join(source_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(source_dir):
        if filename.lower().endswith(".jpg"):
            input_path = os.path.join(source_dir, filename)
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{base_name}_recompressed.jpg")
            print(f"Processing {filename} -> {os.path.basename(output_path)}")
            try:
                recompress_image_with_mozjpeg(input_path, output_path)
            except Exception as e:
                print(f"Failed to process {filename}: {e}")


if __name__ == "__main__":
    if not (check_tool_exists(CJPEG_PATH, "cjpeg") and check_tool_exists(EXIFTOOL_PATH, "exiftool")):
        print("Please ensure that cjpeg and exiftool are installed and accessible.")
        sys.exit(1)

    if len(sys.argv) != 2:
        print("Usage: python recompress_jpgs_with_mozjpeg.py <source_directory>")
        sys.exit(1)

    source_dir = sys.argv[1]
    if not os.path.isdir(source_dir):
        print(f"Error: {source_dir} is not a directory")
        sys.exit(1)

    process_directory(source_dir)
