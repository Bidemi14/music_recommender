from fastapi import FastAPI,HTTPException 
import joblib
import pandas as pd
from pathlib import Path
from backend.recommender import recommended_songs
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "music.db"
class PlaylistCreate(BaseModel):
    user_id: int
    playlist_name: str

class SongCreate(BaseModel):
    song_title: str
    artist_name: str

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
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