import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import MemoryCacheHandler
import discogs_client
from itertools import islice

# Configuration de la page
st.set_page_config(
    page_title="Discify",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("🎵 Discify")
st.caption("Compare tes titres likés Spotify avec ta collection & ta Wantlist Discogs.")

SPOTIFY_SCOPE = "user-library-read"

# --- SIDEBAR : CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")

    sp_id_default = st.secrets.get("SPOTIFY_CLIENT_ID", "") if "SPOTIFY_CLIENT_ID" in st.secrets else ""
    sp_secret_default = st.secrets.get("SPOTIFY_CLIENT_SECRET", "") if "SPOTIFY_CLIENT_SECRET" in st.secrets else ""
    sp_redirect_default = st.secrets.get("SPOTIFY_REDIRECT_URI", "") if "SPOTIFY_REDIRECT_URI" in st.secrets else ""
    dc_token_default = st.secrets.get("DISCOGS_TOKEN", "") if "DISCOGS_TOKEN" in st.secrets else ""
    dc_user_default = st.secrets.get("DISCOGS_USERNAME", "") if "DISCOGS_USERNAME" in st.secrets else ""

    spotify_client_id = st.text_input("Spotify Client ID", value=sp_id_default, type="password", key="sp_id")
    spotify_client_secret = st.text_input("Spotify Client Secret", value=sp_secret_default, type="password", key="sp_secret")
    spotify_redirect_uri = st.text_input(
        "Spotify Redirect URI",
        value=sp_redirect_default,
        key="sp_redirect",
        help="Doit être EXACTEMENT la même URL que celle enregistrée dans ton app sur le Spotify Developer Dashboard (ex: https://tonapp.streamlit.app)"
    )
    discogs_token = st.text_input("Discogs Personal Access Token", value=dc_token_default, type="password", key="dc_token")
    discogs_username = st.text_input("Nom d'utilisateur Discogs", value=dc_user_default, key="dc_user")

# --- CONTENU PRINCIPAL ---
if not (spotify_client_id and spotify_client_secret and spotify_redirect_uri and discogs_token and discogs_username):
    st.info("👈 Renseigne tes identifiants dans la barre latérale ou les Secrets Streamlit pour démarrer.")
else:
    try:
        d_client = discogs_client.Client('DiscifyApp/1.0', user_token=discogs_token.strip())

        # --- AUTH SPOTIFY (Authorization Code Flow, obligatoire pour lire les titres likés) ---
        auth_manager = SpotifyOAuth(
            client_id=spotify_client_id.strip(),
            client_secret=spotify_client_secret.strip(),
            redirect_uri=spotify_redirect_uri.strip(),
            scope=SPOTIFY_SCOPE,
            cache_handler=MemoryCacheHandler(),
            show_dialog=False,
        )

        if "sp_token_info" not in st.session_state:
            st.session_state.sp_token_info = None

        # Étape retour de redirection : Spotify renvoie ?code=... dans l'URL
        query_params = st.query_params
        auth_code = query_params.get("code")

        if st.session_state.sp_token_info is None and auth_code:
            token_info = auth_manager.get_access_token(auth_code, as_dict=True, check_cache=False)
            st.session_state.sp_token_info = token_info
            st.query_params.clear()
            st.rerun()

        if st.session_state.sp_token_info is None:
            auth_url = auth_manager.get_authorize_url()
            st.info("👋 Connecte-toi à Spotify pour afficher tes titres likés.")
            st.link_button("🔗 Se connecter à Spotify", auth_url)
            st.stop()

        # Rafraîchir le token si expiré
        token_info = st.session_state.sp_token_info
        if auth_manager.is_token_expired(token_info):
            token_info = auth_manager.refresh_access_token(token_info["refresh_token"])
            st.session_state.sp_token_info = token_info

        sp = spotipy.Spotify(auth=token_info["access_token"])

        st.success("⚡ Connecté à Spotify & Discogs !")

        # --- RÉCUPÉRATION DES TITRES LIKÉS ---
        if "saved_offset" not in st.session_state:
            st.session_state.saved_offset = 0
        if "saved_tracks" not in st.session_state:
            st.session_state.saved_tracks = []

        PAGE_SIZE = 20

        def load_more_liked_tracks():
            with st.spinner("Récupération de tes titres likés..."):
                results = sp.current_user_saved_tracks(limit=PAGE_SIZE, offset=st.session_state.saved_offset)
                for item in results.get("items", []):
                    t = item["track"]
                    if not t:
                        continue
                    st.session_state.saved_tracks.append({
                        'id': t['id'],
                        'title': t['name'],
                        'artist': t['artists'][0]['name'] if t['artists'] else "Artiste inconnu",
                        'album': t['album']['name'] if t['album'] else "",
                        'cover': t['album']['images'][0]['url'] if (t['album'] and t['album']['images']) else None
                    })
                st.session_state.saved_offset += PAGE_SIZE

        if not st.session_state.saved_tracks:
            load_more_liked_tracks()

        st.markdown("---")

        if not st.session_state.saved_tracks:
            st.warning("Aucun titre liké trouvé sur ton compte Spotify.")
        else:
            for track in st.session_state.saved_tracks:
                col_cover, col_details = st.columns([1, 4])

                with col_cover:
                    if track['cover']:
                        st.image(track['cover'], use_container_width=True)

                with col_details:
                    st.markdown(f"### **{track['title']}**")
                    st.markdown(f"**Artiste :** {track['artist']} | **Album :** *{track['album']}*")

                    if st.button("🔍 Chercher le vinyle sur Discogs", key=f"search_{track['id']}"):
                        with st.spinner("Recherche des pressages sur Discogs..."):
                            try:
                                d_results = d_client.search(f"{track['artist']} {track['title']}", type='release', format='Vinyl')
                                if not d_results:
                                    st.warning("Aucun vinyle trouvé sur Discogs.")
                                else:
                                    st.markdown("#### Pressages vinyles disponibles :")
                                    for rel in islice(d_results, 3):
                                        rel_title = f"{rel.artists[0].name} - {rel.title}"
                                        year = rel.year if hasattr(rel, 'year') and rel.year else "N/A"

                                        # Vérifie si ce release est déjà dans la collection Discogs
                                        in_collection = False
                                        try:
                                            coll_resp = d_client._get(
                                                f"/users/{discogs_username.strip()}/collection/releases/{rel.id}"
                                            )
                                            in_collection = bool(coll_resp.get("releases"))
                                        except Exception:
                                            in_collection = False

                                        c1, c2 = st.columns([3, 1])
                                        with c1:
                                            st.markdown(f"📀 **{rel_title}** ({year})")
                                        with c2:
                                            if in_collection:
                                                st.success("✅ Déjà possédé")
                                            else:
                                                if st.button("➕ Wantlist", key=f"want_{track['id']}_{rel.id}"):
                                                    d_client.user(discogs_username.strip()).wantlist.add(rel.id)
                                                    st.toast(f"Ajouté à la Wantlist : {rel.title}")
                            except Exception as err:
                                st.error(f"Erreur Discogs : {err}")

                st.markdown("---")

            if st.button("⬇️ Charger plus de titres likés"):
                load_more_liked_tracks()
                st.rerun()

    except Exception as e:
        st.error(f"Erreur de connexion : {e}")