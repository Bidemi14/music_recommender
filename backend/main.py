from fastapi import FastAPI,HTTPException,Request
from backend import database
import joblib
import pandas as pd
from pathlib import Path
from backend.recommender import recommended_songs
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
import secrets
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth
from fastapi.responses import RedirectResponse,JSONResponse
import spotipy
from cryptography.fernet import Fernet
import json
import hashlib
import time

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)
encryption_key = os.environ["SPOTIFY_ENCRYPTION_KEY"]
cipher = Fernet(encryption_key.encode())

spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
spotify_redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI")

DB_PATH = Path(__file__).resolve().parent.parent / "music.db"
def create_spotify_sessions_table():
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spotify_sessions (
            session_id_hash TEXT PRIMARY KEY,
            encrypted_token_info TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        )
    """)

    connection.commit()
    connection.close()


create_spotify_sessions_table()

class PlaylistCreate(BaseModel):
    user_id: int
    playlist_name: str

class SongCreate(BaseModel):
    song_title: str
    artist_name: str

app = FastAPI()
spotify_auth = SpotifyOAuth(
    client_id=spotify_client_id,
    client_secret=spotify_client_secret,
    redirect_uri=spotify_redirect_uri,
    scope="playlist-modify-private playlist-modify-public"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://music-recommender-1-8zt5.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["GET","POST"],
    allow_headers=["*"]
)
model_folder = Path(__file__).resolve().parent / "models"


knn = joblib.load(model_folder / "knn_model.pkl")


songs = pd.read_pickle(model_folder / "songs.pkl")

recommendation_features = pd.read_pickle(
    model_folder / "recommendation_features.pkl"
)

@app.get("/")
def home():
    return {"message": "Welcome to my music recommender"}

@app.get("/recommend")
def recommend(song: str):
    results = recommended_songs(
        song, songs, knn, recommendation_features
    )

    if isinstance(results, str):
        return {"error": results}

    return {
        "selected_song": song,
        "recommendations": results[
            ["title", "artist_name"]
        ].to_dict(orient="records")
    }
@app.post("/playlists")
def create_playlist(playlist: PlaylistCreate):

    connection = sqlite3.connect(DB_PATH)

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO playlists (user_id, playlist_name)
        VALUES (?, ?)
        """,
        (playlist.user_id, playlist.playlist_name)
    )

    connection.commit()

    playlist_id = cursor.lastrowid

    connection.close()

    return {
        "message": "Playlist saved successfully",
        "playlist_id": playlist_id
    }

@app.post("/playlists/{playlist_id}/songs")
def add_song(playlist_id: int, song: SongCreate):

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM playlists WHERE playlist_id = ?",
        (playlist_id,)
    )

    if cursor.fetchone() is None:
        connection.close()
        return {"error": "Playlist does not exist"}

    cursor.execute(
        """
        INSERT INTO playlist_songs (playlist_id, song_title, artist_name)
        VALUES (?, ?, ?)
        """,
        (playlist_id, song.song_title, song.artist_name)
    )

    connection.commit()
    connection.close()

    return {
        "message": "Song saved successfully",
        "playlist_id": playlist_id
    }

@app.get("/login")
def spotify_login():
    state = secrets.token_urlsafe(32)
    auth_url = spotify_auth.get_authorize_url(state=state)

    response = RedirectResponse(url=auth_url)

    response.set_cookie(
        key="spotify_oauth_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600
    )

    return response


