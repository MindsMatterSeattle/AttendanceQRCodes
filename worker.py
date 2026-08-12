import glob
import json
import os
import time
from datetime import datetime

from app import generate_qr_code, TASKS_DIR

POLL_INTERVAL_SECONDS = 5


def load_task(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_task(task, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(task, f, indent=2)


def get_pending_tasks():
    pattern = os.path.join(TASKS_DIR, '*.json')
    return sorted(glob.glob(pattern))


def process_task(path):
    task = load_task(path)
    if task.get('status') not in ('queued', 'processing'):
        return

    task['status'] = 'processing'
    task['updated_at'] = datetime.utcnow().isoformat() + 'Z'
    save_task(task, path)

    generated_files = []
    failed_emails = []

    for email in task.get('emails', []):
        try:
            filepath = generate_qr_code(email)
            if filepath:
                generated_files.append(filepath)
            else:
                failed_emails.append(email)
        except Exception as exc:
            failed_emails.append(email)
            print(f'Worker error generating QR for {email}: {exc}')

    task['generated_files'] = generated_files
    task['failed_emails'] = failed_emails
    task['updated_at'] = datetime.utcnow().isoformat() + 'Z'
    task['status'] = 'completed' if not failed_emails else 'completed'

    if len(generated_files) == 0 and failed_emails:
        task['status'] = 'failed'

    save_task(task, path)


if __name__ == '__main__':
    print('Starting QR generation worker...')
    while True:
        pending_tasks = get_pending_tasks()
        queued = False
        for task_path in pending_tasks:
            task = load_task(task_path)
            if task.get('status') == 'queued':
                queued = True
                print(f'Processing task {task["id"]} ({task["email_count"]} emails)')
                process_task(task_path)
                print(f'Finished task {task["id"]}')
        if not queued:
            time.sleep(POLL_INTERVAL_SECONDS)
