from dotenv import load_dotenv
from flask import Flask, request, redirect, render_template, url_for, copy_current_request_context
import requests
import os
import base64
import threading
import time
import schedule
import datetime
import json

app = Flask(__name__)

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = "http://192.168.0.187:5543/callback" #Change this for different hosting pc

# Define your global variables here
access_token = None
refresh_token = None
playlist_id = None

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
    global access_token, refresh_token
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
    refresh_token = response_data['refresh_token']
    
    # Fetch user profile
    profile_response = requests.get('https://api.spotify.com/v1/me', headers={'Authorization': 'Bearer ' + access_token})
    profile_data = profile_response.json()
    
    display_name = profile_data.get('display_name', 'Unknown')
    
    return render_template('callback.html', display_name=display_name, access_token=access_token)

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    global access_token, playlist_id
    
    access_token = request.form.get('access_token')
    
    # Get the current user's user ID
    user_id = get_user_id(access_token)
    
    if user_id:
        # Hardcode the playlist name for now
        playlist_name = "SpotDiscover"
        
        # Create the empty playlist
        playlist_id = create_playlist(access_token, user_id, playlist_name)
        
        if playlist_id:  # Check if playlist ID was made
            seed_artists = get_top_artists(access_token)
            seed_tracks = get_top_tracks(access_token)
            market = get_user_market(access_token)
            recommendations = get_recommendations(access_token, seed_artists, seed_tracks, market)
            add_recommendations_to_playlist(access_token, playlist_id, recommendations)

            return redirect(url_for('successful_generate', access_token=access_token, playlist_id=playlist_id, refresh_token=refresh_token))
        else:
            return 'Failed to create playlist'
    else:
        return 'Failed to get user ID'
    
@app.route('/successful_generate')
def successful_generate():
    global access_token, playlist_id, refresh_token
    
    access_token = request.args.get('access_token')
    playlist_id = request.args.get('playlist_id')
    refresh_token = request.args.get('refresh_token')
    
    # Start the scheduler after the playlist is successfully created
    refresh_playlist_midnight(access_token, playlist_id, refresh_token)

    return render_template('successful_generate.html')

def refresh_playlist_midnight(access_token, playlist_id, refresh_token):
    # Schedule the refresh_playlist function to run at midnight every night
    #schedule.every().day.at("00:00").do(copy_current_request_context(refresh_playlist), access_token=access_token, playlist_id=playlist_id, refresh_token=refresh_token)
    schedule.every(65).minutes.do(copy_current_request_context(refresh_playlist), access_token=access_token, playlist_id=playlist_id, refresh_token=refresh_token)

def scheduler_thread():
    while True:
        schedule.run_pending()
        time.sleep(1)
    
def get_user_id(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get('https://api.spotify.com/v1/me', headers=headers)
    if response.status_code == 200:
        user_id = response.json()['id']
        return user_id
    else:
        print("Failed to get user ID. Status code:", response.status_code)
        print("Response content:", response.content)
        return None


def create_playlist(access_token, user_id, playlist_name):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        'name': playlist_name,
        'public': True  # Change to True if you want the playlist to be public
    }
    url = f'https://api.spotify.com/v1/users/{user_id}/playlists'
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201 or 200: # For some reason response code is 200 instead of 201?
        playlist_id = response.json()['id']
        return playlist_id
    else:
        print("Failed to create playlist:", response.status_code, response.content)  # Print response content
        return None

