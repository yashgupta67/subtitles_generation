from flask import Flask, render_template, request, send_from_directory, redirect, url_for
import whisper
import os
import cv2
import ffmpeg
import json
import subprocess

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/Users/rajeshgupta/PycharmProjects/subtitles/uploads'
app.config['PROCESSED_FOLDER'] = '/Users/rajeshgupta/PycharmProjects/subtitles/static/videos'

# Load the Whisper model
model = whisper.load_model("base")

def generate_subtitles(video_path):
    try:
        # Extract audio from the video
        audio_path = "audio.wav"
        ffmpeg.input(video_path).output(audio_path).run(overwrite_output=True)
        print(f"Audio extracted to {audio_path}")

        # Transcribe the audio
        result = model.transcribe(audio_path)
        subtitles = result['segments']
        print(f"Transcription complete: {subtitles}")

        return subtitles  # Return the subtitles array for display

    except Exception as e:
        print(f"Error generating subtitles: {e}")
        return None

def process_video(video_path, output_path):
    try:
        # Generate subtitles for the video
        subtitles = generate_subtitles(video_path)
        if not subtitles:
            raise ValueError("No subtitles generated.")

        # Path to the temporary video file with subtitles
        temp_subtitles_video_path = "temp_subtitles_video.mp4"

        # Create video with subtitles using OpenCV
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Error opening video file.")

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_subtitles_video_path, fourcc, fps, (width, height))

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1
        font_color = (255, 255, 255)
        thickness = 2
        line_type = cv2.LINE_AA

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Add subtitles to the frame
            current_time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            for subtitle in subtitles:
                if subtitle['start'] <= current_time <= subtitle['end']:
                    cv2.putText(frame, subtitle['text'], (50, height - 50), font, font_scale, font_color, thickness, line_type)
            out.write(frame)

        cap.release()
        out.release()

        # Combine the temporary video with subtitles and the audio file
        final_output_path = output_path
        ffmpeg_cmd = [
            'ffmpeg', '-i', temp_subtitles_video_path, '-i', 'audio.wav',
            '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0', final_output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        print(f"Final video with audio saved to {final_output_path}")

        # Clean up temporary files
        os.remove(temp_subtitles_video_path)
        os.remove("audio.wav")  # Clean up the audio file as well
        return os.path.basename(final_output_path)  # Return the filename for use in rendering

    except Exception as e:
        print(f"Error processing video: {e}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files['file']
        if file:
            # Save uploaded file
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(video_path)

            # Process video to add subtitles
            processed_video_filename = os.path.splitext(file.filename)[0] + '.mp4'
            processed_video_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_video_filename)
            subtitles_filename = process_video(video_path, processed_video_path)

            if subtitles_filename:
                return redirect(url_for('video', filename=subtitles_filename))
            else:
                return "An error occurred while processing the video."
    return render_template('index.html')

@app.route('/video/<filename>')
def video(filename):
    video_path = os.path.join(app.config['PROCESSED_FOLDER'], filename)
    if not os.path.isfile(video_path):
        return "Video not found.", 404

    # Load subtitles for the given video file
    subtitles = generate_subtitles(video_path)
    if subtitles is None:
        return "Subtitles could not be generated.", 500

    return render_template('video.html', filename=filename, subtitles=json.dumps(subtitles))

@app.route('/static/videos/<filename>')
def send_video(filename):
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename, as_attachment=False)

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
    app.run(debug=True)
