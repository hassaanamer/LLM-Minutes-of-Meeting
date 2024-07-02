from celery import current_app as celery
from speech import get_speech_transcription
from summary import get_minutes_of_meeting
import time

# Function to split text into chunks
def split_text(text, max_tokens):
    words = text.split()
    chunks = []
    while len(words) > max_tokens:
        chunks.append(" ".join(words[:max_tokens]))
        words = words[max_tokens:]
    chunks.append(" ".join(words))
    return chunks

@celery.task(bind=True)
def process_audio(self, audio_path, filename):
    
    self.update_state(state='STARTED', meta={'info': 'Processing Audio File.', 'audio_path': audio_path, 'audio_filename': filename})
    time.sleep(10)
    
    text = get_speech_transcription(audio_path)
    
    self.update_state(state='PROGRESS', meta={'info': 'Text extracted, Summarizing now.', 'audio_path': audio_path, 'audio_filename': filename})
    time.sleep(10)
    
    # Split text into chunks to fit within model's context window
    max_tokens = 704  # Adjust this value based on your model's token limit
    text_chunks = split_text(text, max_tokens)
    
    summaries = []
    for chunk in text_chunks:
        summary = get_minutes_of_meeting(chunk)
        summaries.append(summary)
    
    # Combine the summaries of the chunks
    minutes_of_meeting = " ".join(summaries)
    
    self.update_state(state='SUCCESS', meta={'info': 'Summary Ready.', 'summary': minutes_of_meeting, 'audio_path': audio_path, 'audio_filename': filename})
    time.sleep(10)
    return {'summary': minutes_of_meeting, 'audio_path': audio_path, 'audio_filename': filename}
