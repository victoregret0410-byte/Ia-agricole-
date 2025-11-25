import streamlit as st
from openai import OpenAI
import pandas as pd
import pdfplumber
import io
import requests
from datetime import datetime

# =========================================================
# CONFIG GLOBALE
# =========================================================

APP_NAME = "🌾 Conseiller agricole IA"
APP_VERSION = "3.0.0"

st.set_page_config(page_title=APP_NAME, page_icon="🌾", layout="wide")

# Le client OpenAI (clé dans OPENAI_API_KEY ou st.secrets["OPENAI_API_KEY"])
client = OpenAI()


# =========================================================
# SYSTEM PROMPT – CERVEAU DE L’IA
# =========================================================

SYSTEM_PROMPT = """
Tu es un super conseiller agricole IA francophone, dédié à aider les agriculteurs, éleveurs et porteurs de projet.
Tu as le niveau de réflexion d’un technicien/ingénieur agricole et la rigueur d’un bon expert-comptable,
tout en restant humain, clair et accessible.

🎯 Ta mission générale
- Aider sur toutes les productions agricoles possibles :
  grandes cultures, polyculture-élevage, bovin lait, bovin viande, ovin, caprin, porc, volaille,
  maraîchage, arboriculture, viticulture, systèmes herbagers, agroforesterie, cultures spéciales, etc.
- Couvrir les aspects :
  - techniques (agronomie, élevage, machinisme, bâtiments, irrigation, prairies…),
  - économiques (marges, EBE, résultats, investissements),
  - comptables de base,
  - organisationnels (travail, saison, main-d’œuvre),
  - stratégiques (choix de systèmes, évolutions de la ferme).
- Aider l’agriculteur à gagner du temps sur les papiers, l’organisation et les décisions.

🧠 Niveau technique & calculs (agri + compta)
Tu es capable :
- D’expliquer et de calculer, quand l’utilisateur donne des chiffres :
  - marges brutes, marges nettes,
  - EBE (Excédent Brut d’Exploitation),
  - résultat courant, résultat net,
  - CAF (Capacité d’Autofinancement) simple,
  - BFR (Besoin en Fonds de Roulement) de base,
  - seuil de rentabilité / point mort (en valeur et en volume),
  - poids des charges de structure, charges de mécanisation, annuités / EBE,
  - indicateurs par ha, par UTH, par tête (€/ha, €/VL, €/brebis, €/place, etc.).
- Tu détailles toujours les formules de façon pédagogique, par exemple :
  - “Marge brute = Produit – Charges opérationnelles directes”
  - “EBE = Produit d’exploitation – Charges opérationnelles – Charges de structure (hors amortissements)”.
- Tu réorganises les infos numériques dans des tableaux logiques avant de conclure (même approximatifs).
- S’il manque des données essentielles, tu poses 2–3 questions ciblées avant de proposer un avis.

📊 Comptabilité, facturation, tableaux de suivi
- Tu aides à structurer :
  - des plans de comptes simples par atelier ou par culture,
  - des tableaux de suivi de marges, d’EBE, de trésorerie, d’annuités, de stocks.
- Tu peux proposer des modèles de tableaux (colonnes claires) pour :
  - factures et devis (date, n° de facture, client, description, quantité, unité, prix unitaire HT, TVA %, total HT, total TTC, mode de règlement, date d’échéance),
  - suivi de trésorerie (date, libellé, catégorie, montant, entrée/sortie, moyen de paiement, atelier),
  - suivi de marges par culture ou par atelier,
  - suivi d’élevage (effectifs, GMQ, production laitière, mortalité, renouvellement, etc.).
- Tu expliques comment organiser ces tableaux pour qu’ils soient facilement réutilisables dans la plupart des logiciels comptables ou agricoles.
- Tu rappelles régulièrement que tu ne remplaces pas un expert-comptable, un centre de gestion ou un conseiller officiel.

🌾 Technique agricole avancée
Tu peux aborder, avec un niveau “technicien confirmé”, par exemple :
- fertilisation (bilans N-P-K, restitution effluents, ordres de grandeur de doses),
- protection des cultures (IFT, prévention, rotation, gestion des résistances),
- rotation & assolement (successions cohérentes, insertion de prairies et de couverts),
- prairies & fourrages (conduite, fauche, chargement, stocks MS, rations fourrages + concentrés),
- alimentation animale (ingestion, équilibre énergie/protéine, risques principaux),
- bâtiments, bien-être, organisation du travail, sécurité des chantiers.
Tu restes prudent et invites à valider les points sensibles avec les techniciens/vétérinaires locaux.

📲 Aide à la vie de l’agriculteur & papiers
- Tu aides l’utilisateur à gagner du temps sur :
  - tri et compréhension de documents (tableaux de marges, factures, relevés, bilans),
  - préparation de documents (factures, devis, tableaux de bord, plans de trésorerie),
  - organisation des papiers (classement simple, check-lists, routines).
- Tu peux suggérer des idées générales pour placer son argent de manière prudente (diversification, sécurité),
  mais tu ne donnes pas de conseil financier personnalisé ou spéculatif. Tu renvoies vers banquier / conseiller financier.

🔎 Contacts, annonces, affaires, enchères
- Tu ne peux pas récupérer directement des numéros de téléphone ou des annonces en temps réel,
  mais tu peux proposer :
  - des stratégies de recherche (sites possibles, mots-clés, types de plateformes),
  - des modèles de textes pour rédiger une annonce (vente de matériel, recherche de foncier, travail à façon),
  - des conseils pour bien préparer une enchère (prix plafond, contrôle de l’état du matériel, etc.).

🌦️ Météo & décisions
- Tu sais que la météo est centrale pour les semis, récoltes, traitements, pâturage, irrigation.
- Tu aides l’utilisateur à réfléchir à ses décisions en fonction des prévisions (fenêtres météo, risques, marge de sécurité),
  en rappelant que les prévisions restent incertaines.

🎥 Ressources, vidéos, documentaires
- Quand c’est pertinent, tu peux suggérer :
  - des types de vidéos ou documentaires à chercher (mots-clés, thématiques),
  - des idées de formats : témoignages d’agriculteurs, chaînes techniques, vulgarisation, MOOC, webinaires.
- Tu donnes surtout des pistes (thèmes, idées de recherches) et tu encourages à confronter ces contenus à la réalité de la ferme.

🧾 Modèles de factures, tableaux, schémas
- Quand on te le demande (“générer une facture”, “proposer un tableau de suivi”, “schéma d’organisation”…), tu :
  - proposes des modèles de tableaux structurés (colonnes précisées),
  - peux donner un exemple de quelques lignes,
  - expliques concrètement comment s’en servir.
- Pour les schémas (rotation, organisation du travail, flux des bâtiments, plan de pâturage),
  tu décris clairement ce que le schéma pourrait représenter (même sans dessin).

⚡ Vitesse et style de réponse
- Tu vas à l’essentiel : des réponses claires, organisées, sans blabla.
- Par défaut, tu réponds en quelques paragraphes bien structurés.
- Si l’utilisateur demande plus de détails, tu peux développer davantage.
- Tu restes logique et cohérent, tu évites les contradictions.

🧑‍🏫 Style de réponse
- Français courant, ton humain, positif, bienveillant.
- Phrases courtes, claires, concrètes.
- Tu expliques comme à un collègue agriculteur.
- Tu structures tes réponses avec des emojis (🌾🐄📊💶💡⚠️✅…) et des listes.
- Tu organises tes réponses en général ainsi :
  1) Reformulation rapide de la demande,
  2) Analyse / réflexion structurée,
  3) Éléments chiffrés / calculs / exemples, si utiles,
  4) Pistes d’actions concrètes (étapes, check-lists, scénarios).

🛑 Règle fondamentale : aucun contenu offensant
- Tu ne dois jamais produire de contenus offensants, humiliants, discriminants, blessants ou irrespectueux.
- Aucun jugement moral, aucune moquerie, aucun propos visant à rabaisser une personne ou un groupe.
- Tu restes toujours bienveillant, professionnel et respectueux, même si la question est maladroite.
- Tu ne parles jamais négativement d’un groupe (origine, religion, métier, genre, orientation, physique, handicap, etc.).
- Si une formulation pourrait heurter quelqu’un, tu reformules de manière douce et constructive.

⚠️ Limites & honnêteté
- Tu indiques quand un sujet dépend de la réglementation locale, de la PAC, de la MSA, de la DDT, etc.
- Tu ne fabriques pas de lois, de barèmes ou de taux d’aides précis quand tu n’es pas sûr : tu restes sur des ordres de grandeur et tu invites à vérifier auprès des organismes compétents.
- Tu restes un outil d’aide à la réflexion, pas un substitut aux conseillers de terrain, aux vétérinaires, aux experts-comptables ou aux juristes.
"""


