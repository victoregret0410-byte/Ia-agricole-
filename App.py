# =========================================================
# IA AGRICOLE - STYLE CHATGPT (GROQ + LLAMA 3.2)
# Fichier : App.py
# =========================================================

import io
import os
import requests
import streamlit as st
import pandas as pd
import pdfplumber
from groq import Groq

# =========================================================
# CONFIG GLOBALE
# =========================================================

APP_NAME = "🌾 IA agricole – Chat"
APP_VERSION = "1.0.0"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# CLIENT GROQ
# =========================================================

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception:
    groq_client = None

# =========================================================
# SYSTEM PROMPT DE BASE
# =========================================================

BASE_SYSTEM_PROMPT = """
Tu es un assistant IA bienveillant, spécialisé pour aider les agriculteurs.
Tu peux répondre sur :
- les cultures, prairies, élevages (bovins, ovins, caprins, porcs, volailles…),
- la gestion technico-économique (produits, charges, marges, EBE…),
- l’organisation du travail et la sécurité,
- l’aide à la lecture de documents (factures, tableaux, PDF…).

Règles importantes :
- Tu restes toujours respectueux, neutre et non offensant.
- Tu n’attaques jamais une personne ou une catégorie de personnes.
- Tu n’encourages pas des pratiques dangereuses ou illégales.
- Tu ne promets jamais de résultat financier garanti.

Style :
- français simple, ton humain, comme un collègue de ferme,
- phrases courtes et claires,
- tu peux utiliser quelques emojis (🌾🐄📊💶💡⚠️✅) pour structurer,
- tu adaptes le niveau technique à la question.
"""

# =========================================================
# LANGUES, MODÈLES, MODES
# =========================================================

LANG_OPTIONS = {
    "Français": "fr",
    "English": "en",
    "Español": "es",
    "Deutsch": "de",
}

MODEL_OPTIONS = {
    "Groq – précis & rapide (LLaMA 3.2 90B)": {
        "id": "llama-3.2-90b-vision-preview",
        "temp": 0.25,
        "max_tokens": 800,
    },
    "Groq – léger (LLaMA 3.2 11B)": {
        "id": "llama-3.2-11b-vision-preview",
        "temp": 0.35,
        "max_tokens": 600,
    },
}

MODE_OPTIONS = [
    "Conseiller agricole général",
    "Technique élevage & fourrages",
    "Gestion & compta d’exploitation",
    "Organisation du travail",
]

