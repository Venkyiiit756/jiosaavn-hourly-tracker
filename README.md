# JioSaavn Play Count Monitor

A simple web application that monitors the play count of a JioSaavn song and displays it on a webpage that updates automatically.

## Features

- Fetches play count from JioSaavn every 15 minutes
- Displays play count and last update timestamp
- Auto-refreshes webpage every 60 seconds
- Simple and clean web interface

## Requirements

- Python 3.7+
- Flask
- Requests
- BeautifulSoup4
- python-dotenv

## Setup

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Open your web browser and navigate to:
   ```
   http://localhost:5000
   ```

## Notes

- The webpage automatically refreshes every 60 seconds
- The play count is updated every 15 minutes in the background
- The application uses a simple in-memory storage for the latest play count