# =========================================================
# FONCTIONS FICHIERS
# =========================================================

def lire_csv(file) -> str:
    """Lit un CSV et retourne un petit résumé texte pour le contexte."""
    try:
        df = pd.read_csv(file)
    except Exception:
        file.seek(0)
        df = pd.read_csv(file, sep=";")
    apercu = df.head(10)
    return (
        f"Fichier CSV chargé : {getattr(file, 'name', 'inconnu')}\n"
        f"Colonnes : {list(df.columns)}\n"
        f"10 premières lignes :\n{apercu.to_markdown(index=False)}"
    )


def lire_pdf(file) -> str:
    """Lit rapidement un PDF et renvoie le texte des premières pages."""
    texte_total = []
    with pdfplumber.open(file) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= 3:
                break
            texte_page = page.extract_text() or ""
            texte_total.append(f"--- Page {i+1} ---\n{texte_page}")
    return (
        f"Fichier PDF chargé : {getattr(file, 'name', 'inconnu')}\n"
        "Extraits des premières pages :\n" + "\n\n".join(texte_total)
    )


# =========================================================
# FONCTIONS FACTURE / TABLEAUX / SCHÉMAS
# =========================================================

def generer_modele_facture_df():
    df = pd.DataFrame({
        "Date": [""],
        "N° facture": [""],
        "Client": [""],
        "Adresse client": [""],
        "SIRET client": [""],
        "Description": [""],
        "Quantité": [0],
        "Unité": [""],  # ex : t, kg, h, u
        "Prix unitaire HT": [0.0],
        "TVA (%)": [20],
        "Total HT": [0.0],
        "Total TTC": [0.0],
        "Mode de règlement": [""],
        "Date d’échéance": [""],
    })
    return df


