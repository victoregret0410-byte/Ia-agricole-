import streamlit as st
from groq import Groq
import pandas as pd
import pdfplumber
import io
import requests
import os

# =========================================================
# CONFIG GLOBALE
# =========================================================

APP_NAME = "🌾 IA agricole – Chat rapide"
APP_VERSION = "6.0.0"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Client Groq (clé dans les secrets Streamlit : GROQ_API_KEY)
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))


# =========================================================
# SYSTEM PROMPT (CERVEAU GÉNÉRAL)
# =========================================================

BASE_SYSTEM_PROMPT = """
Tu es un conseiller agricole IA francophone, bienveillant, jamais offensant.
Tu aides les agriculteurs à :
- mieux gérer leurs cultures, prairies, élevage (bovin, ovin, caprin, porc, volaille…),
- réfléchir à leur organisation de travail,
- comprendre leurs chiffres (produits, charges, marges, EBE…),
- gagner du temps sur les papiers (factures, tableaux, relevés…),
- penser leurs investissements avec prudence (sans faire de conseil financier risqué).

Style :
- français simple, ton humain, sans jugement,
- phrases courtes, claires, concrètes,
- tu expliques comme à un collègue agriculteur,
- tu utilises quelques emojis pour structurer (🌾🐄📊💶💡⚠️✅…),
- tu restes toujours respectueux, jamais offensant.
"""

# =========================================================
# STYLE GLOBAL
# =========================================================

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    body {
        background-color: #f5f7fb;
    }
    .main {
        background: #f5f7fb;
    }
    .stButton>button, .stDownloadButton>button {
        border-radius: 999px;
        padding: 0.35rem 1.2rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# FONCTIONS UTILITAIRES
# =========================================================

def lire_csv(file) -> str:
    """Résumé texte d'un CSV pour le contexte IA (10 lignes max)."""
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


def lire_pdf(file) -> str:
    """Extrait les 2 premières pages d'un PDF pour le contexte IA."""
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


def generer_modele_facture_df():
    """Modèle simple de facture agricole."""
    return pd.DataFrame({
        "Date": [""],
        "N° facture": [""],
        "Client": [""],
        "Adresse client": [""],
        "SIRET client": [""],
        "Description": [""],
        "Quantité": [0],
        "Unité": [""],  # t, kg, h, u...
        "Prix unitaire HT": [0.0],
        "TVA (%)": [20],
        "Total HT": [0.0],
        "Total TTC": [0.0],
        "Mode de règlement": [""],
        "Date d’échéance": [""],
    })


def generer_modeles_tableaux_gestion():
    """Quelques modèles de tableaux utiles (marges, trésorerie, élevage)."""
    df_marges = pd.DataFrame(columns=[
        "Année", "Atelier / Culture", "Surface_ha / Nb têtes",
        "Produit total €", "Charges opérationnelles €",
        "Charges de structure €", "Marge brute €", "EBE €",
        "Marge brute /ha ou /tête", "EBE /ha ou /tête"
    ])

    df_tresorerie = pd.DataFrame(columns=[
        "Date", "Type", "Catégorie", "Libellé",
        "Montant €", "Sens",
        "Moyen de paiement", "Atelier", "Observation"
    ])

    df_elevage = pd.DataFrame(columns=[
        "Année", "Espèce", "Atelier", "Nb animaux moyen",
        "GMQ (g/j) ou Prod. lait (kg/VL/an)",
        "IC / conso concentrés (kg/an)", "Taux de renouvellement (%)",
        "Taux de mortalité (%)", "Remarques techniques"
    ])

    return {
        "Suivi_marges": df_marges,
        "Trésorerie": df_tresorerie,
        "Elevage": df_elevage
    }


def texte_idees_schemas():
    return (
        "📈 **Idées de schémas pour organiser la ferme**\n\n"
        "1️⃣ Rotation des cultures\n"
        "2️⃣ Organisation du travail (quotidien / hebdo / saison)\n"
        "3️⃣ Flux en bâtiment (entrée → zones → sortie)\n\n"
        "Tu peux les dessiner sur papier ou dans Canva/PowerPoint."
    )


def get_meteo(location: str):
    """Mini météo via Open-Meteo."""
    if not location:
        return None, "Aucune localisation fournie."
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        params_geo = {
            "name": location,
            "count": 1,
            "language": "fr",
            "format": "json"
        }
        r_geo = requests.get(geo_url, params=params_geo, timeout=8)
        if r_geo.status_code != 200:
            return None, "Impossible de joindre le service de géocodage météo."

        data_geo = r_geo.json()
        if "results" not in data_geo or not data_geo["results"]:
            return None, f"Aucune localisation trouvée pour '{location}'."

        loc = data_geo["results"][0]
        lat = loc["latitude"]
        lon = loc["longitude"]
        nom = loc.get("name", location)
        pays = loc.get("country", "")

        meteo_url = "https://api.open-meteo.com/v1/forecast"
        params_met = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "current_weather": "true",
            "timezone": "auto"
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
            })
        except Exception:
            pass

        info = {
            "nom": nom,
            "pays": pays,
            "current": current,
            "daily_df": df_daily
        }
        return info, None
    except Exception as e:
        return None, f"Erreur météo : {e}"


