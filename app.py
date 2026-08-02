import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import discogs_client

# Configuration de la page
st.set_page_config(
    page_title="Discify",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🎵 Discify")
st.caption("Compare tes titres Spotify avec ta Wantlist Discogs.")

# --- SIDEBAR : CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")
    
    sp_id_default = st.secrets.get("SPOTIFY_CLIENT_ID", "") if "SPOTIFY_CLIENT_ID" in st.secrets else ""
    sp_secret_default = st.secrets.get("SPOTIFY_CLIENT_SECRET", "") if "SPOTIFY_CLIENT_SECRET" in st.secrets else ""
    dc_token_default = st.secrets.get("DISCOGS_TOKEN", "") if "DISCOGS_TOKEN" in st.secrets else ""
    dc_user_default = st.secrets.get("DISCOGS_USERNAME", "") if "DISCOGS_USERNAME" in st.secrets else ""

    spotify_client_id = st.text_input("Spotify Client ID", value=sp_id_default, type="password", key="sp_id")
    spotify_client_secret = st.text_input("Spotify Client Secret", value=sp_secret_default, type="password", key="sp_secret")
    discogs_token = st.text_input("Discogs Personal Access Token", value=dc_token_default, type="password", key="dc_token")
    discogs_username = st.text_input("Nom d'utilisateur Discogs", value=dc_user_default, key="dc_user")

# --- CONTENU PRINCIPAL ---
if not (spotify_client_id and spotify_client_secret and discogs_token and discogs_username):
    st.info("👈 Renseigne tes identifiants dans la barre latérale ou les Secrets Streamlit pour démarrer.")
else:
    try:
        # Initialisation sans popup OAuth
        auth_manager = SpotifyClientCredentials(
            client_id=spotify_client_id, 
            client_secret=spotify_client_secret
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        d_client = discogs_client.Client('DiscifyApp/1.0', user_token=discogs_token)

        st.success("⚡ Connecté à Spotify & Discogs !")
        
        # Champ de recherche
        search_query = st.text_input("🔎 Recherche une chanson ou un artiste sur Spotify :", value="Iron Maiden")
        
        if search_query.strip():
            with st.spinner("Recherche Spotify..."):
                # Précision explicite des paramètres q, limit et type
                results = sp.search(q=search_query.strip(), limit=15, type='track')
                tracks = []
                
                if results and 'tracks' in results and 'items' in results['tracks']:
                    for t in results['tracks']['items']:
                        tracks.append({
                            'id': t['id'],
                            'title': t['name'],
                            'artist': t['artists'][0]['name'] if t['artists'] else "Artiste inconnu",
                            'album': t['album']['name'] if t['album'] else "",
                            'cover': t['album']['images'][0]['url'] if (t['album'] and t['album']['images']) else None
                        })

            st.markdown("---")

            if not tracks:
                st.warning("Aucun résultat trouvé sur Spotify.")
            else:
                for track in tracks:
                    col_cover, col_details = st.columns([1, 4])
                    
                    with col_cover:
                        if track['cover']:
                            st.image(track['cover'], use_container_width=True)
                    
                    with col_details:
                        st.markdown(f"### **{track['title']}**")
                        st.markdown(f"**Artiste :** {track['artist']} | **Album :** *{track['album']}*")
                        
                        if st.button(f"🔍 Chercher le vinyle sur Discogs", key=f"search_{track['id']}"):
                            with st.spinner("Recherche des pressages sur Discogs..."):
                                try:
                                    d_results = d_client.search(f"{track['artist']} {track['title']}", type='release', format='Vinyl')
                                    if not d_results:
                                        st.warning("Aucun vinyle trouvé sur Discogs.")
                                    else:
                                        st.markdown("#### Pressages vinyles disponibles :")
                                        for rel in d_results[:3]:
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