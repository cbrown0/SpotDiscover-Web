from dotenv import load_dotenv
from flask import Flask, request, session, redirect, render_template, url_for
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import random
import spotipy.oauth2 as oauth2

app = Flask(__name__)

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
app.secret_key = os.getenv("SECRET_KEY")
redirect_uri = "http://192.168.0.195:5543/callback"  # Change this for different hosting pc

# Define your global variables here
scope = "user-read-private user-read-email playlist-modify-public playlist-modify-private user-top-read"
sp_oauth = SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope=scope)
sp = spotipy.Spotify(auth_manager=sp_oauth)
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
    state = 'your_state'  # Set your custom state value here
    return redirect(sp.auth_manager.get_authorize_url(state=state))

@app.route('/callback')
def callback():
    global sp_oauth  # Declare sp_oauth as global to access the global variable

    code = request.args.get('code')
    state = request.args.get('state')

    if state != 'your_state':  # Check if state matches
        return 'State mismatch error'

    # Exchange the authorization code for an access token
    token_info = sp_oauth.get_access_token(code)
    access_token = token_info['access_token']
    refresh_token = token_info.get('refresh_token')

    # Store the access token and refresh token in the session or database
    session['access_token'] = access_token
    if refresh_token:
        session['refresh_token'] = refresh_token

    # Use the access token to fetch user profile data
    sp = spotipy.Spotify(auth=access_token)
    profile_data = sp.current_user()
    display_name = profile_data.get('display_name', 'Unknown')

    return render_template('callback.html', display_name=display_name, access_token=access_token)

@app.route('/generate_playlist', methods=['POST'])
def generate_playlist():
    global access_token, playlist_id, refresh_token

    access_token = request.form.get('access_token')
    refresh_token = request.form.get('refresh_token')  # Assuming it's passed in the request

    # Get the current user's user ID
    user_id = get_user_id(access_token)

    if user_id:
        # Hardcode the playlist name for now
        playlist_name = "SpotDiscover"

        # Get top artists and top tracks
        seed_artists = get_top_artists(access_token)
        seed_tracks = get_top_tracks(access_token)
        market = get_user_market(access_token)

        # Create the empty playlist with artists and tracks as description
        playlist_id = create_playlist(access_token, user_id, playlist_name, seed_artists, seed_tracks)

        if playlist_id:
            recommendations = get_recommendations(access_token, seed_artists, seed_tracks, market)
            add_recommendations_to_playlist(access_token, playlist_id, recommendations)

            return redirect(url_for('successful_generate', access_token=access_token, playlist_id=playlist_id, refresh_token=refresh_token))
        else:
            return 'Failed to create playlist'
    else:
        return 'Failed to get user ID'

@app.route('/successful_generate')  # Add this line
def successful_generate():
    global playlist_id

    user_data = sp.current_user()
    access_token = session.get('access_token')  # Get access_token from session
    playlist_id = request.args.get('playlist_id')
    refresh_token = session.get('refresh_token')  # Get refresh_token from session

    start_scheduler(access_token, playlist_id, refresh_token)

    return render_template('successful_generate.html')

def start_scheduler(access_token, playlist_id, refresh_token):
    # Remove refresh_token from the function signature
    print("Refresh Token in start_scheduler: ", refresh_token)
    scheduler.add_job(refresh_playlist, CronTrigger(hour=0), id='refresh_job', args=[access_token, playlist_id, refresh_token])
    
def get_user_id(access_token):
    sp = spotipy.Spotify(auth=access_token)
    try:
        user_data = sp.current_user()
        user_id = user_data['id']
        return user_id
    except spotipy.SpotifyException as e:
        print("Failed to get user ID:", e)
        return None


