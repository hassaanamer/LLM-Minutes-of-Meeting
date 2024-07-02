import os
from flask import Flask, render_template, request, redirect, jsonify, send_from_directory
from flask_cors import CORS

from werkzeug.utils import secure_filename

from celery import Celery

from utils import convert_to_wav

from global_variables import BASE_DATA_UPLOADED_RECORDINGS_DIRECTORY


def make_celery(app):
    celery = Celery(
        app.import_name,
        backend='redis://localhost:6379/0',
    )
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = BASE_DATA_UPLOADED_RECORDINGS_DIRECTORY
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'wav', 'mp3'}
CORS(app)
celery = make_celery(app)

from tasks import process_audio

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/check_task/<task_id>')
def check_task(task_id):
    task = process_audio.AsyncResult(task_id)
    response = {'status': task.state}
    
    if task.state == 'FAILURE':
        response['info'] = str(task.result)
        response['filename'] = ''
    elif task.state == 'SUCCESS':
        response['info'] = task.info.get('info', 'COMPLETED') if task.info else 'COMPLETED'
        response['filename'] = task.info.get('audio_filename', '') if task.info else ''
        response['summary'] = task.info.get('summary', '') if task.info else ''
    else:
        response['info'] = 'Task is still processing'
        response['filename'] = ''

    return jsonify(response)



@app.route('/audio/<filename>')
def send_audio(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/results/<task_id>')
def results(task_id):
    task = process_audio.AsyncResult(task_id)

    if task.state == 'PENDING':
        # Task is still in progress
        return render_template('result.html', minutes_of_meeting="Task is still processing", recording_status="Pending", recording_filename="", audio_path="#")

    elif task.state != 'FAILURE':
        result = task.result or {}
        minutes_of_meeting = result.get('summary', 'No summary available')
        recording_status = "Unknown"
        recording_filename = result.get('audio_filename', '')
        audio_path = os.path.join('/audio', recording_filename) if recording_filename else '#'
        return render_template('result.html', minutes_of_meeting=minutes_of_meeting, recording_status=recording_status, recording_filename=recording_filename, audio_path=audio_path)

    else:
        # Something went wrong with the task
        return render_template('result.html', minutes_of_meeting="Task failed", recording_status="Failed", recording_filename="", audio_path="#")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return redirect(request.url)
    
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    audio_path = convert_to_wav(file_path)
    
    task = process_audio.delay(audio_path, filename)
    
    return jsonify({'task_id': task.id})

if __name__ == '__main__':
    # app.run(debug=True)
    app.run(port=50021)
