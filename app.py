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
st.caption("Faites le pont entre vos Titres Likés Spotify et votre Collection / Wantlist Discogs.")

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

# --- FONCTIONS APIS AVEC CACHE ---
@st.cache_resource(show_spinner=False)
def init_discogs(token):
    return discogs_client.Client('DiscifyApp/1.0', user_token=token)

@st.cache_data(ttl=300, show_spinner=False)
def get_spotify_liked_tracks(_sp):
    results = _sp.current_user_saved_tracks(limit=50)
    tracks = []
    for item in results['items']:
        track = item['track']
        tracks.append({
            'id': track['id'],
            'title': track['name'],
            'artist': track['artists'][0]['name'],
            'album': track['album']['name'],
            'cover': track['album']['images'][0]['url'] if track['album']['images'] else None
        })
    return tracks

@st.cache_data(ttl=300, show_spinner=False)
def fetch_discogs_collection(_d_client, username):
    user = _d_client.user(username)
    collection = set()
    for item in user.collection_folders[0].releases:
        release = item.release
        title_str = f"{release.artists[0].name} - {release.title}".lower()
        collection.add(title_str)
    return collection

# --- CONTENU PRINCIPAL ---
if not (spotify_client_id and spotify_client_secret and discogs_token and discogs_username):
    st.info("👈 Veuillez renseigner vos identifiants Spotify et Discogs dans le menu de gauche (ou via les Secrets) pour démarrer.")
else:
    try:
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=spotify_client_id,
            client_secret=spotify_client_secret,
            redirect_uri=redirect_uri,
            scope="user-library-read"
        ))
        
        d_client = init_discogs(discogs_token)
        
        # Chargement rapide avec spinner
        with st.spinner("Chargement ultra-rapide de Spotify & Discogs..."):
            my_collection = fetch_discogs_collection(d_client, discogs_username)
            liked_tracks = get_spotify_liked_tracks(sp)

        st.success(f"Connecté ! {len(liked_tracks)} titres likés chargés.")
        st.markdown("---")

        # Affichage fluide sous forme de liste
        for track in liked_tracks:
            col_cover, col_details = st.columns([1, 4])
            
            with col_cover:
                if track['cover']:
                    st.image(track['cover'], use_column_width=True)
            
            with col_details:
                st.markdown(f"### **{track['title']}**")
                st.markdown(f"**Artiste :** {track['artist']} | **Album Spotify :** *{track['album']}*")
                
                # RECHERCHE À LA DEMANDE (évite de bloquer l'API)
                if st.button(f"🔍 Chercher les vinyles pour « {track['title']} »", key=f"search_{track['id']}"):
                    with st.spinner("Recherche des éditions sur Discogs..."):
                        search_query = f"{track['artist']} {track['title']}"
                        results = d_client.search(search_query, type='release', format='Vinyl')
                        
                        if not results:
                            st.warning("Aucun vinyle correspondant trouvé sur Discogs.")
                        else:
                            st.markdown("#### Éditions Vinyles trouvées :")
                            for rel in results[:5]:
                                rel_title = f"{rel.artists[0].name} - {rel.title}"
                                is_owned = rel_title.lower() in my_collection
                                year = rel.year if hasattr(rel, 'year') and rel.year else "Année N/A"
                                
                                c1, c2 = st.columns([3, 1])
                                with c1:
                                    if is_owned:
                                        st.markdown(f"🟢 **{rel_title}** ({year}) — *Déjà dans votre collection*")
                                    else:
                                        st.markdown(f"⚪ **{rel_title}** ({year})")
                                
                                with c2:
                                    if not is_owned:
                                        if st.button("➕ Wantlist", key=f"want_{track['id']}_{rel.id}"):
                                            d_client.user(discogs_username).wantlist.add(rel.id)
                                            st.toast(f"Ajouté à la Wantlist : {rel.title}")

            st.markdown("---")

    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")