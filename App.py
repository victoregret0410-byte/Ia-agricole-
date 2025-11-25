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

APP_NAME = "💬 IA Conseiller – Chat sérieux"
APP_VERSION = "2.0.0"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="💬",
    layout="centered",  # une seule colonne, comme ChatGPT mobile
)

# --------- Client Groq (clé à mettre dans les secrets Streamlit : GROQ_API_KEY) ----------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# =========================================================
# STYLE GLOBAL – sobre, propre, type ChatGPT
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
        max-width: 780px;
    }
    .stButton>button, .stDownloadButton>button {
        border-radius: 999px;
        padding: 0.35rem 1.2rem;
        font-weight: 600;
    }
    .app-title {
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .app-subtitle {
        color: #666;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# MODES, LANGUES, MODÈLES
# =========================================================

LANG_OPTIONS = {
    "Français": "fr",
    "English": "en",
    "Español": "es",
    "Deutsch": "de",
}

MODEL_OPTIONS = {
    "Groq – précis & rapide (LLaMA 3.1 70B)": {
        "id": model="llama-3.2-90b-vision-preview",
        "temp": 0.25,
        "max_tokens": 800,
    },
    "Groq – léger (LLaMA 3.2 3B)": {
        "id": "llama-3.2-3b-instruct",
        "temp": 0.35,
        "max_tokens": 600,
    },
}

MODE_PROMPTS = {
    "Chat général": """
Tu es une IA de conversation sérieuse, calme, jamais offensante.
Tu peux parler de tous les sujets, de façon claire et logique.
Quand tu ne sais pas, tu le dis franchement.
""",
    "Conseiller agricole": """
Tu es un conseiller agricole IA. Tu aides à :
- raisonner les cultures et rotations,
- réfléchir aux charges, marges, organisation de la ferme,
- améliorer l'élevage (bovins, ovins, caprins, volailles) sans donner de conseils vétérinaires dangereux,
- gagner du temps sur les papiers (tableaux, idées de factures, synthèses).
Tu expliques comme un collègue agriculteur expérimenté, sans jugement.
""",
    "Gestion & compta": """
Tu aides l'utilisateur à comprendre ses chiffres agricoles :
produits, charges, marges, EBE, remboursement des annuités.
Tu détailles les calculs étape par étape. Tu restes prudent :
tu ne remplaces pas un expert-comptable.
""",
    "Documents & administration": """
Tu aides à rédiger des textes sérieux : mails, lettres, comptes rendus,
procédures, fiches de poste. Tu peux proposer des structures de tableaux ou de factures.
Tu fais attention au ton (respectueux, neutre, professionnel).
""",
}

BASE_SYSTEM_PROMPT = """
Tu es une IA de conversation sérieuse, respectueuse, jamais offensante.
Interdiction de produire des propos haineux, discriminants, violents
ou illégaux. Tu refuses toute demande dangereuse.

Style :
- phrases assez courtes,
- explications claires, structurées,
- vocabulaire simple, adapté à un agriculteur ou à un professionnel,
- tu raisonnes réellement avant de répondre (pas de réponses aléatoires),
- tu expliques tes étapes de réflexion de manière résumée.
"""

# =========================================================
# FONCTIONS OUTILS
# =========================================================

def lire_csv(file) -> str:
    """Résumé texte d'un CSV pour donner du contexte à l'IA."""
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
        "Unité": [""],
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
    - cherche plusieurs villes proches,
    - renvoie la météo détaillée pour la première
      + la liste des villes trouvées.
    """
    if not location:
        return None, None, "Aucune localisation fournie."

    try:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        params_geo = {
            "name": location,
            "count": nb_villes,
            "language": "fr",
            "format": "json",
        }
        r_geo = requests.get(geo_url, params=params_geo, timeout=8)
        if r_geo.status_code != 200:
            return None, None, "Impossible de joindre le service de géocodage météo."

        data_geo = r_geo.json()
        if "results" not in data_geo or not data_geo["results"]:
            return None, None, f"Aucune ville trouvée pour « {location} »."

        villes = pd.DataFrame([{
            "Nom": r["name"],
            "Pays": r.get("country", ""),
            "Lat": r["latitude"],
            "Lon": r["longitude"],
        } for r in data_geo["results"]])

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
            "timezone": "auto",
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
            "daily_df": df_daily,
        }
        return info, villes, None
    except Exception as e:
        return None, None, f"Erreur météo : {e}"


# =========================================================
# ÉTAT DE SESSION : une seule conversation principale
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Bonjour 👋\n\nJe suis ton IA conseillère. Explique-moi ta situation ou ta question."}
    ]

if "file_context" not in st.session_state:
    st.session_state.file_context = []  # extraits de fichiers


# =========================================================
# SIDEBAR : réglages globaux
# =========================================================

with st.sidebar:
    st.markdown("### ⚙️ Réglages du chat")
    st.caption(f"Version {APP_VERSION}")

    langue = st.selectbox("Langue de réponse :", list(LANG_OPTIONS.keys()), index=0)
    mode = st.selectbox("Mode :", list(MODE_PROMPTS.keys()), index=1)
    modele_label = st.selectbox("Modèle IA :", list(MODEL_OPTIONS.keys()), index=0)

    if st.button("🔄 Réinitialiser la discussion"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Nouvelle discussion. Explique-moi ta situation."}
        ]
        st.session_state.file_context = []
        st.experimental_rerun()

    st.markdown("---")
    st.markdown(
        "L’IA utilise **Groq** (modèles LLaMA) : rapide et précis.\n\n"
        "Tu peux déposer des fichiers et demander de l’aide sur les chiffres ou les papiers."
    )

# =========================================================
# FONCTION : construire messages pour l’IA
# =========================================================

def construire_messages():
    lang_code = LANG_OPTIONS.get(langue, "fr")
    mode_prompt = MODE_PROMPTS.get(mode, "")

    messages = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT},
        {"role": "system", "content": f"Réponds en langue : {langue} (code {lang_code})."},
        {"role": "system", "content": mode_prompt},
    ]

    if st.session_state.file_context:
        contexte_text = (
            "Voici des extraits de documents fournis par l’utilisateur "
            "(tableaux, PDF, etc.). Utilise-les si c’est utile :\n\n"
            + "\n\n---\n\n".join(st.session_state.file_context[-3:])
        )
        messages.append({"role": "system", "content": contexte_text})

    dernier_messages = st.session_state.messages[-10:]
    for m in dernier_messages:
        if m["role"] in ("user", "assistant"):
            messages.append({"role": m["role"], "content": m["content"]})

    return messages


def appeler_groq():
    if client is None:
        return (
            "❌ Je ne peux pas répondre pour l’instant.\n\n"
            "La clé `GROQ_API_KEY` n'est pas configurée dans les *Secrets* Streamlit."
        )

    model_conf = MODEL_OPTIONS[modele_label]
    msgs = construire_messages()

    try:
        completion = client.chat.completions.create(
            model=model_conf["id"],
            messages=msgs,
            temperature=model_conf["temp"],
            max_tokens=model_conf["max_tokens"],
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur lors de l'appel au modèle Groq : {e}"


# =========================================================
# HEADER
# =========================================================

st.markdown("<div class='app-title'>💬 IA Conseiller – Chat sérieux</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='app-subtitle'>Une seule interface pour discuter, analyser tes chiffres, t'aider sur les papiers et la météo.</div>",
    unsafe_allow_html=True,
)
st.markdown("---")

# =========================================================
# AFFICHAGE DE LA CONVERSATION
# =========================================================

for message in st.session_state.messages:
    with st.chat_message("assistant" if message["role"] == "assistant" else "user"):
        st.markdown(message["content"])

# Champ de saisie
user_input = st.chat_input("Écris ta question ou ta situation ici…")

if user_input:
    texte = user_input.strip()
    if texte:
        st.session_state.messages.append({"role": "user", "content": texte})
        with st.chat_message("user"):
            st.markdown(texte)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("Je réfléchis à ta situation…")
            answer = appeler_groq()
            placeholder.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})

# =========================================================
# OUTILS : fichiers, factures, tableaux, météo
# =========================================================

st.markdown("---")
st.markdown("### 🧰 Outils pratiques (optionnel)")

with st.expander("📂 Fichiers (PDF / CSV) à analyser", expanded=False):
    uploaded_files = st.file_uploader(
        "Dépose ici tes dossiers, tableaux, relevés (PDF ou CSV) :",
        type=["pdf", "csv"],
        accept_multiple_files=True,
    )

    if uploaded_files and st.button("Analyser les fichiers"):
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

        st.session_state.file_context.extend(resumes)
        st.success("Fichiers analysés. L’IA en tiendra compte dans ses prochaines réponses.")
        for r in resumes:
            st.code(r[:1200])

with st.expander("🧾 Modèles de factures & tableaux de gestion", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧾 Modèle de facture"):
            df_fact = generer_modele_facture_df()
            st.dataframe(df_fact, use_container_width=True)
            csv_fact = df_fact.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Télécharger facture.csv",
                data=csv_fact,
                file_name="modele_facture.csv",
                mime="text/csv",
                use_container_width=True,
            )
    with col2:
        if st.button("📊 Modèles de tableaux de gestion"):
            modeles = generer_modeles_tableaux_gestion()
            for nom, df_mod in modeles.items():
                st.markdown(f"**{nom}**")
                st.dataframe(df_mod, use_container_width=True)
                csv_mod = df_mod.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"📥 Télécharger {nom}.csv",
                    data=csv_mod,
                    file_name=f"{nom}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

with st.expander("🌦️ Météo très précise (plusieurs villes)", expanded=False):
    loc = st.text_input("Ville / commune :", placeholder="Ex : Lisieux, Alençon, Limoges…")
    if st.button("Voir la météo"):
        info, villes_df, err = get_meteo_precise(loc)
        if err:
            st.error(err)
        else:
            if villes_df is not None and not villes_df.empty:
                st.markdown("**Villes trouvées :**")
                st.dataframe(villes_df, use_container_width=True)

            if info is None:
                st.error("Impossible de récupérer la météo détaillée.")
            else:
                st.success(f"Météo pour {info['nom']} ({info['pays']})")
                current = info.get("current", {})
                if current:
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.metric("Température (°C)", current.get("temperature", "NA"))
                    with c2:
                        st.metric("Vent (km/h)", current.get("windspeed", "NA"))
                    with c3:
                        st.metric("Code météo", current.get("weathercode", "NA"))

                df_daily = info.get("daily_df")
                if df_daily is not None:
                    st.markdown("**Prévisions 5 jours :**")
                    st.dataframe(df_daily.head(5), use_container_width=True)
                    st.caption(
                        "Source : Open-Meteo. Pour les décisions sensibles "
                        "(récolte, traitements), croise avec une appli météo locale."
                    )