# =========================================================
# ÉTAT : MULTI CONVERSATIONS (COMME CHATGPT)
# =========================================================

if "conversations" not in st.session_state:
    st.session_state.conversations = []  # liste de dict
if "current_conv_index" not in st.session_state:
    st.session_state.current_conv_index = 0


def creer_nouvelle_conversation(style: str = "general"):
    """Crée une nouvelle discussion avec un type (général, élevage, compta)."""
    if style == "elevage":
        titre = f"Élevage {len(st.session_state.conversations) + 1}"
        intro = (
            "On se concentre sur **l’élevage** (bovins, ovins, caprins, volailles…).\n\n"
            "Tu peux me parler de rations, bâtiments, reproduction, santé, organisation…"
        )
    elif style == "compta":
        titre = f"Compta {len(st.session_state.conversations) + 1}"
        intro = (
            "On se concentre sur **la gestion / compta** 📊💶.\n\n"
            "Donne-moi tes produits, charges, annuités… je t’aide à les lire et analyser."
        )
    else:
        style = "general"
        titre = f"Discussion {len(st.session_state.conversations) + 1}"
        intro = (
            "Salut 👋\n\n"
            "Tu peux me parler de ta ferme, de tes cultures, de ton élevage, "
            "de ton organisation ou de tes papiers. On regarde ça calmement."
        )

    conv = {
        "title": titre,
        "type": style,  # general / elevage / compta
        "messages": [
            {"role": "assistant", "content": intro},
        ],
        "fichiers_contextes": [],
    }
    st.session_state.conversations.append(conv)
    st.session_state.current_conv_index = len(st.session_state.conversations) - 1


# Première conversation au démarrage
if not st.session_state.conversations:
    creer_nouvelle_conversation("general")


# =========================================================
# BARRE LATÉRALE (LISTE DES CHATS)
# =========================================================

with st.sidebar:
    st.markdown("### 🌾 IA agricole – Chats")
    st.caption(f"Version {APP_VERSION}")

    st.markdown("#### ➕ Nouvelle discussion")
    c_new1, c_new2, c_new3 = st.columns(3)
    with c_new1:
        if st.button("Général"):
            creer_nouvelle_conversation("general")
    with c_new2:
        if st.button("Élevage"):
            creer_nouvelle_conversation("elevage")
    with c_new3:
        if st.button("Compta"):
            creer_nouvelle_conversation("compta")

    st.markdown("---")

    labels = [conv["title"] for conv in st.session_state.conversations]
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

    st.markdown("---")
    st.markdown(
        "**💡 Astuce :** une discussion = un sujet (élevage, compta, projet…).\n"
        "Tu peux en créer plusieurs et revenir dessus."
    )


# Conversation courante
conv = st.session_state.conversations[st.session_state.current_conv_index]


# =========================================================
# COULEURS SELON TYPE DE DISCUSSION
# =========================================================

def couleurs_par_type(t: str):
    if t == "elevage":
        return "#e4f5e9", "#f6fffa", "#ffffff", "#2e7d32"
    if t == "compta":
        return "#e3f2fd", "#f5fbff", "#ffffff", "#1565c0"
    # général
    return "#fff7e3", "#fffdf7", "#ffffff", "#d7961b"


grad_start, grad_mid, grad_end, accent = couleurs_par_type(conv.get("type", "general"))