def generer_modeles_tableaux_gestion():
    df_marges = pd.DataFrame(columns=[
        "Année", "Atelier / Culture", "Surface_ha / Nb têtes",
        "Produit total €", "Charges opérationnelles €",
        "Charges de structure €", "Marge brute €", "EBE €",
        "Marge brute /ha ou /tête", "EBE /ha ou /tête"
    ])

    df_tresorerie = pd.DataFrame(columns=[
        "Date", "Type", "Catégorie", "Libellé",
        "Montant €", "Sens",  # Sens = Entrée / Sortie
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
        "Tresorerie": df_tresorerie,
        "Elevage": df_elevage
    }


def texte_idees_schemas():
    return """
📈 **Idées de schémas pour organiser la ferme**

1️⃣ Schéma de rotation des cultures (exemple)
- Année 1 : Maïs ensilage 🌽  
- Année 2 : Blé tendre 🌾  
- Année 3 : Orge d’hiver + couvert végétal  
- Année 4 : Prairie temporaire 3 ans 🌱  

2️⃣ Schéma d’organisation du travail
- Bloc “Tâches quotidiennes” : traite, alimentation, paillage…
- Bloc “Tâches hebdo” : clôtures, entretien matériel, papiers…
- Bloc “Tâches saisonnières” : semis, récoltes, ensilage, vêlages, agnelages…

3️⃣ Schéma de flux en bâtiment
- Entrée animaux → zone d’attente → logettes / cases → aire d’exercice → sortie / quai de chargement.

Tu peux transformer ces idées en schémas sur papier, ou dans un logiciel (PowerPoint, Canva, Miro, etc.).
"""


# =========================================================
# FONCTIONS MÉTÉO (Open-Meteo)
# =========================================================

def get_meteo(location: str):
    """Retourne dict avec météo actuelle + prévisions via Open-Meteo."""
    if not location:
        return None, "Aucune localisation fournie."

    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    params_geo = {
        "name": location,
        "count": 1,
        "language": "fr",
        "format": "json"
    }
    r_geo = requests.get(geo_url, params=params_geo, timeout=10)
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
    r_met = requests.get(meteo_url, params=params_met, timeout=10)
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
        "latitude": lat,
        "longitude": lon,
        "current": current,
        "daily_df": df_daily
    }
    return info, None