@app.get("/callback")#exchanges code for token 
def spotify_callback(request: Request):
    returned_state = request.query_params.get("state")
    saved_state = request.cookies.get("spotify_oauth_state")

    if not saved_state or returned_state != saved_state:
        raise HTTPException(
            status_code=400,
            detail="Invalid Spotify login state"
        )

    code = request.query_params.get("code")#allows backend request temporary code from spotify 

    if not code:
        raise HTTPException(
            status_code=400,
            detail="Spotify did not return an authorization code"
        )

    token_info = spotify_auth.get_access_token(code,check_cache=False )

        
    session_id = secrets.token_urlsafe(32)

   
    session_id_hash = hashlib.sha256(
        session_id.encode()
    ).hexdigest()

    
    token_json = json.dumps(token_info)

    # encrypt the token information
    encrypted_token = cipher.encrypt(
        token_json.encode()
    ).decode()

    
    expires_at = int(time.time()) + 86400

    
    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO spotify_sessions
        (session_id_hash, encrypted_token_info, expires_at)
        VALUES (?, ?, ?)
        """,
        (session_id_hash, encrypted_token, expires_at)
    )

    connection.commit()
    connection.close()

    # send the session ID to the browser
    response = JSONResponse({
        "message": "Spotify connected successfully"
    })

    response.set_cookie(
        key="spotify_session",
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400
    )

    response.delete_cookie("spotify_oauth_state")

    return response

def get_spotify_token(request: Request):

    session_id = request.cookies.get("spotify_session")

    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Please connect your Spotify account"
        )

    session_id_hash = hashlib.sha256(
        session_id.encode()
    ).hexdigest()

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT encrypted_token_info, expires_at
        FROM spotify_sessions
        WHERE session_id_hash = ?
        """,
        (session_id_hash,)
    )

    session = cursor.fetchone()
    connection.close()

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Spotify session not found"
        )

    encrypted_token, expires_at = session

    if int(time.time()) >= expires_at:
        raise HTTPException(
            status_code=401,
            detail="Spotify session expired"
        )

    token_json = cipher.decrypt(
        encrypted_token.encode()
    ).decode()

    token_info = json.loads(token_json)

    if spotify_auth.is_token_expired(token_info):

        token_info = spotify_auth.refresh_access_token(
            token_info["refresh_token"]
        )

        encrypted_token = cipher.encrypt(
            json.dumps(token_info).encode()
        ).decode()

        connection = sqlite3.connect(DB_PATH)
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE spotify_sessions
            SET encrypted_token_info = ?
            WHERE session_id_hash = ?
            """,
            (encrypted_token, session_id_hash)
        )

        connection.commit()
        connection.close()

    return token_info

@app.get("/spotify/status")
def spotify_status(request: Request):

    token_info = get_spotify_token(request)

    return {
        "connected": True,
        "message": "Spotify session is working"
    }
    

def find_spotify_song(spotify, title, artist):

    results = spotify.search(
        q=f"track:{title} artist:{artist}",
        type="track",
        limit=1
    )

    tracks = results["tracks"]["items"]

    if not tracks:
        return None

    return tracks[0]["uri"]





@app.post("/spotify/create-recommended-playlist")
def create_recommended_playlist(
    request: Request,
    song: str,
    playlist_name: str
):
    token_info = get_spotify_token(request)

    spotify = spotipy.Spotify(
        auth=token_info["access_token"]
    )

    
    recommendations = recommended_songs(
        song, songs, knn, recommendation_features
    )

    if isinstance(recommendations, str):
        raise HTTPException(
            status_code=404,
            detail=recommendations
        )

   
    track_uris = []

    for _, row in recommendations.iterrows():

        uri = find_spotify_song(
            spotify,
            row["title"],
            row["artist_name"]
        )

        if uri and uri not in track_uris:
            track_uris.append(uri)

    if not track_uris:
        raise HTTPException(
            status_code=404,
            detail="No recommended songs found on Spotify"
        )

    
    playlist = spotify._post(# make new Spotify playlist
        "me/playlists",
        payload={
            "name": playlist_name,
            "public": False,
            "description": f"Recommendations based on {song}"
        }
    )

    
    spotify.playlist_add_items(# add the songs to the playlist
        playlist["id"],
        track_uris
    )

    return {
        "message": "Playlist created successfully!",
        "playlist_url": playlist["external_urls"]["spotify"],
        "songs_added": len(track_uris)
    }