st.markdown(
    f"""
    <style>
    .block-container {{
        background: linear-gradient(
            135deg,
            {grad_start} 0%,
            {grad_mid} 55%,
            {grad_end} 100%
        );
        padding-top: 1.2rem;
        padding-bottom: 3rem;
    }}
    h1, h2, h3, h4 {{
        color: {accent};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FONCTION POUR CONSTRUIRE LES MESSAGES (RAPIDE)
# =========================================================

def construire_messages_pour_ia(conv, style_reponse: str):
    """
    Pour aller vite : on envoie seulement :
    - le system prompt,
    - les 8 derniers messages de la conversation,
    - les 2 derniers contextes fichiers (si présents),
    + une consigne de style.
    """
    messages = [{"role": "system", "content": BASE_SYSTEM_PROMPT}]

    # on prend seulement les 8 derniers messages
    derniers = conv["messages"][-8:]
    for m in derniers:
        role = m["role"]
        if role not in ["user", "assistant"]:
            continue
        messages.append({"role": role, "content": m["content"]})

    # style de réponse
    if style_reponse == "Rapide et synthétique":
        messages.append({
            "role": "system",
            "content": "Réponds de façon claire, concrète et assez courte (2 à 4 paragraphes max)."
        })
    else:
        messages.append({
            "role": "system",
            "content": "Tu peux donner un peu plus de détails, tout en restant simple et structuré."
        })

    # contexte fichiers : seulement les 2 derniers
    if conv["fichiers_contextes"]:
        ctx = conv["fichiers_contextes"][-2:]
        contexte_text = (
            "Voici des extraits de fichiers fournis par l’agriculteur "
            "(tableaux, PDF, etc.). Utilise ce contexte si utile :\n\n"
            + "\n\n---\n\n".join(ctx)
        )
        messages.append({"role": "system", "content": contexte_text})

    return messages


# =========================================================
# LAYOUT PRINCIPAL : CHAT + OUTILS (UNE SEULE PAGE)
# =========================================================

col_chat, col_tools = st.columns([2.4, 1.6])

# ------------------ COLONNE GAUCHE : CHAT ------------------
with col_chat:
    st.title("💬 Chat IA agricole")

    style_reponse = st.radio(
        "Style de réponse :",
        options=["Rapide et synthétique", "Un peu plus détaillée"],
        horizontal=True,
    )

    st.markdown("---")

    # Afficher l'historique
    for msg in conv["messages"]:
        with st.chat_message("assistant" if msg["role"] == "assistant" else "user"):
            st.markdown(msg["content"])

    # Champ de saisie
    user_input = st.chat_input("Écris ta question ou ton problème ici…")

    if user_input:
        user_input = user_input.strip()
        conv["messages"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        messages_for_api = construire_messages_pour_ia(conv, style_reponse)

        # Appel modèle ultra rapide : Groq / llama-3.1-8b-instant
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("Je réfléchis à ta situation… ⏳")

            try:
                completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages_for_api,
                    temperature=0.3,
                    max_tokens=400,
                )
                answer = completion.choices[0].message.content
            except Exception as e:
                msg = str(e)
                if "invalid_api_key" in msg or "authentication" in msg.lower():
                    answer = (
                        "❌ Je ne peux pas répondre car la **clé GROQ_API_KEY** n’est pas valide.\n\n"
                        "➡️ Va dans les *Secrets* Streamlit et vérifie que tu as bien :\n"
                        "`GROQ_API_KEY = \"ta_cle_groq_ici\"`.\n"
                    )
                else:
                    answer = (
                        "❌ Impossible de contacter le modèle Groq pour l’instant.\n\n"
                        "Vérifie ta connexion internet et ta clé `GROQ_API_KEY`.\n\n"
                        f"(Détail technique : {e})"
                    )

            placeholder.markdown(answer)

        conv["messages"].append({"role": "assistant", "content": answer})

    # Sauvegarde
    st.session_state.conversations[st.session_state.current_conv_index] = conv


# ------------------ COLONNE DROITE : OUTILS ------------------
with col_tools:
    st.markdown("### 📂 Fichiers & outils")

    uploaded_files = st.file_uploader(
        "Dépose ici tes PDF ou CSV (dossiers, marges, factures...).",
        type=["csv", "pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("✅ Analyser les fichiers"):
        resumes = []
        for f in uploaded_files:
            try:
                data = f.read()
                if f.name.lower().endswith(".csv"):
                    resume = lire_csv(io.BytesIO(data))
                else:
                    resume = lire_pdf(io.BytesIO(data))
                resumes.append(resume)
            except Exception as e:
                resumes.append(f"Impossible de lire le fichier {f.name} : {e}")

        conv["fichiers_contextes"].extend(resumes)
        st.session_state.conversations[st.session_state.current_conv_index] = conv
        st.success("Fichiers analysés. L’IA tiendra compte de ces