# =========================================================
# ÉTAT DE SESSION
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "assistant",
            "content": (
                "Salut 👋\n\n"
                "Je suis ton conseiller agricole IA. Tu peux me parler de ta ferme, de ton projet "
                "ou m’envoyer des fichiers (PDF, CSV) et je t’aide à les exploiter : marges, papiers, "
                "trésorerie, organisation, élevage…"
            ),
        },
    ]

if "fichiers_contextes" not in st.session_state:
    st.session_state.fichiers_contextes = []

if "suggestion" not in st.session_state:
    st.session_state.suggestion = ""


# =========================================================
# UI PRINCIPALE – ONGLETS
# =========================================================

tab_chat, tab_meteo = st.tabs(["🗣️ Chat IA agricole", "🌦️ Météo agricole"])


# ---------------------------------------------------------
# ONGLET 1 : CHAT IA AGRICOLE
# ---------------------------------------------------------
with tab_chat:
    left, right = st.columns([2.5, 1.5])

    with left:
        st.title("🌾 Conseiller agricole IA")
        st.caption(f"Version {APP_VERSION} – Une seule interface pour piloter ta ferme comme sur ChatGPT.")

        # Options de style de réponse
        style_reponse = st.radio(
            "Style de réponse",
            options=["Rapide et synthétique", "Plus détaillée"],
            horizontal=True,
        )

        # Boutons de suggestion comme ChatGPT
        with st.container():
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                if st.button("📊 Analyser mes marges"):
                    st.session_state.suggestion = "Peux-tu m'aider à analyser les marges de mon exploitation ?"
            with col_s2:
                if st.button("🧾 Aide pour mes papiers"):
                    st.session_state.suggestion = "J'ai des papiers et des documents à trier, peux-tu m'aider à y voir clair ?"
            with col_s3:
                if st.button("🐄 Atelier élevage"):
                    st.session_state.suggestion = "Peux-tu analyser et optimiser mon atelier d'élevage ?"

            col_s4, col_s5, col_s6 = st.columns(3)
            with col_s4:
                if st.button("💶 Investissements & prudence"):
                    st.session_state.suggestion = "Peux-tu m'aider à réfléchir à mes investissements et à placer mon argent de façon prudente ?"
            with col_s5:
                if st.button("🚜 Organisation du travail"):
                    st.session_state.suggestion = "Aide-moi à mieux organiser mon travail sur l'année."
            with col_s6:
                if st.button("📣 Rédiger une annonce"):
                    st.session_state.suggestion = "Aide-moi à rédiger une annonce pour vendre ou acheter du matériel agricole."

        st.markdown("---")

        # Bouton pour vider la conversation
        if st.button("🧹 Vider la conversation"):
            st.session_state.messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "assistant",
                    "content": (
                        "Conversation réinitialisée ✅\n\n"
                        "Dis-moi où tu veux que l'on commence (marges, papiers, élevage, organisation...)."
                    ),
                },
            ]

        st.markdown("---")

        # Affichage historique
        for msg in st.session_state.messages:
            if msg["role"] == "system":
                continue
            with st.chat_message("assistant" if msg["role"] == "assistant" else "user"):
                st.markdown(msg["content"])

        # Entrée utilisateur
        default_text = ""
        if st.session_state.suggestion:
            default_text = st.session_state.suggestion
            st.session_state.suggestion = ""

        user_input = st.chat_input("Pose une question sur ta ferme, tes papiers, tes chiffres…")

        if (not user_input) and default_text:
            user_input = default_text

        if user_input:
            user_input = user_input.strip()
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # Préparation des messages pour l'API
            messages_for_api = st.session_state.messages.copy()

            # Ajout d'une consigne de style court/détaillé
            if style_reponse == "Rapide et synthétique":
                messages_for_api.append({
                    "role": "system",
                    "content": "Pour cette réponse, sois rapide et synthétique : quelques paragraphes maximum, très concrets."
                })
            else:
                messages_for_api.append({
                    "role": "system",
                    "content": "Pour cette réponse, tu peux être un peu plus détaillé, tout en restant clair et structuré."
                })

            # Contexte fichiers
            if st.session_state.fichiers_contextes:
                contexte_text = (
                    "Voici des informations extraites de fichiers de l'exploitation "
                    "(dossiers comptables, tableaux de marges, exports Excel, etc.). "
                    "Utilise-les pour adapter tes réponses :\n\n"
                    + "\n\n---\n\n".join(st.session_state.fichiers_contextes)
                )
                messages_for_api.append({"role": "system", "content": contexte_text})

            # Appel modèle GPT-4.1 (temp basse pour limiter l’aléatoire)
            with st.chat_message("assistant"):
                placeholder = st.empty()
                placeholder.markdown("Je réfléchis à ta situation… ⏳")

                try:
                    response = client.responses.create(
                        model="gpt-4.1",
                        input=messages_for_api,
                        temperature=0.2,
                    )
                    answer = response.output[0].content[0].text.value
                except Exception as e:
                    answer = (
                        "❌ Je n’ai pas réussi à contacter le modèle pour l’instant.\n\n"
                        "Vérifie ta clé `OPENAI_API_KEY` et ta connexion internet.\n\n"
                        f"Détail technique : {e}"
                    )

                placeholder.markdown(answer)

            st.session_state.messages.append({"role": "assistant", "content": answer})

            st.markdown(
                "> ℹ️ Rappel : ce conseiller IA ne remplace pas un conseiller de terrain, "
                "un vétérinaire, un expert-comptable ou un juriste, il t’aide à réfléchir."
            )

    # -----------------------------------------------------
    # COLONNE DROITE : FICHIERS + BOUTONS SMART
    # -----------------------------------------------------
    with right:
        st.subheader("📂 Fichiers à analyser")
        uploaded_files = st.file_uploader(
            "Tu peux déposer plusieurs fichiers à la fois (PDF, CSV).",
            type=["csv", "pdf"],
            accept_multiple_files=True,
        )

        if uploaded_files and st.button("✅ Analyser les fichiers", use_container_width=True):
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

            st.session_state.fichiers_contextes.extend(resumes)
            st.success("Fichiers analysés. L’IA tiendra compte de ces infos.")
            for r in resumes:
                st.code(r[:2000])

        st.markdown("---")
        st.subheader("🧾 Outils rapides")

        # Générer facture
        if st.button("🧾 Générer un modèle de facture", use_container_width=True):
            df_fact = generer_modele_facture_df()
            st.markdown("Voilà un modèle de facture que tu peux remplir :")
            st.dataframe(df_fact, use_container_width=True)
            csv_fact = df_fact.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Télécharger en CSV",
                data=csv_fact,
                file_name="modele_facture_agricole.csv",
                mime="text/csv",
                use_container_width=True
            )

        # Modèles de tableaux de gestion
        if st.button("📊 Modèles de tableaux de gestion", use_container_width=True):
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
                    use_container_width=True
                )

        # Idées de schémas
        if st.button("📈 Idées de schémas (rotation, organisation…)", use_container_width=True):
            st.markdown(texte_idees_schemas())


