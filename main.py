import argparse
import plistlib
import csv
import os
import time
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv


SCOPE = "playlist-modify-public playlist-modify-private user-library-modify"

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET or not SPOTIFY_REDIRECT_URI:
    raise ValueError("Please set the Spotify API credentials in the .env file.")

def load_apple_music_library(xml_path):
    with open(xml_path, 'rb') as f:
        data = plistlib.load(f)
    tracks = data.get('Tracks', {})
    return tracks

def build_search_query(track):
    name = track.get('Name', '')
    artist = track.get('Artist', '')
    # album = track.get('Album', '')
    query = f"track:{name} artist:{artist}"
    return query

def search_spotify_track(sp, track):
    query = build_search_query(track)
    try:
        results = sp.search(q=query, type='track', limit=1)
    except Exception as e:
        print(f"Error during Spotify search for query [{query}]: {e}")
        return None

    items = results.get('tracks', {}).get('items', [])
    if items:
        return items[0]['id']
    return None

def migrate_library(library_path):
    print("Loading Apple Music library...")
    tracks = load_apple_music_library(library_path)
    print(f"Found {len(tracks)} tracks  in your library.")

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE
    ))
    
    track_ids_to_save = []
    track_mapping = {}
    
    kind_mapping = set()
    for apple_track_id, track in tracks.items():
        if 'Kind' in track: 
            kind = track['Kind']
            kind_mapping.add(kind)
        else:
            kind_mapping.add('none found')
        
    print("Migrating tracks and searching on Spotify...")
    for apple_track_id, track in tracks.items():
        if 'Kind' in track:
            kind = track['Kind']
            if 'Apple Music' not in kind and 'Protected' not in kind:
                print(f"Skipping non-Apple Music track: {track.get('Name')} by {track.get('Artist')}")
                continue
        
        spotify_track_id = search_spotify_track(sp, track)
        if spotify_track_id:
            track_mapping[str(apple_track_id)] = {
                'spotify_id': spotify_track_id,
                'date_added': track.get('Date Added'),
                'name': track.get('Name'),
                'artist': track.get('Artist')
            }
            print(f"Matched: {track.get('Name')} by {track.get('Artist')}")
            track_ids_to_save.append(spotify_track_id)
        else:
            print(f"Could not find match for: {track.get('Name')} by {track.get('Artist')}")

        time.sleep(0.1)
    
    print("\nAdding matched tracks to your Spotify library...")
    batch_size = 50 
    for i in range(0, len(track_ids_to_save), batch_size):
        batch = track_ids_to_save[i:i+batch_size]
        try:
            sp.current_user_saved_tracks_add(tracks=batch)
            print(f"Added batch {i//batch_size + 1} ({len(batch)} tracks)")
        except Exception as e:
            print(f"Error adding tracks to library: {e}")
        time.sleep(1) 
    
    export_mapping(track_mapping)
    

def export_mapping(track_mapping, csv_filename="apple_to_spotify_mapping.csv"):
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["AppleTrackID", "Track Name", "Artist", "Date Added", "SpotifyTrackID"])
        for apple_id, info in track_mapping.items():
            date_added = info['date_added']
            if isinstance(date_added, datetime):
                date_str = date_added.isoformat()
            else:
                date_str = str(date_added)
            writer.writerow([apple_id, info['name'], info['artist'], date_str, info['spotify_id']])
    print(f"Exported track mapping to {csv_filename}")

def main():
    parser = argparse.ArgumentParser(
        description="Migrate your Apple Music library and playlists to Spotify."
    )
    parser.add_argument(
        "--library_path", type=str, required=True,
        help="Path to your Apple Music (iTunes) XML library file."
    )
    args = parser.parse_args()
    migrate_library(args.library_path)

if __name__ == "__main__":
    main()
