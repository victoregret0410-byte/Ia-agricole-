# =========================================================
# IA AGRICOLE – CHAT STYLE CHATGPT (GROQ + LLAMA 3.2)
# Fichier : App.py
# =========================================================

import os
import io
import requests
import streamlit as st
import pandas as pd
import pdfplumber
from groq import Groq

# =========================================================
# CONFIG GLOBALE
# =========================================================

APP_NAME = "🌾 IA agricole – Conseiller intelligent"
APP_VERSION = "1.0.0"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# CLIENT GROQ (LLAMA 3.2)
# =========================================================

try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None


# =========================================================
# SYSTEM PROMPT DE BASE
# =========================================================

BASE_SYSTEM_PROMPT = """
Tu es un conseiller agricole IA francophone, calme et bienveillant.
Tu aides les agriculteurs à :
- mieux gérer leurs cultures, prairies, élevages (bovin, ovin, caprin, porc, volaille…),
- comprendre leurs chiffres (produits, charges, marges, EBE…),
- gagner du temps sur leurs papiers (factures, tableaux, relevés…),
- réfléchir à leurs investissements avec prudence (sans jamais donner de conseil financier risqué),
- organiser leur travail (planning, priorités, sécurité).

Règles de style :
- français simple, ton humain, comme un collègue de ferme,
- phrases courtes, concrètes, exemples pratiques,
- toujours respectueux, tu n’attaques jamais personne,
- tu évites tout ce qui peut être offensant ou discriminant,
- tu ne promets jamais de résultat financier garanti.

Tu peux utiliser quelques emojis pour structurer : 🌾🐄📊💶💡⚠️✅.
"""


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
    "Conseiller agricole complet",
    "Élevage & fourrages",
    "Compta & gestion",
    "Organisation du travail",
]


