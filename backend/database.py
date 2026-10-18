import sqlite3
from pathlib import Path

# Find the database file in  main project folder
DB_PATH = Path(__file__).resolve().parent.parent / "music.db"


connection = sqlite3.connect(DB_PATH)


connection.execute("PRAGMA foreign_keys = ON")


cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS playlists (
    playlist_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    playlist_name TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS playlist_songs (
    id INTEGER PRIMARY KEY,
    playlist_id INTEGER,
    song_title TEXT,
    artist_name TEXT,
    FOREIGN KEY (playlist_id)
        REFERENCES playlists(playlist_id)
        ON DELETE CASCADE
)
""")



cursor.execute("SELECT COUNT(*) FROM playlist_songs")
print("Songs:", cursor.fetchall())

cursor.execute("""SELECT song_title
FROM playlist_songs
""")
print("Songs:", cursor.fetchall())

connection.commit()

connection.close()