# ---------------------------------------------------------
# ONGLET 2 : MÉTÉO AGRICOLE
# ---------------------------------------------------------
with tab_meteo:
    st.header("🌦️ Météo agricole")
    st.caption("Petit onglet météo pour t’aider à caler semis, récoltes, pâturage, traitements…")

    col_loc, col_btn = st.columns([3, 1])
    with col_loc:
        localisation = st.text_input(
            "Ville / commune / lieu",
            placeholder="Exemple : Rouen, Toulouse, Rennes…"
        )
    with col_btn:
        lancer = st.button("🔍 Voir la météo")

    if lancer and localisation:
        info, err = get_meteo(localisation)
        if err:
            st.error(err)
        elif info is None:
            st.error("Impossible de récupérer la météo.")
        else:
            st.success(f"Météo récupérée pour **{info['nom']} ({info['pays']})**")

            current = info.get("current", {})
            if current:
                st.subheader("🕒 Météo actuelle (approx.)")
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Température (°C)", current.get("temperature", "NA"))
                with col_b:
                    st.metric("Vent (km/h)", current.get("windspeed", "NA"))
                with col_c:
                    st.metric("Code météo", current.get("weathercode", "NA"))

            df_daily = info.get("daily_df")
            if df_daily is not None:
                st.subheader("📆 Prévisions sur quelques jours")
                st.dataframe(df_daily.head(5), use_container_width=True)
                st.markdown(
                    "> ℹ️ Ces données viennent d’Open-Meteo (modèle global). "
                    "Pour des décisions sensibles, croise toujours avec une appli météo locale ou pro."
                )
    elif lancer and not localisation:
        st.info("👉 Saisis d’abord un nom de commune pour afficher la météo.")
