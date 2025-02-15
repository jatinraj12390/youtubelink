from flask import Flask, render_template, request, send_file, redirect, url_for
from yt_dlp import YoutubeDL
import os
import re
import glob

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

MAX_FILES = 2 # Limit for auto cleanup

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>| ]', '_', filename)

def cleanup_old_files():
    """Removes the oldest files if the folder exceeds MAX_FILES."""
    files = sorted(glob.glob(os.path.join(DOWNLOAD_FOLDER, "*")), key=os.path.getctime)
    while len(files) > MAX_FILES:
        os.remove(files.pop(0))  # Remove the oldest file

def get_video_info(video_url, format_type):
    """Fetch video/audio information without downloading."""
    ydl_opts = {
        "quiet": True,
        "format": "bestaudio" if format_type == "mp3" else "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)  # Get metadata only
        file_size = info.get("filesize", 0) or sum(f["filesize"] for f in info.get("formats", []) if f.get("filesize"))
        return info.get("title", "Unknown"), round(file_size / (1024 * 1024), 2) if file_size else "Unknown"

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        video_url = request.form.get("url")
        download_format = request.form.get("format")

        try:
            # Fetch video info before downloading
            file_title, estimated_size = get_video_info(video_url, download_format)

            cleanup_old_files()  # Cleanup before downloading

            ydl_opts = {
                "quiet": True,
                "restrictfilenames": True,
                "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
            }

            # Handle MP3 format
            if download_format == "mp3":
                ydl_opts.update({
                    "format": "bestaudio",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                })

            # Handle MP4 format (Forces H.264 & AAC audio)
            elif download_format == "mp4":
                ydl_opts.update({
                    "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]",  # Forces MP4 video/audio
                    "merge_output_format": "mp4",
                })

            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(video_url, download=True)
                
                # Get original filename
                original_path = ydl.prepare_filename(info_dict)

                # Determine correct file extension
                file_ext = "mp3" if download_format == "mp3" else "mp4"

                # Sanitize filename
                sanitized_title = sanitize_filename(file_title)
                file_filename = f"{sanitized_title}.{file_ext}"
                file_path = os.path.join(DOWNLOAD_FOLDER, file_filename)

                # Fix for potential extension mismatch
                if not original_path.endswith(f".{file_ext}"):
                    original_path = original_path.replace(".webm", f".{file_ext}").replace(".m4a", f".{file_ext}")

                # Delete existing file before renaming
                if os.path.exists(file_path):
                    os.remove(file_path)

                # Rename to correct filename
                if os.path.exists(original_path):
                    os.rename(original_path, file_path)
                else:
                    return f"Error: File not found at {original_path}"

                # Get final downloaded file size
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # Convert bytes to MB
                file_size = round(file_size, 2)

            # Redirect user to download the file
            return redirect(url_for("download_file", filename=file_filename))

        except Exception as e:
            return f"An error occurred: {e}"

    return render_template("index.html")

@app.route("/download/<filename>")
def download_file(filename):
    """Serve the file for download."""
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return "Error: File not found", 404

if __name__ == "__main__":
    app.run(debug=True)