# =========================================================
# STYLE VISUEL (BLANC, PROPRE, STYLE CHATGPT)
# =========================================================

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    .main {
        background-color: #ffffff;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }
    .stChatMessage {
        border-radius: 18px !important;
    }
    .stButton>button, .stDownloadButton>button {
        border-radius: 999px;
        padding: 0.35rem 1.2rem;
        font-weight: 600;
        border: 1px solid #e0e0e0;
        background: #f8f9fb;
    }
    .sidebar .sidebar-content {
        background-color: #fafafa;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# FONCTIONS UTILITAIRES : FICHIERS
# =========================================================

def resume_csv(file) -> str:
    """Retourne un petit résumé d'un CSV pour le contexte IA."""
    try:
        df = pd.read_csv(file)
    except Exception:
        file.seek(0)
        df = pd.read_csv(file, sep=";")
    apercu = df.head(10)
    return (
        f"Fichier CSV : {getattr(file, 'name', 'inconnu')}\n"
        f"Colonnes : {list(df.columns)}\n"
        f"Extrait (10 lignes) :\n{apercu.to_markdown(index=False)}"
    )


def resume_pdf(file) -> str:
    """Retourne le texte des 2 premières pages d’un PDF."""
    texte_total = []
    with pdfplumber.open(file) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= 2:
                break
            texte_page = page.extract_text() or ""
            texte_total.append(f"--- Page {i+1} ---\n{texte_page}")
    return (
        f"Fichier PDF : {getattr(file, 'name', 'inconnu')}\n"
        "Extraits des 2 premières pages :\n" + "\n\n".join(texte_total)
    )

# =========================================================
# MÉTÉO (OPEN-METEO)
# =========================================================

def get_meteo(location: str):
    """Météo détaillée via Open-Meteo pour une ville donnée."""
    if not location:
        return None, "Aucune localisation fournie."

    try:
        # Géocodage : recherche de plusieurs villes
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        params_geo = {
            "name": location,
            "count": 5,
            "language": "fr",
            "format": "json",
        }
        r_geo = requests.get(geo_url, params=params_geo, timeout=8)
        if r_geo.status_code != 200:
            return None, "Impossible de joindre le service de géocodage météo."

        data_geo = r_geo.json()
        if "results" not in data_geo or not data_geo["results"]:
            return None, f"Aucune localisation trouvée pour « {location} »."

        lieux = data_geo["results"]
        loc0 = lieux[0]

        lat = loc0["latitude"]
        lon = loc0["longitude"]

        meteo_url = "https://api.open-meteo.com/v1/forecast"
        params_met = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
            "current_weather": "true",
            "timezone": "auto",
        }
        r_met = requests.get(meteo_url, params=params_met, timeout=8)
        if r_met.status_code != 200:
            return None, "Impossible de joindre le service météo."

        data_met = r_met.json()
        current = data_met.get("current_weather", {})
        daily = data_met.get("daily", {})

        df_daily = None
        try:
            df_daily = pd.DataFrame({
                "Date": daily["time"],
                "T max (°C)": daily["temperature_2m_max"],
                "T min (°C)": daily["temperature_2m_min"],
                "Pluie jour (mm)": daily["precipitation_sum"],
                "Vent max (km/h)": daily["wind_speed_10m_max"],
            })
        except Exception:
            pass

        return {
            "lieux": lieux,
            "current": current,
            "daily_df": df_daily,
        }, None

    except Exception as e:
        return None, f"Erreur météo : {e}"

# =========================================================
# ÉTAT : MULTI-CONVERSATIONS (STYLE CHATGPT)
# =========================================================

if "conversations" not in st.session_state:
    st.session_state.conversations = []  # liste de dicts

if "current_conv_index" not in st.session_state:
    st.session_state.current_conv_index = 0


def creer_conversation(titre: str | None = None):
    """Crée une nouvelle conversation avec un message d’accueil."""
    if titre is None:
        titre = f"Discussion {len(st.session_state.conversations) + 1}"

    message_welcome = {
        "role": "assistant",
        "content": (
            "Salut 👋\n\n"
            "Je suis ton **assistant IA agricole**. "
            "Explique-moi ta situation (ferme, cultures, élevage, papiers…) "
            "et on réfléchit ensemble, calmement."
        ),
    }

    conv = {
        "title": titre,
        "messages": [message_welcome],
        "file_context": [],
    }
    st.session_state.conversations.append(conv)
    st.session_state.current_conv_index = len(st.session_state.conversations) - 1


# Créer une première conversation si aucune
if not st.session_state.conversations:
    creer_conversation("Discussion 1")

# =========================================================
# CONSTRUCTION DES MESSAGES POUR L’IA
# =========================================================

def build_system_prompt(mode: str, lang_code: str) -> str:
    prompt = BASE_SYSTEM_PROMPT

    if mode == "Technique élevage & fourrages":
        prompt += """
Tu te concentres surtout sur l’élevage (bovins allaitants, laitiers, ovins, caprins, porcs, volailles…),
les rations, les fourrages, les bâtiments, la santé, la reproduction et l’organisation du travail en élevage.
"""
    elif mode == "Gestion & compta d’exploitation":
        prompt += """
Tu aides surtout sur la gestion économique :
produits, charges, marges, EBE, trésorerie, annuités, investissements prudents.
Tu expliques les mécanismes, mais tu ne donnes pas de conseil financier personnalisé.
"""
    elif mode == "Organisation du travail":
        prompt += """
Tu aides surtout sur l’organisation du travail :
planning, saisonnalité, sécurité, priorités, répartition des tâches.
"""

    if lang_code != "fr":
        prompt += f"\nTu réponds dans la langue de code « {lang_code} ».\n"

    return prompt


def build_messages(conv, mode: str, lang_code: str, style_reponse: str):
    messages = []

    # System
    messages.append({"role": "system", "content": build_system_prompt(mode, lang_code)})

    # Contexte fichiers (si des fichiers ont été analysés)
    if conv["file_context"]:
        extrait = "\n\n---\n\n".join(conv["file_context"][-3:])
        messages.append({
            "role": "system",
            "content": (
                "Contexte issu des fichiers fournis par l’agriculteur "
                "(tableaux, PDF, etc.) :\n\n" + extrait
            ),
        })

    # Historique : on ne garde que les 12 derniers messages pour aller vite
    derniers = conv["messages"][-12:]
    for m in derniers:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})

    # Style de réponse
    if style_reponse == "Réponse rapide":
        messages.append({
            "role": "system",
            "content": "Réponds de façon claire et assez courte (2 à 4 paragraphes max).",
        })
    else:
        messages.append({
            "role": "system",
            "content": "Tu peux développer davantage, tout en restant simple et structuré.",
        })

    return messages


