import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import discogs_client

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Discify",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🎵 Discify")
st.caption("Compare tes Titres Likés Spotify à ta Collection et ta Wantlist Discogs.")

# --- SIDEBAR : CONFIGURATION ET IDENTIFIANTS ---
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

# --- FONCTIONS AVEC CACHE INTELLIGENT ---
@st.cache_resource(show_spinner=False)
def init_discogs(token):
    return discogs_client.Client('DiscifyApp/1.0', user_token=token)

@st.cache_data(ttl=1800, show_spinner=False)
def get_all_spotify_liked_tracks(sp_id, sp_secret, uri):
    """Récupère l'intégralité des titres likés (pagination jusqu'à épuisement)."""
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=sp_id,
        client_secret=sp_secret,
        redirect_uri=uri,
        scope="user-library-read"
    ))
    
    tracks = []
    offset = 0
    limit = 50
    
    while True:
        results = sp.current_user_saved_tracks(limit=limit, offset=offset)
        items = results.get('items', [])
        if not items:
            break
            
        for item in items:
            track = item['track']
            tracks.append({
                'id': track['id'],
                'title': track['name'],
                'artist': track['artists'][0]['name'],
                'album': track['album']['name'],
                'cover': track['album']['images'][0]['url'] if track['album']['images'] else None
            })
        
        offset += limit
        if len(items) < limit:
            break
            
    return tracks

@st.cache_data(ttl=1800, show_spinner=False)
def get_discogs_collection_titles(token, username):
    """Récupère les 60 albums de la collection Discogs."""
    try:
        d = discogs_client.Client('DiscifyApp/1.0', user_token=token)
        user = d.user(username)
        collection_titles = set()
        
        for item in user.collection_folders[0].releases:
            rel = item.release
            # Format de recherche simple : artiste + titre
            full_title = f"{rel.artists[0].name} - {rel.title}".lower()
            collection_titles.add(full_title)
            
        return collection_titles
    except Exception:
        return set()

# --- CONTENU PRINCIPAL ---
if not (spotify_client_id and spotify_client_secret and discogs_token and discogs_username):
    st.info("👈 Renseigne tes identifiants dans la barre latérale ou les Secrets Streamlit pour démarrer.")
else:
    try:
        # Chargement avec indicateur
        with st.spinner("Chargement de tes 500 titres Spotify & de ta collection Discogs..."):
            liked_tracks = get_all_spotify_liked_tracks(spotify_client_id, spotify_client_secret, redirect_uri)
            my_discogs_collection = get_discogs_collection_titles(discogs_token, discogs_username)
            d_client = init_discogs(discogs_token)

        st.success(f"⚡ Connecté ! {len(liked_tracks)} titres Spotify et {len(my_discogs_collection)} albums Discogs en mémoire.")
        
        # Champ de recherche pour filtrer parmi les 500 titres
        search_filter = st.text_input("🔎 Filtrer tes titres Spotify (par artiste ou chanson) :", "")
        
        if search_filter:
            filtered_tracks = [t for t in liked_tracks if search_filter.lower() in t['title'].lower() or search_filter.lower() in t['artist'].lower()]
        else:
            filtered_tracks = liked_tracks[:30] # Affiche les 30 premiers pour un défilement ultra fluide
            st.caption("Affichage des 30 plus récents. Utilise la barre de recherche ci-dessus pour trouver un titre précis.")

        st.markdown("---")

        # Affichage des cartes de musique
        for track in filtered_tracks:
            col_cover, col_details = st.columns([1, 4])
            
            with col_cover:
                if track['cover']:
                    st.image(track['cover'], use_column_width=True)
            
            with col_details:
                st.markdown(f"### **{track['title']}**")
                st.markdown(f"**Artiste :** {track['artist']} | **Album :** *{track['album']}*")
                
                # Bouton de recherche d'édition vinyle sur Discogs
                if st.button(f"🔍 Chercher l'édition vinyle sur Discogs", key=f"search_{track['id']}"):
                    with st.spinner("Recherche des pressages..."):
                        search_query = f"{track['artist']} {track['title']}"
                        results = d_client.search(search_query, type='release', format='Vinyl')
                        
                        if not results:
                            st.warning("Aucun vinyle trouvé sur Discogs pour ce titre.")
                        else:
                            st.markdown("#### Pressages vinyles disponibles :")
                            for rel in results[:5]:
                                rel_title = f"{rel.artists[0].name} - {rel.title}"
                                is_in_collection = rel_title.lower() in my_discogs_collection
                                year = rel.year if hasattr(rel, 'year') and rel.year else "N/A"
                                
                                c1, c2 = st.columns([3, 1])
                                with c1:
                                    if is_in_collection:
                                        st.markdown(f"🟢 **{rel_title}** ({year}) — *Déjà dans ta collection !*")
                                    else:
                                        st.markdown(f"📀 **{rel_title}** ({year})")
                                
                                with c2:
                                    if not is_in_collection:
                                        if st.button("➕ Ajout Wantlist", key=f"want_{track['id']}_{rel.id}"):
                                            d_client.user(discogs_username).wantlist.add(rel.id)
                                            st.toast(f"Ajouté à ta Wantlist Discogs : {rel.title}")

            st.markdown("---")

    except Exception as e:
        st.error(f"Une erreur s'est produite lors de la connexion : {e}")