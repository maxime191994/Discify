import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import discogs_client

# Configuration de la page
st.set_page_config(
    page_title="Discify",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🎵 Discify")
st.caption("Compare tes Titres Likés Spotify à ta Wantlist & Collection Discogs.")

# --- SIDEBAR : CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    sp_id_default = st.secrets.get("SPOTIFY_CLIENT_ID", "") if "SPOTIFY_CLIENT_ID" in st.secrets else ""
    sp_secret_default = st.secrets.get("SPOTIFY_CLIENT_SECRET", "") if "SPOTIFY_CLIENT_SECRET" in st.secrets else ""
    sp_uri_default = st.secrets.get("SPOTIFY_REDIRECT_URI", "https://localhost:8501/callback") if "SPOTIFY_REDIRECT_URI" in st.secrets else "https://localhost:8501/callback"
    dc_token_default = st.secrets.get("DISCOGS_TOKEN", "") if "DISCOGS_TOKEN" in st.secrets else ""
    dc_user_default = st.secrets.get("DISCOGS_USERNAME", "") if "DISCOGS_USERNAME" in st.secrets else ""

    spotify_client_id = st.text_input("Client ID", value=sp_id_default, type="password", key="sp_id")
    spotify_client_secret = st.text_input("Client Secret", value=sp_secret_default, type="password", key="sp_secret")
    redirect_uri = st.text_input("Redirect URI", value=sp_uri_default, key="sp_uri")
    discogs_token = st.text_input("Personal Access Token", value=dc_token_default, type="password", key="dc_token")
    discogs_username = st.text_input("Nom d'utilisateur Discogs", value=dc_user_default, key="dc_user")

# --- FONCTION SPOTIFY ULTRA SEKUR (RECUPERE LES 500 TITRES SANS BUG) ---
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_spotify_tracks(sp_id, sp_secret, uri):
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=sp_id,
        client_secret=sp_secret,
        redirect_uri=uri,
        scope="user-library-read"
    ))
    
    tracks = []
    offset = 0
    limit = 50
    
    # Sécurité : 10 boucles max (500 titres)
    for _ in range(10):
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        items = results.get('items', [])
        if not items:
            break
            
        for item in items:
            t = item['track']
            tracks.append({
                'id': t['id'],
                'title': t['name'],
                'artist': t['artists'][0]['name'],
                'album': t['album']['name'],
                'cover': t['album']['images'][0]['url'] if t['album']['images'] else None
            })
        
        offset += limit
        if len(items) < limit:
            break
            
    return tracks

# --- CONTENU PRINCIPAL ---
if not (spotify_client_id and spotify_client_secret and discogs_token and discogs_username):
    st.info("👈 Renseigne tes identifiants dans les Secrets ou le menu de gauche pour démarrer.")
else:
    try:
        # 1. Chargement garanti en 3 secondes de Spotify
        with st.spinner("Chargement de tes titres Spotify..."):
            liked_tracks = fetch_spotify_tracks(spotify_client_id, spotify_client_secret, redirect_uri)

        # 2. Client Discogs
        d_client = discogs_client.Client('DiscifyApp/1.0', user_token=discogs_token)

        st.success(f"⚡ Connecté ! {len(liked_tracks)} titres Spotify chargés.")
        
        # Filtre de recherche
        search_filter = st.text_input("🔎 Chercher parmi tes 500 titres :", "")
        
        if search_filter:
            filtered_tracks = [t for t in liked_tracks if search_filter.lower() in t['title'].lower() or search_filter.lower() in t['artist'].lower()]
        else:
            filtered_tracks = liked_tracks[:25] # Affiche 25 par 25 pour un défilement rapide
            st.caption("Affichage des 25 plus récents. Utilise la recherche ci-dessus pour trouver n'importe quelle chanson.")

        st.markdown("---")

        # Affichage
        for track in filtered_tracks:
            col_cover, col_details = st.columns([1, 4])
            
            with col_cover:
                if track['cover']:
                    st.image(track['cover'], use_column_width=True)
            
            with col_details:
                st.markdown(f"### **{track['title']}**")
                st.markdown(f"**Artiste :** {track['artist']} | **Album :** *{track['album']}*")
                
                if st.button(f"🔍 Chercher le vinyle sur Discogs", key=f"search_{track['id']}"):
                    with st.spinner("Recherche des pressages sur Discogs..."):
                        try:
                            search_query = f"{track['artist']} {track['title']}"
                            results = d_client.search(search_query, type='release', format='Vinyl')
                            
                            if not results:
                                st.warning("Aucun vinyle trouvé.")
                            else:
                                st.markdown("#### Pressages vinyles disponibles :")
                                for rel in results[:5]:
                                    rel_title = f"{rel.artists[0].name} - {rel.title}"
                                    year = rel.year if hasattr(rel, 'year') and rel.year else "N/A"
                                    
                                    c1, c2 = st.columns([3, 1])
                                    with c1:
                                        st.markdown(f"📀 **{rel_title}** ({year})")
                                    
                                    with c2:
                                        if st.button("➕ Wantlist", key=f"want_{track['id']}_{rel.id}"):
                                            d_client.user(discogs_username).wantlist.add(rel.id)
                                            st.toast(f"Ajouté à la Wantlist : {rel.title}")
                        except Exception as err:
                            st.error(f"Erreur Discogs : {err}")

            st.markdown("---")

    except Exception as e:
        st.error(f"Erreur de connexion : {e}")