def create_playlist(access_token, user_id, playlist_name, artists, tracks):
    sp = spotipy.Spotify(auth=access_token)
    try:
        # Get the names of artists
        artist_names = [sp.artist(artist)['name'] for artist in artists]
        # Get the names of tracks
        track_names = [sp.track(track)['name'] for track in tracks]

        # Construct the playlist description
        description = f"Recommendations based on top artists: {', '.join(artist_names)} and top tracks: {', '.join(track_names)}"

        # Create the playlist with the provided name and description
        playlist_data = sp.user_playlist_create(user=user_id, name=playlist_name, description=description, public=True)

        # Retrieve the playlist ID from the response
        playlist_id = playlist_data['id']
        return playlist_id
    except spotipy.SpotifyException as e:
        print("Failed to create playlist:", e)
        return None

def get_top_artists(access_token):
    sp = spotipy.Spotify(auth=access_token)
    try:
        offset = random.randint(0, 50)  # Generate a random offset
        limit = 2  # Adjust the limit as needed
        top_artists_data = sp.current_user_top_artists(time_range='short_term', limit=limit, offset=offset)
        top_artists = [artist['id'] for artist in top_artists_data['items']]
        print("Offset for top artists:", offset)  # Print the offset to the console
        return top_artists
    except spotipy.SpotifyException as e:
        print("Failed to get top artists:", e)
        return None
    
def get_top_tracks(access_token):
    sp = spotipy.Spotify(auth=access_token)
    try:
        offset = random.randint(0, 50)  # Generate a random offset
        limit = 3  # Adjust the limit as needed
        top_tracks_data = sp.current_user_top_tracks(time_range='short_term', limit=limit, offset=offset)
        top_tracks = [track['id'] for track in top_tracks_data['items']]
        print("Offset for top tracks:", offset)  # Print the offset to the console
        return top_tracks
    except spotipy.SpotifyException as e:
        print("Failed to get top tracks:", e)
        return None

def get_user_market(access_token):
    sp = spotipy.Spotify(auth=access_token)
    try:
        user_data = sp.current_user()
        country = user_data.get('country')
        return country
    except spotipy.SpotifyException as e:
        print("Failed to get user market:", e)
        return None
    
def get_recommendations(access_token, seed_artists, seed_tracks, market, limit=31):
    sp = spotipy.Spotify(auth=access_token)
    try:
        recommendations = sp.recommendations(seed_artists=seed_artists, seed_tracks=seed_tracks, limit=limit, country=market)
        recommended_tracks = [track['name'] for track in recommendations['tracks']]
        return recommended_tracks
    except spotipy.SpotifyException as e:
        print("Failed to get recommendations:", e)
        return None
    
def add_recommendations_to_playlist(access_token, playlist_id, recommendations):
    if recommendations is None:
        print("Failed to fetch recommendations from Spotify")
        return 'Failed to fetch recommendations from Spotify'

    sp = spotipy.Spotify(auth=access_token)
    track_uris = []
    for track_name in recommendations[:30]:  # Add only the first 30 tracks
        track_uri = get_track_uri(sp, track_name)
        if track_uri:
            track_uris.append(track_uri)
    if track_uris:
        try:
            sp.playlist_add_items(playlist_id, track_uris)
            return 'Recommendations added to playlist successfully!'
        except spotipy.SpotifyException as e:
            print("Failed to add recommendations to playlist:", e)
            return 'Failed to add recommendations to playlist'
    else:
        return 'No recommendations found'

def get_track_uri(sp, track_name):
    try:
        results = sp.search(q=f"track:{track_name}", type='track', limit=1)
        items = results['tracks']['items']
        if items:
            track_uri = items[0]['uri']
            return track_uri
    except spotipy.SpotifyException as e:
        print("Error searching for track:", e)
    return None

def add_tracks_to_playlist(access_token, playlist_id, track_uris):
    sp = spotipy.Spotify(auth=access_token)
    try:
        sp.playlist_add_items(playlist_id, track_uris)
        return True
    except spotipy.SpotifyException as e:
        print("Failed to add tracks to playlist:", e)
        return False
    
