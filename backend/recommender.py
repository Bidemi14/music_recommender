def recommended_songs(song_name, songs, knn, recommendation_features):

    matching_song = songs[
    songs['title'].str.strip().str.casefold() == song_name.strip().casefold()
]

    if matching_song.empty:
        return "Song not found"

    matching_song_index = matching_song.index[0]

    distances, indices = knn.kneighbors(
        recommendation_features.iloc[[matching_song_index]]
    )

    return songs.iloc[indices[0][1:]]