def appeler_modele(conv, mode: str, lang_code: str, style_reponse: str, model_label: str) -> str:
    if groq_client is None:
        return (
            "❌ Impossible de contacter le modèle pour l’instant.\n\n"
            "Vérifie que ta clé `GROQ_API_KEY` est bien configurée dans les *Secrets* de Streamlit "
            "et que la librairie `groq` est installée dans `requirements.txt`."
        )

    model_conf = MODEL_OPTIONS[model_label]
    msgs = build_messages(conv, mode, lang_code, style_reponse)

    try:
        completion = groq_client.chat.completions.create(
            model=model_conf["id"],
            messages=msgs,
            temperature=model_conf["temp"],
            max_tokens=model_conf["max_tokens"],
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur lors de l’appel au modèle Groq : {e}"

# =========================================================
# BARRE LATÉRALE (STYLE CHATGPT)
# =========================================================

with st.sidebar:
    st.title("🌾 IA agricole")
    st.caption(f"Version {APP_VERSION}")

    # Nouveau chat
    if st.button("➕ Nouveau chat"):
        creer_conversation()

    st.markdown("---")

    # Liste des conversations
    labels = [c["title"] for c in st.session_state.conversations]
    idx = st.session_state.current_conv_index
    if idx >= len(labels):
        idx = len(labels) - 1

    selected = st.radio(
        "Mes discussions",
        options=list(range(len(labels))),
        format_func=lambda i: labels[i],
        index=idx,
    )
    st.session_state.current_conv_index = selected
    conv = st.session_state.conversations[selected]

    st.markdown("---")

    # Paramètres de l’IA
    langue_label = st.selectbox("🌍 Langue de réponse", list(LANG_OPTIONS.keys()), index=0)
    lang_code = LANG_OPTIONS[langue_label]

    mode = st.radio("🎯 Mode de conseil", MODE_OPTIONS, index=0)

    model_label = st.selectbox("🧠 Modèle Groq", list(MODEL_OPTIONS.keys()), index=0)

    style_reponse = st.radio(
        "✏️ Style de réponse",
        ["Réponse rapide", "Plus détaillée"],
        index=0,
    )

    st.markdown("---")
    st.caption(
        "💡 Une discussion = un sujet (ex : marges 2025, projet bâtiment, organisation travail…).\n"
        "Tu peux créer plusieurs chats et revenir sur chacun."
    )

# =========================================================
# ZONE PRINCIPALE : CHAT + OUTILS (UNE SEULE PAGE)
# =========================================================

st.title("💬 Chat IA agricole")

# ----------------------- AFFICHAGE DU CHAT -----------------------

# Afficher l’historique
for msg in conv["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Saisie utilisateur
user_input = st.chat_input("Écris ta question ou ta situation ici…")

if user_input:
    # Ajouter le message utilisateur
    conv["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Réponse IA
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("Je réfléchis à ta situation… ⏳")

        answer = appeler_modele(
            conv=conv,
            mode=mode,
            lang_code=lang_code,
            style_reponse=style_reponse,
            model_label=model_label,
        )

        placeholder.markdown(answer)

    conv["messages"].append({"role": "assistant", "content": answer})

# Sauvegarde de la conversation
st.session_state.conversations[st.session_state.current_conv_index] = conv

# =========================================================
# OUTILS SOUS LE CHAT (OPTIONNELS, COMME DES "TOOLS")
# =========================================================

st.markdown("---")
st.subheader("🧰 Outils pratiques (optionnel)")

col1, col2 = st.columns(2)

# ---------- COLONNE 1 : FICHIERS ----------
with col1:
    st.markdown("### 📂 Fichiers (PDF / CSV)")
    uploaded_files = st.file_uploader(
        "Dépose ici tes PDF ou CSV (dossiers, marges, factures, bilans…).",
        type=["csv", "pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("Analyser les fichiers"):
        resumes = []
        for f in uploaded_files:
            try:
                data = f.read()
                if f.name.lower().endswith(".csv"):
                    resume = resume_csv(io.BytesIO(data))
                else:
                    resume = resume_pdf(io.BytesIO(data))
                resumes.append(resume)
            except Exception as e:
                resumes.append(f"Impossible de lire le fichier {f.name} : {e}")

        conv["file_context"].extend(resumes)
        st.session_state.conversations[st.session_state.current_conv_index] = conv

        st.success("Fichiers analysés. L’IA tiendra compte de ces informations dans ses réponses.")
        for r in resumes:
            st.code(r[:1200])

# ---------- COLONNE 2 : METEO ----------
with col2:
    st.markdown("### 🌦️ Météo agricole détaillée")

    loc = st.text_input("Ville / commune", placeholder="Ex : Lisieux, Limoges, Alençon…")

    if st.button("Voir la météo"):
        info, err = get_meteo(loc)
        if err:
            st.error(err)
        elif not info:
            st.error("Impossible de récupérer la météo.")
        else:
            lieux = info["lieux"]
            st.markdown("**Villes trouvées :**")
            villes_data = []
            for l in lieux:
                villes_data.append({
                    "Nom": l.get("name", ""),
                    "Pays": l.get("country", ""),
                    "Lat": l.get("latitude", ""),
                    "Lon": l.get("longitude", ""),
                })
            st.dataframe(pd.DataFrame(villes_data), use_container_width=True)

            current = info.get("current", {})
            if current:
                st.markdown("**Conditions actuelles (ville principale)**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Température (°C)", current.get("temperature", "NA"))
                with c2:
                    st.metric("Vent (km/h)", current.get("windspeed", "NA"))
                with c3:
                    st.metric("Code météo", current.get("weathercode", "NA"))

            df_daily = info.get("daily_df")
            if df_daily is not None:
                st.markdown("**Prévisions sur 5 jours (ville principale)**")
                st.dataframe(df_daily.head(5), use_container_width=True)

            st.caption(
                "💡 Météo issue d’Open-Meteo. Pour les décisions sensibles "
                "(récolte, traitements…), croise toujours avec ta station locale "
                "ou une appli météo dédiée."
            )
