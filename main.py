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
    scope = 'user-read-private user-read-email'
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
    
    response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=data)
    response_data = response.json()
    
    access_token = response_data['access_token']
    
    # Fetch user profile
    profile_response = requests.get('https://api.spotify.com/v1/me', headers={'Authorization': 'Bearer ' + access_token})
    profile_data = profile_response.json()
    
    display_name = profile_data.get('display_name', 'Unknown')
    
    return f'Hello, {display_name}! Your access token is: {access_token}'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5543)