# =========================================================
# STYLES VISUELS
# =========================================================

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    .main {
        background-color: #f5f7fb;
    }
    .block-container {
        padding-top: 1.2rem;
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
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FONCTIONS UTILITAIRES : FICHIERS
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


def generer_tableaux_gestion():
    """Quelques modèles de tableaux utiles (marges, trésorerie, élevage)."""
    df_marges = pd.DataFrame(columns=[
        "Année", "Atelier / Culture", "Surface_ha / Nb têtes",
        "Produit total €", "Charges opérationnelles €",
        "Charges de structure €", "Marge brute €", "EBE €",
        "Marge brute /ha ou /tête", "EBE /ha ou /tête"
    ])

    df_tresorerie = pd.DataFrame(columns=[
        "Date", "Type", "Catégorie", "Libellé",
        "Montant €", "Sens (Entrée/Sortie)",
        "Moyen de paiement", "Atelier", "Observation"
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


def texte_idees_schemas():
    return (
        "📈 **Idées de schémas simples pour organiser la ferme**\n\n"
        "1️⃣ Rotation des cultures (parceles, successions, légumineuses…)\n"
        "2️⃣ Organisation du travail (journalier / hebdo / saison)\n"
        "3️⃣ Flux en bâtiment (entrées → zones → sorties, circulation des animaux)\n"
        "4️⃣ Schéma de trésorerie sur l’année (pics de dépenses / recettes)\n\n"
        "Tu peux les dessiner sur papier, tablette ou dans Canva / PowerPoint."
    )


# =========================================================
# MÉTÉO AGRICOLE (OPEN-METEO)
# =========================================================

def get_meteo(location: str):
    """Météo précise via Open-Meteo pour une ville donnée."""
    if not location:
        return None, "Aucune localisation fournie."
    try:
        # 1) Géocodage : trouver la latitude / longitude
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        params_geo = {
            "name": location,
            "count": 5,            # on récupère plusieurs villes possibles
            "language": "fr",
            "format": "json",
        }
        r_geo = requests.get(geo_url, params=params_geo, timeout=8)
        if r_geo.status_code != 200:
            return None, "Impossible de joindre le service de géocodage météo."

        data_geo = r_geo.json()
        if "results" not in data_geo or not data_geo["results"]:
            return None, f"Aucune localisation trouvée pour '{location}'."

        lieux = data_geo["results"]

        # 2) Pour la première ville, on récupère la météo détaillée
        loc0 = lieux[0]
        lat = loc0["latitude"]
        lon = loc0["longitude"]

        meteo_url = "https://api.open-meteo.com/v1/forecast"
        params_met = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
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

        info = {
            "lieux": lieux,
            "current": current,
            "daily_df": df_daily,
        }
        return info, None
    except Exception as e:
        return None, f"Erreur météo : {e}"


# =========================================================
# ÉTAT DE SESSION (MESSAGES + CONTEXTE FICHIERS)
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "file_context" not in st.session_state:
    st.session_state.file_context = []  # liste de résumés de fichiers


# =========================================================
# CONSTRUCTION DES MESSAGES POUR GROQ
# =========================================================

def construire_system_prompt(mode: str, lang_code: str) -> str:
    prompt = BASE_SYSTEM_PROMPT

    if mode == "Élevage & fourrages":
        prompt += """
Tu te concentres surtout sur l’élevage (bovin, ovin, caprin, porcs, volailles…) :
rations, fourrages, bâtiments, reproduction, santé, organisation du travail en élevage.
"""
    elif mode == "Compta & gestion":
        prompt += """
Tu aides surtout sur la gestion économique :
produits, charges, marges, EBE, trésorerie, annuités, investissements prudents.
Tu ne donnes pas de conseil financier personnalisé, mais tu expliques les mécanismes.
"""
    elif mode == "Organisation du travail":
        prompt += """
Tu aides à organiser le travail :
planning, saisonnalité, sécurité, priorités, répartition des tâches.
"""

    if lang_code != "fr":
        prompt += f"\nTu réponds dans la langue : code '{lang_code}'.\n"

    return prompt


def construire_messages(mode: str, lang_code: str, style_reponse: str):
    messages = []

    # system prompt
    system_content = construire_system_prompt(mode, lang_code)
    messages.append({"role": "system", "content": system_content})

    # contexte fichiers (si présent)
    if st.session_state.file_context:
        extrait = "\n\n---\n\n".join(st.session_state.file_context[-3:])
        messages.append({
            "role": "system",
            "content": (
                "Contexte issu des fichiers fournis par l’agriculteur "
                "(tableaux, PDF, etc.) :\n\n" + extrait
            ),
        })

    # historique : on garde les 12 derniers messages
    derniers = st.session_state.messages[-12:]
    for m in derniers:
        messages.append({"role": m["role"], "content": m["content"]})

    # style court / long
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


def appeler_groq(mode: str, lang_code: str, style_reponse: str, modele_label: str) -> str:
    if client is None:
        return (
            "❌ Je ne peux pas répondre pour l’instant.\n\n"
            "La clé `GROQ_API_KEY` n'est pas configurée dans les *Secrets* Streamlit."
        )

    model_conf = MODEL_OPTIONS[modele_label]
    msgs = construire_messages(mode, lang_code, style_reponse)

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
# BARRE LATÉRALE (PARAMÈTRES)
# =========================================================

with st.sidebar:
    st.title("🌾 IA agricole")
    st.caption(f"Version {APP_VERSION}")

    langue_label = st.selectbox("🌍 Langue de réponse", list(LANG_OPTIONS.keys()), index=0)
    lang_code = LANG_OPTIONS[langue_label]

    mode = st.radio("🎯 Mode d’aide", MODE_OPTIONS, index=0)

    modele_label = st.selectbox("🧠 Modèle IA (Groq)", list(MODEL_OPTIONS.keys()), index=0)

    style_reponse = st.radio(
        "✏️ Style de réponse",
        ["Réponse rapide", "Plus détaillée"],
        index=0,
    )

    st.markdown("---")
    st.markdown(
        "💡 *Astuce : tu peux charger des fichiers (PDF, CSV) dans la colonne de droite, "
        "je m’en servirai comme contexte pour analyser tes chiffres ou tes documents.*"
    )


# =========================================================
# LAYOUT PRINCIPAL : CHAT + OUTILS
# =========================================================

col_chat, col_tools = st.columns([2.3, 1.7])

# ----------------------- COLONNE CHAT ----------------------
with col_chat:
    st.title("💬 Conseiller agricole IA")

    if not st.session_state.messages:
        # message d’accueil
        texte_bienvenue = (
            "Salut 👋\n\n"
            "Je suis ton **conseiller agricole IA**.\n\n"
            "Tu peux me parler de ta ferme, de tes cultures, de ton élevage, "
            "de ta trésorerie ou de tes papiers. On regarde ça calmement, "
            "sans jugement, étape par étape."
        )
        st.session_state.messages.append({"role": "assistant", "content": texte_bienvenue})

    # afficher l'historique
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # champ de saisie
    user_input = st.chat_input("Écris ta question ou ta situation ici…")

    if user_input:
        # ajouter le message utilisateur
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # réponse IA
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("Je réfléchis à ta situation… ⏳")

            answer = appeler_groq(
                mode=mode,
                lang_code=lang_code,
                style_reponse=style_reponse,
                modele_label=modele_label,
            )

            placeholder.markdown(answer)

        st.session_state.messages.append({"role": "assistant", "content": answer})


# ----------------------- COLONNE OUTILS --------------------
with col_tools:
    st.markdown("### 🧰 Outils pratiques (optionnel)")

    # ---------- FICHIERS ----------
    st.markdown("#### 📂 Fichiers (PDF / CSV)")

    uploaded_files = st.file_uploader(
        "Dépose ici tes PDF ou CSV (dossiers, marges, factures, bilans…).",
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

        st.session_state.file_context.extend(resumes)
        st.success("Fichiers analysés. L’IA tiendra compte de ces infos.")
        for r in resumes:
            st.code(r[:1200])

    st.markdown("---")

    # ---------- FACTURES & TABLEAUX ----------
    st.markdown("#### 🧾 Factures & tableaux de gestion")

    if st.button("🧾 Générer un modèle de facture"):
        df_fact = generer_modele_facture_df()
        st.markdown("Modèle de facture agricole :")
        st.dataframe(df_fact, use_container_width=True)
        csv_fact = df_fact.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Télécharger `modele_facture_agricole.csv`",
            data=csv_fact,
            file_name="modele_facture_agricole.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if st.button("📊 Générer des tableaux de gestion"):
        modeles = generer_tableaux_gestion()
        for nom, df_mod in modeles.items():
            st.markdown(f"**{nom}**")
            st.dataframe(df_mod, use_container_width=True)
            csv_mod = df_mod.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"📥 Télécharger `{nom}.csv`",
                data=csv_mod,
                file_name=f"{nom}.csv",
                mime="text/csv",
                use_container_width=True,
            )

    if st.button("📈 Idées de schémas pour la ferme"):
        st.markdown(texte_idees_schemas())

    st.markdown("---")

    # ---------- METEO ----------
    with st.expander("🌦️ Météo agricole détaillée", expanded=False):
        loc = st.text_input("Ville / commune", placeholder="Ex : Lisieux, Limoges, Alençon…")
        if st.button("Voir la météo", key="btn_meteo"):
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
                    "(récolte, traitements…), croise toujours avec ta station météo locale "
                    "ou une appli dédiée."
                )
