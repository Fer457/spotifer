import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from datetime import timedelta, datetime
import datetime as dt
import schedule
import os
import requests
from collections import defaultdict
from sendMail import send_email_with_summary
from sheet import create_or_open_excel, log_track_to_excel, get_daily_summary, save_excel

SPOTIPY_CLIENT_ID = ''
SPOTIPY_CLIENT_SECRET = ''
SPOTIPY_REDIRECT_URI = ''
EXCEL_FILE = 'spotify_track_log.xlsx'

SCOPE = 'user-read-playback-state,user-read-currently-playing'

sp_oauth = SpotifyOAuth(client_id=SPOTIPY_CLIENT_ID,
                        client_secret=SPOTIPY_CLIENT_SECRET,
                        redirect_uri=SPOTIPY_REDIRECT_URI,
                        scope=SCOPE)

auth_url = sp_oauth.get_authorize_url()
print(f'Ve a la siguiente URL e inicia sesión: {auth_url}')

response_url = input('Introduce la URL a la que fuiste redirigido: ')

code = sp_oauth.parse_response_code(response_url)
token_info = sp_oauth.get_access_token(code)

sp = spotipy.Spotify(auth=token_info['access_token'])

workbook, sheet = create_or_open_excel(EXCEL_FILE)

artist_time = defaultdict(float)
track_time = defaultdict(float)

def get_current_track():
    refresh_token_if_needed()
    current_track = sp.current_playback()
    if current_track and current_track['is_playing']:
        track = current_track['item']
        artist_name = track['artists'][0]['name']
        track_name = track['name']
        album_image_url = track['album']['images'][0]['url']
        return track_name, artist_name, album_image_url
    return None, None, None

def refresh_token_if_needed():
    global token_info, sp
    if sp_oauth.is_token_expired(token_info):
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        sp = spotipy.Spotify(auth=token_info['access_token'])

def log_track(artist, track, start_time, end_time, album_image_url):
    duration = end_time - start_time
    duration_seconds = duration.total_seconds()
    duration_formatted = str(dt.datetime.utcfromtimestamp(duration_seconds).strftime('%H:%M:%S'))
    
    artist_time[artist] += duration_seconds / 60
    track_time[track] += duration_seconds / 60
    
    log_track_to_excel(sheet, artist, track, start_time, end_time, duration_formatted)
    
    save_excel(workbook, EXCEL_FILE)

    image_path = f'images/{track}.jpg'
    os.makedirs('images', exist_ok=True)
    if not os.path.exists(image_path):
        with open(image_path, 'wb') as img_file:
            img_file.write(requests.get(album_image_url).content)

def convert_to_minutes(duration_str):
    h, m, s = map(float, duration_str.split(':'))
    return h * 60 + m + s / 60

def get_daily_summary(sheet):
    artist_time = defaultdict(float)
    track_time = defaultdict(float)
    for row in sheet.iter_rows(min_row=2, values_only=True):
        artist, track, start_time, end_time, duration_str = row
        duration_minutes = convert_to_minutes(duration_str)
        artist_time[artist] += duration_minutes
        track_time[track] += duration_minutes
    return artist_time, track_time

def daily_email_task():
    today = dt.date.today()
    
    artist_time, track_time = get_daily_summary(sheet)
    top_artists = sorted(artist_time.items(), key=lambda x: x[1], reverse=True)[:5]
    top_tracks = sorted(track_time.items(), key=lambda x: x[1], reverse=True)[:5]
    
    top_artists_html = ''.join([f'<li><b>{artist}:</b> &nbsp; {minutes:.2f} minutos</li>' for artist, minutes in top_artists])
    
    images = []
    top_tracks_html = ''
    for track, minutes in top_tracks:
        image_path = f'images/{track}.jpg'
        images.append(image_path)
        top_tracks_html += f'''
        <li class="track">
            <div class="track-info">
                <b>{track}:</b> {minutes:.2f} minutos
            </div>
        </li>
        '''

    email_body = f'''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
                color: #333;
            }}
            .container {{
                width: 100%;
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                border-radius: 8px;
            }}
            h1 {{
                color: #1db954;
                text-align: center;
                margin-bottom: 20px;
            }}
            h2 {{
                color: #555555;
                border-bottom: 2px solid #1db954;
                padding-bottom: 5px;
            }}
            ul {{
                list-style-type: none;
                padding: 0;
            }}
            li {{
                background-color: #f9f9f9;
                margin: 10px 0;
                padding: 15px;
                border-radius: 5px;
                display: flex;
                align-items: center;
            }}
            .track img {{
                width: 50px;
                height: 50px;
                margin-right: 15px;
                border-radius: 5px;
            }}
            .track-info {{
                display: inline-block;
                vertical-align: middle;
            }}
            .footer {{
                margin-top: 20px;
                text-align: center;
                font-size: 12px;
                color: #888;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Resumen Ferpotify</h1>
            <h2>Artistas más escuchados</h2>
            <ul>
                {top_artists_html}
            </ul>
            <h2>Canciones más escuchadas</h2>
            <ul>
                {top_tracks_html}
            </ul>
            <div class="footer">
                <p>Generado automáticamente por Ferpotify</p>
            </div>
        </div>
    </body>
    </html>
    '''

    send_email_with_summary('Resumen de Ferpotify', email_body, images)

if __name__ == "__main__":
    last_track = None
    start_time = None
    today = dt.date.today()

    schedule.every().day.at("02:08").do(daily_email_task)

    try:
        while True:
            current_track, current_artist, album_image_url = get_current_track()
            if current_track != last_track:
                if last_track:
                    end_time = dt.datetime.now()
                    log_track(last_artist, last_track, start_time, end_time, last_album_image_url)

                last_track = current_track
                last_artist = current_artist
                last_album_image_url = album_image_url
                start_time = dt.datetime.now()

                if current_track:
                    print(f'Currently playing: {current_track} by {current_artist}')
                else:
                    print('No music is playing right now.')

            if dt.date.today() != today:
                today = dt.date.today()

            schedule.run_pending()
            time.sleep(3)
    except KeyboardInterrupt:
        if last_track:
            end_time = dt.datetime.now()
            log_track(last_artist, last_track, start_time, end_time, last_album_image_url)
        print("\nPrograma terminado.")
