document.addEventListener("DOMContentLoaded", function () {

    const songInput = document.getElementById("songInput");
    const recommendButton = document.getElementById("recommendButton");
    const results = document.getElementById("results");
    const savePlaylistButton = document.getElementById("savePlaylistButton");
    const playlistName = document.getElementById("playlistName");
    let recommendedSongs = [];



    recommendButton.addEventListener("click", async function () {

        const song = songInput.value.trim();

        if (!song) {
            alert("Please enter a song name");
            return;
        }
        recommendedSongs = [];

        results.textContent = "Finding recommendations...";

        try {
            const response = await fetch(
                `http://127.0.0.1:8001/recommend?song=${encodeURIComponent(song)}`
            );

            const data = await response.json();

            if (data.error) {
                results.textContent = data.error;
                return;
            }

            results.innerHTML = "";

            recommendedSongs = data.recommendations;

            data.recommendations.forEach(function (track) {

                const paragraph = document.createElement("p");
                paragraph.textContent = `${track.title} — ${track.artist_name}`;
                results.appendChild(paragraph);
            });

        } catch (error) {
            console.error(error);
            results.textContent = "Could not connect to the backend.";
        }

    });
    savePlaylistButton.addEventListener("click", async function () {

        const name = playlistName.value.trim();

        if (recommendedSongs.length === 0) {
            alert("Please generate recommendations first");
            return;
        }

        if (!name) {
            alert("Please enter a playlist name");
            return;
        }

        try {
    const response = await fetch("http://127.0.0.1:8001/playlists", {
        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            user_id: 101,
            playlist_name: name
        })
    });

    if (!response.ok) {
    throw new Error("Could not create playlist");
    }

    const data = await response.json();

const playlistId = data.playlist_id;

for (const song of recommendedSongs) {

    const songResponse = await fetch(
        `http://127.0.0.1:8001/playlists/${playlistId}/songs`,
        {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                song_title: song.title,
                artist_name: song.artist_name
            })
        }
    );

    if (!songResponse.ok) {
        throw new Error("Could not save a song");
    }
}

    alert("Playlist and songs saved successfully!");

    } catch (error) {
    console.error(error);
    alert("Something went wrong while saving the playlist.");
    }

    });

});