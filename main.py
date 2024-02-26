from dotenv import load_dotenv
from flask import Flask, request, redirect, render_template, url_for
import requests
import os
import base64
import json

app = Flask(__name__)

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_Secret")
redirect_uri = "http://192.168.0.195:5543/callback" # remember to change this to pi IPV4 address when ready for deployment

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    # Redirect to the Spotify authorization page
    return redirect(url_for('authorize'))

@app.route('/authorize')
def authorize():
    state = 'your_state'  # Generate a unique state value
    scope = 'user-read-private user-read-email user-top-read playlist-modify-public playlist-modify-private'
    return redirect(f'https://accounts.spotify.com/authorize?response_type=code&client_id={client_id}&scope={scope}&redirect_uri={redirect_uri}&state={state}')

@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')
    
    if state != 'your_state':  # Check if state matches
        return 'State mismatch error'
    
    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode('utf-8')
    
    headers = {
        'Authorization': f'Basic {auth_b64}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
    
    # Get token
    response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=data)
    response_data = response.json()
    
    access_token = response_data['access_token']
    
    # Test code for output
    # user_country = get_user_market(access_token)
    # print(user_country)
    
    # Fetch user profile
    profile_response = requests.get('https://api.spotify.com/v1/me', headers={'Authorization': 'Bearer ' + access_token})
    profile_data = profile_response.json()
    
    display_name = profile_data.get('display_name', 'Unknown')
    
    return render_template('callback.html', display_name=display_name, access_token=access_token)

def get_user_id(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get('https://api.spotify.com/v1/me', headers=headers)
    if response.status_code == 200:
        user_id = response.json()['id']
        return user_id
    else:
        return None

def create_playlist(access_token, user_id, playlist_name):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        'name': playlist_name,
        'public': False  # Change to True if you want the playlist to be public
    }
    url = f'https://api.spotify.com/v1/users/{user_id}/playlists'
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        playlist_id = response.json()['id']
        return playlist_id
    else:
        return None


@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    access_token = request.form.get('access_token')
    
    # Get the current user's user ID
    user_id = get_user_id(access_token)
    
    if user_id:
        # Hardcode the playlist name for now
        playlist_name = "SpotDiscover"
        
        # Create the empty playlist
        playlist_id = create_playlist(access_token, user_id, playlist_name)
        
        if playlist_id:
            return 'Playlist created successfully!'
        else:
            return 'Failed to create playlist'
    else:
        return 'Failed to get user ID'
    
def get_top_artists(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'time_range': 'short_term',  # Change this to 'medium_term' or 'long_term' if needed
        'limit': 2  # Adjust the limit as needed
    }
    response = requests.get('https://api.spotify.com/v1/me/top/artists', headers=headers, params=params)
    if response.status_code == 200:
        top_artists = [(artist['id']) for artist in response.json()['items']]
        return top_artists
    else:
        return None
    
def get_top_tracks(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'time_range': 'short_term',  # Change this to 'medium_term' or 'long_term' if needed
        'limit': 3  # Adjust the limit as needed
    }
    response = requests.get('https://api.spotify.com/v1/me/top/tracks', headers=headers, params=params)
    if response.status_code == 200:
        top_tracks = [(track['id']) for track in response.json()['items']]
        return top_tracks
    else:
        return None

def get_user_market(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get('https://api.spotify.com/v1/me', headers=headers)
    if response.status_code == 200:
        user_data = response.json()
        country = user_data.get('country')
        return country
    else:
        return None

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5543)
