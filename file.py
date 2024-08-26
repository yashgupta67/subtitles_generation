from flask import Flask, request, send_file, redirect
from werkzeug.utils import secure_filename
import os
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import speech_recognition as sr
from pydub import AudioSegment
import tempfile

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER


def extract_audio(video_path, audio_path):
    video = VideoFileClip(video_path)
    audio = video.audio
    audio.write_audiofile(audio_path)


def audio_to_text(audio_path):
    recognizer = sr.Recognizer()
    audio = AudioSegment.from_wav(audio_path)
    chunk_size = 30000  # 30 seconds in milliseconds
    subtitles = []

    # Temporary file for audio chunks
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_chunk_file:
        temp_chunk_path = temp_chunk_file.name

    for start in range(0, len(audio), chunk_size):
        end = min(start + chunk_size, len(audio))
        chunk = audio[start:end]
        chunk.export(temp_chunk_path, format="wav")

        with sr.AudioFile(temp_chunk_path) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data)
                subtitles.append({
                    'start': start / 1000,  # converting milliseconds to seconds
                    'end': end / 1000,
                    'text': text
                })
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                continue

    os.remove(temp_chunk_path)  # Clean up the temporary file
    return subtitles


def add_subtitles(video_path, subtitles, output_path):
    video = VideoFileClip(video_path)
    subtitle_clips = []

    for subtitle in subtitles:
        subtitle_clip = TextClip(subtitle['text'], fontsize=24, color='white', bg_color='black', size=(video.w, 100))
        subtitle_clip = subtitle_clip.set_duration(subtitle['end'] - subtitle['start'])
        subtitle_clip = subtitle_clip.set_start(subtitle['start']).set_position(('center', 'bottom'))
        subtitle_clips.append(subtitle_clip)

    video_with_subtitles = CompositeVideoClip([video] + subtitle_clips)
    video_with_subtitles.write_videofile(output_path, codec='libx264', audio_codec='aac')


@app.route('/')
def index():
    return '''
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <title>Video Subtitle Generator</title>
      </head>
      <body>
        <h1>Upload a Video</h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
          <input type="file" name="video" accept="video/*">
          <input type="submit" value="Upload Video">
        </form>
      </body>
    </html>
    '''


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'video' not in request.files:
        return redirect(request.url)
    file = request.files['video']
    if file.filename == '':
        return redirect(request.url)

    filename = secure_filename(file.filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    processed_path = os.path.join(app.config['PROCESSED_FOLDER'], 'processed_' + filename)

    file.save(video_path)

    # Extract audio and generate subtitles
    audio_path = os.path.join(app.config['UPLOAD_FOLDER'], 'audio.wav')
    extract_audio(video_path, audio_path)
    subtitles = audio_to_text(audio_path)
    add_subtitles(video_path, subtitles, processed_path)

    return '''
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <title>Processed Video</title>
      </head>
      <body>
        <h1>Processed Video</h1>
        <video width="800" controls>
          <source src="/processed/{}" type="video/mp4">
          Your browser does not support the video tag.
        </video>
        <br>
        <a href="/processed/{}" download>Download Video</a>
      </body>
    </html>
    '''.format('processed_' + filename, 'processed_' + filename)


@app.route('/processed/<filename>')
def processed_file(filename):
    return send_file(os.path.join(app.config['PROCESSED_FOLDER'], filename), as_attachment=False)


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)
    app.run(debug=True)