def refresh_playlist(access_token, playlist_id, refresh_token):
    sp = spotipy.Spotify(auth=access_token)
    print("Starting refresh...")
    print("Access token before refresh: ", access_token)
    print("Refresh token before refresh:", refresh_token)

    if is_token_expired(access_token):
        print("Access token expired attempting to refresh token...")
        access_token = refresh_access_token(refresh_token)

    print("Access token after refresh: ", access_token)
    print("Refresh token after refresh:", refresh_token)

    user_id = sp.me()['id']
    if user_id:
        playlist_name = "SpotDiscover"
        
        playlists = sp.current_user_playlists()
        existing_playlist_id = None
        for playlist in playlists['items']:
            if playlist['name'] == playlist_name:
                existing_playlist_id = playlist['id']
                break

        if existing_playlist_id:
            current_tracks = sp.playlist_tracks(existing_playlist_id)
            if current_tracks:
                current_track_uris = [track['track']['uri'] for track in current_tracks['items']]
                sp.playlist_remove_all_occurrences_of_items(existing_playlist_id, current_track_uris)
                print("Existing tracks removed from the playlist")

            seed_artists = get_top_artists(access_token)
            seed_tracks = get_top_tracks(access_token)
            market = get_user_market(access_token)
            recommendations = get_recommendations(access_token, seed_artists, seed_tracks, market)
            add_recommendations_to_playlist(access_token, existing_playlist_id, recommendations)
            print("Playlist successfully refreshed!")
        else:
            print("Playlist does not exist")
            scheduler.remove_job('refresh_job')
        
def is_token_expired(access_token):
    sp = spotipy.Spotify(auth=access_token)
    try:
        # Make a simple request to Spotify API to check if token is valid
        sp.current_user()
        return False
    except spotipy.SpotifyException as e:
        if e.http_status == 401:
            return True
        else:
            raise e  # If it's not a 401 error, raise the exception for further analysis

def refresh_access_token(refresh_token):
    # Initialize SpotifyOAuth object with client_id, client_secret, and redirect_uri
    sp_oauth = oauth2.SpotifyOAuth(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)

    # Refresh the access token using the refresh token
    token_info = sp_oauth.refresh_access_token(refresh_token)

    if "access_token" in token_info:
        print("Refresh token successfully refreshed")
        return token_info["access_token"]
    else:
        print(f"ERROR! Access token refresh failed: {token_info.get('error', 'Unknown error')}")
        return None

def get_playlist_id(access_token, user_id, playlist_name):
    # Initialize Spotipy client
    sp = spotipy.Spotify(auth=access_token)

    # Get user's playlists
    playlists = sp.user_playlists(user_id)

    # Search for the playlist by name
    for playlist in playlists['items']:
        if playlist['name'] == playlist_name:
            return playlist['id']

    return None
    
def get_user_playlists(access_token, user_id):
    # Initialize Spotipy client
    sp = spotipy.Spotify(auth=access_token)

    # Get user's playlists
    playlists = sp.user_playlists(user_id)

    # Extract playlist information
    playlist_info = [{'id': playlist['id'], 'name': playlist['name']} for playlist in playlists['items']]

    return playlist_info
    
def get_playlist_tracks(access_token, playlist_id):
    # Initialize Spotipy client
    sp = spotipy.Spotify(auth=access_token)

    # Get tracks of the playlist
    tracks = sp.playlist_tracks(playlist_id)

    # Extract track URIs
    track_uris = [track['track']['uri'] for track in tracks['items']]

    return track_uris
    
def remove_tracks_from_playlist(access_token, playlist_id, track_uris):
    # Initialize Spotipy client
    sp = spotipy.Spotify(auth=access_token)

    # Remove tracks from the playlist
    sp.playlist_remove_all_occurrences_of_items(playlist_id, track_uris)

    return True  # Assuming successful removal, Spotipy does not return a response
    
# Scheduler using APScheduler
scheduler = BackgroundScheduler()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5543)