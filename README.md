A tool to create attendance QR codes for Minds Matter Seattle. 

Deployed to [attendanceqrcodes.onrender.com](https://attendanceqrcodes.onrender.com/)

## Background worker

This app now queues QR generation jobs and processes them in the background. Start the worker in a separate process with:

```bash
python worker.py
```

Then run the Flask app as usual.