def get_top_artists(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'time_range': 'short_term',  # Change this to 'medium_term' or 'long_term' if needed
        'limit': 2,  # Adjust the limit as needed
        'offset': 30
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
        'limit': 3,  # Adjust the limit as needed
        'offset': 30
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
    
def get_recommendations(access_token, seed_artists, seed_tracks, market, limit=30):
    # Construct the request URL
    url = 'https://api.spotify.com/v1/recommendations'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    params = {
        'limit': limit,
        'market': market,
        'seed_artists': seed_artists,
        'seed_tracks': seed_tracks
    }

    # Send the request to Spotify API
    response = requests.get(url, headers=headers, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response and extract recommended tracks
        recommendations = response.json()['tracks']
        recommended_tracks = [track['name'] for track in recommendations]
        return recommended_tracks
    else:
        # Handle errors if the request fails
        print("Failed to get recommendations:", response.status_code)
        return None
    
def add_recommendations_to_playlist(access_token, playlist_id, recommendations):
    # Convert track names to track URIs
    track_uris = []
    for track_name in recommendations:
        track_uri = get_track_uri(access_token, track_name)
        if track_uri:
            track_uris.append(track_uri)

    # Add the track URIs to the playlist
    if track_uris:
        added = add_tracks_to_playlist(access_token, playlist_id, track_uris)
        if added:
            return 'Recommendations added to playlist successfully!'
        else:
            return 'Failed to add recommendations to playlist'
    else:
        return 'No recommendations found'


def get_track_uri(access_token, track_name):
    # Search for the track using its name
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'q': track_name,
        'type': 'track',
        'limit': 1
    }
    response = requests.get('https://api.spotify.com/v1/search', headers=headers, params=params)
    if response.status_code == 200:
        # Extract the track URI from the response
        items = response.json()['tracks']['items']
        if items:
            track_uri = items[0]['uri']
            return track_uri
    return None

def add_tracks_to_playlist(access_token, playlist_id, track_uris):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    params = {
        'uris': track_uris
    }
    response = requests.post(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers, json=params)
    if response.status_code == 201:
        return True
    else:
        return False
    
def refresh_playlist(access_token, playlist_id, refresh_token):
    with app.app_context():
        print("Starting refresh...")
    
        if is_token_expired(access_token):
            print("Access token expired attempting to refresh token...")
            access_token = refresh_access_token(refresh_token)
        
        # Get the current user's user ID
        user_id = get_user_id(access_token)

        if user_id:
            # Hardcode the playlist name for now
            playlist_name = "SpotDiscover"
        
            # Check if the playlist already exists
            existing_playlist_id = get_playlist_id(access_token, user_id, playlist_name)
        
            if existing_playlist_id:
                # Get the tracks currently in the playlist
                current_tracks = get_playlist_tracks(access_token, existing_playlist_id)
            
                # Remove existing tracks from the playlist
                if current_tracks:
                    remove_tracks_from_playlist(access_token, existing_playlist_id, current_tracks)
                    print("Existing tracks removed from the playlist")
            
                # Get new recommendations and add them to the playlist
                seed_artists = get_top_artists(access_token)
                seed_tracks = get_top_tracks(access_token)
                market = get_user_market(access_token)
                recommendations = get_recommendations(access_token, seed_artists, seed_tracks, market)
                add_recommendations_to_playlist(access_token, existing_playlist_id, recommendations)
                print("Playlist successfully refreshed!")
            
                return 'Playlist refreshed successfully!'
            else:
                print("Playlist does not exist")
                return schedule.CancelJob
        
def is_token_expired(access_token):
  response = requests.get('https://api.spotify.com/v1/me', headers={
    'Authorization': 'Bearer ' + access_token
  })
  return response.status_code == 401

def refresh_access_token(refresh_token):
    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode('utf-8')

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth_b64}'
    }

    data = {
        'grant_type' : 'refresh_token',
        'refresh_token' : refresh_token
    }

    response = requests.post('https://accounts.spotify.com/api/token', data=data, headers=headers) #sends request off to spotify

    if(response.status_code == 200): #checks if request was valid
        print("Refresh token successfully refreshed")
        response_json = response.json()
        return response_json["access_token"]
    else:
        print("ERROR! Access token did not return 200 during refresh: "+ str(response))

# Function to get the playlist ID if it already exists
def get_playlist_id(access_token, user_id, playlist_name):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(f'https://api.spotify.com/v1/me/playlists', headers=headers)
    if response.status_code == 200:
        playlists = response.json()['items']
        for playlist in playlists:
            if playlist['name'] == playlist_name:
                return playlist['id']
    return None
    
def get_user_playlists(access_token, user_id):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    params = {
        'limit': 50  # Adjust the limit as needed
    }
    response = requests.get(f'https://api.spotify.com/v1/users/{user_id}/playlists', headers=headers, params=params)
    if response.status_code == 200:
        playlists_data = response.json().get('items', [])
        playlists = [{'id': playlist['id'], 'name': playlist['name']} for playlist in playlists_data]
        return playlists
    else:
        print("Failed to retrieve user playlists:", response.status_code)
        return None
    
def get_playlist_tracks(access_token, playlist_id):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    response = requests.get(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers)
    if response.status_code == 200:
        tracks = response.json()['items']
        track_uris = [track['track']['uri'] for track in tracks]
        return track_uris
    else:
        return None
    
def remove_tracks_from_playlist(access_token, playlist_id, track_uris):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    data = {
        'tracks': [{'uri': uri} for uri in track_uris]
    }
    response = requests.delete(f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks', headers=headers, json=data)
    if response.status_code == 200:
        return True
    else:
        return False
    
# Start the scheduler in a separate thread
scheduler_thread = threading.Thread(target=scheduler_thread)
scheduler_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5543)