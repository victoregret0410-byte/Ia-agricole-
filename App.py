import os
import io
import requests
import streamlit as st
from groq import Groq
import pandas as pd
import pdfplumber

# =========================================================
# CONFIG GLOBALE
# =========================================================

APP_NAME = "💬 Conseiller IA – agricole & général"
APP_VERSION = "8.0.0"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Client Groq (clé dans les secrets Streamlit : GROQ_API_KEY)
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))


# =========================================================
# STYLE GLOBAL – look type ChatGPT, tout blanc
# =========================================================

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        background-color: #ffffff;
    }
    .main {
        background-color: #ffffff;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        max-width: 900px;
    }
    .stButton>button, .stDownloadButton>button {
        border-radius: 999px;
        padding: 0.35rem 1.2rem;
        font-weight: 600;
    }
    .chat-title {
        font-size: 2rem;
        font-weight: 700;
    }
    .chat-subtitle {
        color: #666;
        font-size: 0.9rem;
        margin-bottom: 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# MODES, LANGUES, MODELES
# =========================================================

LANG_OPTIONS = {
    "Français": "fr",
    "English": "en",
    "Español": "es",
    "Deutsch": "de",
}

# Modèles Groq (gratuits) – tu peux en ajouter d'autres si tu veux
MODEL_OPTIONS = {
    "Groq – rapide (LLaMA 3.2 3B)": {
        "id": "llama-3.2-3b-instruct",
        "temp": 0.3,
        "max_tokens": 500,
    },
    "Groq – très précis (LLaMA 3.1 70B)": {
        "id": "llama-3.1-70b-versatile",
        "temp": 0.25,
        "max_tokens": 900,
    },
}

MODE_PROMPTS = {
    "Général": """
Tu es une IA de conversation générale, bienveillante, qui peut parler de n’importe quel sujet
dans la limite des règles de sécurité. Tu restes respectueuse et neutre.
Quand tu ne sais pas, tu le dis clairement.
""",
    "Conseiller agricole": """
Tu es un conseiller agricole IA. Tu aides à :
- raisonner les cultures (assolement, rotations, doses, charges, marges…),
- gérer les prairies et les stocks fourragers,
- améliorer l’élevage (bovins, ovins, caprins, volailles…) sur la technique de base,
- réfléchir au travail, à la sécurité, au confort de vie.
Tu expliques calmement, comme un collègue agriculteur expérimenté.
""",
    "Gestion & compta": """
Tu aides à lire les chiffres de l’exploitation : produits, charges, marges, EBE,
capacité de remboursement. Tu peux proposer des tableaux, des exemples de calcul,
mais tu ne remplaces pas un expert-comptable ou un conseiller de gestion.
Tu expliques chaque étape de calcul.
""",
    "Tech / documents": """
Tu aides à écrire et améliorer des documents (mails, courriers, rapports),
créer des modèles de factures, de tableaux, de check-lists, des procédures.
Tu fais attention à l’orthographe et à la clarté.
""",
}

BASE_SYSTEM_PROMPT = """
Tu es une IA de conversation, toujours calme et respectueuse.
Tu ne fais jamais de propos offensants, haineux ou discriminants.
Tu ne donnes pas de conseils dangereux (santé, violence, illégal…).

Tu expliques les choses avec :
- phrases courtes,
- vocabulaire simple,
- structure claire (titres, puces),
- quelques emojis pour aider à lire (🌾🐄📊💶💡⚠️✅…).

Tu dois privilégier la précision et le raisonnement logique
plutôt que des réponses vagues ou aléatoires.
Quand tu donnes un conseil, tu expliques d’abord le raisonnement.
"""


# =========================================================
# OUTILS : lecture fichiers, météo, modèles de tableaux, etc.
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
    """Modèle simple de facture (agricole ou autre)."""
    return pd.DataFrame({
        "Date": [""],
        "N° facture": [""],
        "Client": [""],
        "Adresse client": [""],
        "SIRET / TVA client": [""],
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
    """Modèles de tableaux utiles pour une ferme."""
    df_marges = pd.DataFrame(columns=[
        "Année", "Atelier / Culture", "Surface_ha / Nb têtes",
        "Produit total €", "Charges opérationnelles €",
        "Charges de structure €", "Marge brute €", "EBE €",
        "Marge brute /ha ou /tête", "EBE /ha ou /tête"
    ])

    df_tresorerie = pd.DataFrame(columns=[
        "Date", "Type (encaissement / décaissement)", "Catégorie",
        "Libellé", "Montant €", "Moyen de paiement", "Atelier", "Observation"
    ])

    df_elevage = pd.DataFrame(columns=[
        "Année", "Espèce", "Atelier", "Nb animaux moyen",
        "GMQ (g/j) ou Prod. lait (kg/VL/an)",
        "Conso concentrés (kg/an)", "Taux de renouvellement (%)",
        "Taux de mortalité (%)", "Remarques techniques"
    ])

    return {
        "Suivi_marges": df_marges,
        "Trésorerie": df_tresorerie,
        "Elevage": df_elevage,
    }


def get_meteo_precise(location: str, nb_villes: int = 5):
    """
    Météo précise via Open-Meteo :
    - cherche plusieurs villes proches (nb_villes),
    - renvoie la météo détaillée pour la première
      + une liste de villes proches à comparer.
    """
    if not location:
        return None, None, "Aucune localisation fournie."
    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        params_geo = {
            "name": location,
            "count": nb_villes,
            "language": "fr",
            "format": "json"
        }
        r_geo = requests.get(geo_url, params=params_geo, timeout=8)
        if r_geo.status_code != 200:
            return None, None, "Impossible de joindre le service de géocodage météo."

        data_geo = r_geo.json()
        if "results" not in data_geo or not data_geo["results"]:
            return None, None, f"Aucune localisation trouvée pour « {location} »."

        # Liste des villes proposées
        villes = pd.DataFrame([{
            "Nom": r["name"],
            "Pays": r.get("country", ""),
            "Lat": r["latitude"],
            "Lon": r["longitude"],
        } for r in data_geo["results"]])

        # On prend la première pour la météo détaillée
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
            return None, villes, "Impossible de joindre le service météo."

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
        return info, villes, None
    except Exception as e:
        return None, None, f"Erreur météo : {e}"


# =========================================================
# ÉTAT : multi-conversations type ChatGPT
# =========================================================

if "conversations" not in st.session_state:
    st.session_state.conversations = []

if "current_index" not in st.session_state:
    st.session_state.current_index = 0


def creer_nouvelle_conversation(title: str, mode: str, lang: str, model_label: str):
    conv = {
        "title": title,
        "mode": mode,
        "lang": lang,
        "model": model_label,
        "messages": [
            {
                "role": "assistant",
                "content": "Salut 👋\n\nExplique-moi ta situation, on va regarder ça calmement."
            }
        ],
        "fichiers_contextes": [],
    }
    st.session_state.conversations.append(conv)
    st.session_state.current_index = len(st.session_state.conversations) - 1


# Première discussion par défaut
if not st.session_state.conversations:
    creer_nouvelle_conversation(
        "Discussion 1",
        "Général",
        "Français",
        "Groq – très précis (LLaMA 3.1 70B)",
    )


# =========================================================
# SIDEBAR : langues, modes, modèles, listes de chats
# =========================================================

with st.sidebar:
    st.markdown("### 💬 Conseiller IA")
    st.caption(f"Version {APP_VERSION}")

    lang_choice = st.selectbox("Langue :", list(LANG_OPTIONS.keys()))
    mode_choice = st.selectbox("Mode :", list(MODE_PROMPTS.keys()))
    model_choice = st.selectbox("Version d’IA :", list(MODEL_OPTIONS.keys()))

    st.markdown("---")
    if st.button("➕ Nouvelle discussion"):
        titre = f"{mode_choice} – {lang_choice} #{len(st.session_state.conversations) + 1}"
        creer_nouvelle_conversation(titre, mode_choice, lang_choice, model_choice)

    st.markdown("##### Mes discussions")
    labels = [c["title"] for c in st.session_state.conversations]
    idx = st.session_state.current_index
    if idx >= len(labels):
        idx = len(labels) - 1
    selected = st.radio(
        "",
        options=list(range(len(labels))),
        format_func=lambda i: labels[i],
        index=idx,
    )
    st.session_state.current_index = selected

    st.markdown("---")
    st.markdown(
        "ℹ️ L’IA utilise **Groq** (modèles LLaMA) : rapide et gratuit.\n"
        "Pour plus de précision, choisis le modèle 70B."
    )

# Conversation active
conv = st.session_state.conversations[st.session_state.current_index]

# On synchronise ce que l’utilisateur a choisi dans la sidebar
conv["mode"] = mode_choice
conv["lang"] = lang_choice
conv["model"] = model_choice


# =========================================================
# CONSTRUCTION DES MESSAGES POUR L’IA
# =========================================================

def construire_messages(conv):
    lang_code = LANG_OPTIONS.get(conv["lang"], "fr")
    mode_prompt = MODE_PROMPTS.get(conv["mode"], "")

    messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"La langue de réponse doit être : {conv['lang']} (code {lang_code})."
        },
        {"role": "system", "content": mode_prompt},
    ]

    # Contexte fichiers (2 derniers seulement pour aller vite)
    if conv["fichiers_contextes"]:
        ctx = conv["fichiers_contextes"][-2:]
        contexte_text = (
            "Voici des extraits de documents fournis par l’utilisateur "
            "(tableaux, PDF, etc.). Utilise-les si c’est utile :\n\n"
            + "\n\n---\n\n".join(ctx)
        )
        messages.append({"role": "system", "content": contexte_text})

    # 10 derniers messages
    derniers = conv["messages"][-10:]
    for m in derniers:
        if m["role"] in ["user", "assistant"]:
            messages.append({"role": m["role"], "content": m["content"]})

    return messages


def appeler_modele(conv):
    model_conf = MODEL_OPTIONS[conv["model"]]
    messages_for_api = construire_messages(conv)

    try:
        completion = client.chat.completions.create(
            model=model_conf["id"],
            messages=messages_for_api,
            temperature=model_conf["temp"],
            max_tokens=model_conf["max_tokens"],
        )
        return completion.choices[0].message.content
    except Exception as e:
        msg = str(e)
        if "api_key" in msg.lower() or "authentication" in msg.lower():
            return (
                "❌ Je ne peux pas répondre car la **clé GROQ_API_KEY** n’est pas valide.\n\n"
                "Va dans les *Secrets* Streamlit et vérifie que tu as bien :\n"
                '`GROQ_API_KEY = "gsk_........"`'
            )
        return (
            "❌ Impossible de contacter le modèle Groq pour l’instant.\n\n"
            f"(Détail technique : {e})"
        )


# =========================================================
