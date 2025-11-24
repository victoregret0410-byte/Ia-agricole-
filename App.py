import streamlit as st
import pdfplumber
import pandas as pd
import re
import matplotlib.pyplot as plt
from datetime import datetime

# =========================================================
# CONFIG GLOBALE
# =========================================================

APP_NAME = "IA agricole – marges & conseils"
APP_VERSION = "1.0.0"  # augmente ce numéro quand tu modifies le code

st.set_page_config(page_title=APP_NAME, layout="wide")


# =========================================================
# FONCTIONS UTILITAIRES
# =========================================================

def _to_float_fr(s, default=None):
    """Convertit '41,70' ou '41 70' en float 41.70."""
    if s is None:
        return default
    s = s.replace("\xa0", " ")
    s = s.replace(" ", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


# =========================================================
# EXTRACTION ASSOLEMENT DEPUIS PDF (TYPE CERFRANCE)
# =========================================================

def extraire_assolement_cerfrance_file(pdf_file, debug=False):
    """
    pdf_file : fichier uploadé (file-like)
    Retour : DataFrame avec Culture, Surface_ha
    """

    cultures_patterns = [
        r"Bl[ée] tendre",
        r"Bl[ée] dur",
        r"Orge d'hiver",
        r"Orge de printemps",
        r"Ma[iî]s fourrage",
        r"Ma[iî]s grain",
        r"Ma[iî]s",
        r"Colza",
        r"Lin textile",
        r"Tournesol",
        r"Betteraves? sucri[eè]res?",
        r"Prairies? permanentes?",
        r"Prairies? temporaires?",
        r"Luzerne",
        r"Méteil",
        r"Jach[èe]re",
    ]
    cultures_regex = re.compile("(" + "|".join(cultures_patterns) + ")", flags=re.IGNORECASE)

    lignes_trouvees = []

    with pdfplumber.open(pdf_file) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            for raw_line in text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue

                m_cult = cultures_regex.search(line)
                if not m_cult:
                    continue

                culture_brute = m_cult.group(0).strip()

                # Surface "41,70 ha" ou "41,70"
                m_surface = re.search(r"([\d\s\u00a0,]+)\s*ha", line, flags=re.IGNORECASE)
                if not m_surface:
                    m_surface = re.search(r"([\d\s\u00a0,]+)$", line)
                if not m_surface:
                    continue

                surface_ha = _to_float_fr(m_surface.group(1))
                if surface_ha is None:
                    continue

                lignes_trouvees.append({
                    "Culture_brute": culture_brute,
                    "Surface_ha": surface_ha,
                    "Page": page_num,
                    "Ligne_brute": raw_line
                })

    if not lignes_trouvees:
        return pd.DataFrame(columns=["Culture", "Surface_ha"])

    df_assolement = pd.DataFrame(lignes_trouvees)

    def normaliser_culture(nom):
        original_lower = nom.lower()
        n = original_lower
        n = n.replace("é", "e").replace("è", "e").replace("ê", "e")
        n = n.replace("ï", "i").replace("î", "i")
        n = n.replace("  ", " ").strip()

        if "ble tendre" in n:
            return "Blé tendre"
        if "ble dur" in n:
            return "Blé dur"
        if "orge d'hiver" in n or "orge dhiver" in n:
            return "Orge d'hiver"
        if "orge de printemps" in n:
            return "Orge de printemps"
        if "lin textile" in n:
            return "Lin textile"
        if "betterave" in n and "sucr" in n:
            return "Betteraves sucrières"
        if "mais fourrage" in n or "maïs fourrage" in original_lower:
            return "Maïs fourrage"
        if "mais grain" in n or "maïs grain" in original_lower:
            return "Maïs grain"
        if "maïs" in original_lower or "mais" in n:
            return "Maïs"
        if "colza" in n:
            return "Colza"
        if "tournesol" in n:
            return "Tournesol"
        if "prairie permanente" in n:
            return "Prairies permanentes"
        if "prairie" in n:
            return "Prairies"
        if "luzerne" in n:
            return "Luzerne"
        if "meteil" in n or "méteil" in n:
            return "Méteil"
        if "jachere" in n or "jachère" in original_lower:
            return "Jachère"
        return nom.strip()

    df_assolement["Culture"] = df_assolement["Culture_brute"].apply(normaliser_culture)

    df_regroupe = (
        df_assolement
        .groupby("Culture", as_index=False)
        .agg({"Surface_ha": "sum"})
    )

    if debug:
        return df_regroupe, df_assolement
    return df_regroupe


# =========================================================
# REFERENCES DE CHARGES (CSV)
# =========================================================

def charger_references_charges_file(csv_file, sep=";"):
    df_ref = pd.read_csv(csv_file, sep=sep)
    df_ref.columns = [c.strip() for c in df_ref.columns]
    return df_ref


def fusionner_cultures_et_references(df_cultures, df_refs):
    df = df_cultures.copy()
    if "Aides_€/ha" not in df.columns:
        df["Aides_€/ha"] = 0.0
    df_merged = df.merge(df_refs, on="Culture", how="left", indicator=True)
    return df_merged


# =========================================================
# CALCUL DES MARGES PAR CULTURE
# =========================================================

def calculer_marges_par_culture(df_cultures):
    df = df_cultures.copy()

    colonnes_obligatoires = [
        "Culture",
        "Surface_ha",
        "Unité_rendement",
        "Rendement_par_ha",
        "Prix_vente_€/unité",
        "Semences_€/ha",
        "Engrais_€/ha",
        "Phyto_€/ha",
        "Autres_charges_op_€/ha"
    ]
    for col in colonnes_obligatoires:
        if col not in df.columns:
            raise ValueError(f"Colonne manquante : {col}")

    if "Aides_€/ha" not in df.columns:
        df["Aides_€/ha"] = 0.0
    if "Charges_structure_€/ha" not in df.columns:
        df["Charges_structure_€/ha"] = 0.0

    df["Produit_€/ha"] = df["Rendement_par_ha"] * df["Prix_vente_€/unité"] + df["Aides_€/ha"]

    df["Charges_op_€/ha"] = (
        df["Semences_€/ha"] +
        df["Engrais_€/ha"] +
        df["Phyto_€/ha"] +
        df["Autres_charges_op_€/ha"]
    )

    df["Marge_brute_€/ha"] = df["Produit_€/ha"] - df["Charges_op_€/ha"]
    df["Marge_apres_structure_€/ha"] = df["Marge_brute_€/ha"] - df["Charges_structure_€/ha"]

    df["Produit_total_€"] = df["Produit_€/ha"] * df["Surface_ha"]
    df["Charges_op_totales_€"] = df["Charges_op_€/ha"] * df["Surface_ha"]
    df["Charges_structure_totales_€"] = df["Charges_structure_€/ha"] * df["Surface_ha"]
    df["Marge_brute_totale_€"] = df["Marge_brute_€/ha"] * df["Surface_ha"]
    df["Marge_apres_structure_totale_€"] = df["Marge_apres_structure_€/ha"] * df["Surface_ha"]

    total_surface = df["Surface_ha"].sum()
    total_produit = df["Produit_total_€"].sum()
    total_charges_op = df["Charges_op_totales_€"].sum()
    total_charges_struct = df["Charges_structure_totales_€"].sum()
    total_marge_brute = df["Marge_brute_totale_€"].sum()
    total_marge_apres_struct = df["Marge_apres_structure_totale_€"].sum()

    lignes_synthese = [
        {"Indicateur": "Surface totale", "Valeur": total_surface, "Unité": "ha"},
        {"Indicateur": "Produit total", "Valeur": total_produit, "Unité": "€"},
        {"Indicateur": "Charges op. totales", "Valeur": total_charges_op, "Unité": "€"},
        {"Indicateur": "Charges structure totales", "Valeur": total_charges_struct, "Unité": "€"},
        {"Indicateur": "Marge brute totale", "Valeur": total_marge_brute, "Unité": "€"},
        {"Indicateur": "Marge après structure totale", "Valeur": total_marge_apres_struct, "Unité": "€"},
    ]
    if total_surface > 0:
        lignes_synthese.extend([
            {"Indicateur": "Produit moyen / ha", "Valeur": total_produit / total_surface, "Unité": "€/ha"},
            {"Indicateur": "Charges op. moyennes / ha", "Valeur": total_charges_op / total_surface, "Unité": "€/ha"},
            {"Indicateur": "Charges structure moyennes / ha", "Valeur": total_charges_struct / total_surface, "Unité": "€/ha"},
            {"Indicateur": "Marge brute moyenne / ha", "Valeur": total_marge_brute / total_surface, "Unité": "€/ha"},
            {"Indicateur": "Marge après structure moyenne / ha", "Valeur": total_marge_apres_struct / total_surface, "Unité": "€/ha"},
        ])

    df_synthese = pd.DataFrame(lignes_synthese)

    return df, df_synthese


# =========================================================
# ANALYSE GLOBALE EXPLOITATION (SIMPLE)
# =========================================================

def analyser_exploitation_simple(
    produit_total,
    charges_op,
    charges_structure,
    annuites,
    sau_ha,
    uth
):
    marge_brute = produit_total - charges_op
    ebe = produit_total - charges_op - charges_structure
    revenu_avant_impot = ebe - annuites

    df_montants = pd.DataFrame({
        "Poste": [
            "Produit total",
            "Charges opérationnelles",
            "Charges de structure",
            "Annuités",
            "Marge brute",
            "EBE",
            "Revenu avant impôt"
        ],
        "Montant (€ / an)": [
            produit_total,
            charges_op,
            charges_structure,
            annuites,
            marge_brute,
            ebe,
            revenu_avant_impot
        ]
    })

    lignes_indic = []
    if sau_ha > 0:
        lignes_indic.append({
            "Indicateur": "EBE / ha",
            "Valeur": ebe / sau_ha,
            "Unité": "€/ha"
        })
        lignes_indic.append({
            "Indicateur": "Marge brute / ha",
            "Valeur": marge_brute / sau_ha,
            "Unité": "€/ha"
        })
    if uth > 0:
        lignes_indic.append({
            "Indicateur": "Revenu avant impôt / UTH",
            "Valeur": revenu_avant_impot / uth,
            "Unité": "€/UTH"
        })
    df_indic = pd.DataFrame(lignes_indic) if lignes_indic else pd.DataFrame(columns=["Indicateur", "Valeur", "Unité"])

    commentaires = []
    if ebe < 0:
        commentaires.append("EBE négatif : la ferme ne couvre pas ses charges de structure. Situation fragile.")
    elif ebe < produit_total * 0.15:
        commentaires.append("EBE positif mais faible : charges lourdes. Chercher des économies et des gains techniques.")
    else:
        commentaires.append("EBE correct par rapport au produit : structure globalement équilibrée.")

    if revenu_avant_impot < 0:
        commentaires.append("Revenu avant impôt négatif : annuités trop lourdes ou résultat insuffisant.")
    elif revenu_avant_impot < 20000:
        commentaires.append("Revenu avant impôt modeste : vérifier la rémunération par personne et le temps de travail.")
    else:
        commentaires.append("Revenu avant impôt significatif : vérifier la pérennité de ce niveau.")

    df_com = pd.DataFrame({"Commentaire": commentaires})

    return df_montants, df_indic, df_com


# =========================================================
# MINI BASE DE CONNAISSANCES AGRICOLES (EXEMPLES)
# =========================================================

FICHES_CULTURES = {
    "Blé tendre": {
        "Objectif": "Produire un rendement régulier avec une teneur en protéines suffisante selon le débouché.",
        "Sol": "Sol profond, bien drainé, pH 6–7. Éviter les sols asphyxiants.",
        "Rotation": "Éviter blé sur blé trop fréquent, bien après légumineuses ou colza.",
        "Points_cles": [
            "Adapter la densité de semis au potentiel, à la date et au type de sol.",
            "Raisonner la fertilisation azotée avec un bilan (ou outils type N-Tester).",
            "Surveiller les maladies foliaires aux stades clés (2 nœuds, dernière feuille).",
            "Limiter le travail du sol agressif sur sols fragiles."
        ]
    },
    "Colza": {
        "Objectif": "Culture à forte valeur, mais sensible à l’implantation.",
        "Sol": "Sol profond, bien pourvu en eau, éviter les zones très séchantes.",
        "Rotation": "Pas de colza trop fréquent (risque maladies). Bons précédents : céréales.",
        "Points_cles": [
            "Implantation très soignée : lit de semences fin, profondeur régulière.",
            "Gérer les ravageurs d’automne de façon raisonnée, sans surtraiter.",
            "Suivre l’azote et le soufre (fortes exigences).",
            "Attention au désherbage (adventices dicotylées)."
        ]
    },
    "Maïs fourrage": {
        "Objectif": "Produire un fourrage énergétique et régulier pour l’élevage.",
        "Sol": "Sol bien ressuyé, réchauffant, éviter les excès d’eau.",
        "Rotation": "Bien après prairie, céréales, méteil.",
        "Points_cles": [
            "Choisir des variétés adaptées à la précocité de la zone.",
            "Soigner la fertilisation de fond (P-K) et l’azote selon le potentiel.",
            "Réaliser un désherbage précis (précocité des adventices).",
            "Soigner la récolte : stade grain laiteux-pâteux, bon tassement du silo."
        ]
    }
}

def get_fiche_culture(culture):
    fiche = FICHES_CULTURES.get(culture)
    if fiche is None:
        return f"Aucune fiche détaillée enregistrée pour {culture} pour l’instant.", None
    texte = f"🎯 Objectif : {fiche['Objectif']}\n\n"
    texte += f"🌱 Sol conseillé : {fiche['Sol']}\n\n"
    texte += f"🔁 Place dans la rotation : {fiche['Rotation']}\n\n"
    texte += "✅ Points clés :\n"
    for p in fiche["Points_cles"]:
        texte += f"  • {p}\n"
    return texte, fiche


# =========================================================
# MINI OUTIL STOCK FOURRAGER (APPROXIMATIF)
# =========================================================

def calcul_stock_fourrager(ha_prairie, rendement_tMS_ha, besoins_kgMS_jour, nb_jours):
    """
    ha_prairie : ha de prairies exploitées
    rendement_tMS_ha : t MS / ha / an
    besoins_kgMS_jour : kg MS / jour pour le troupeau
    nb_jours : durée de couverture visée
    """
    production_totale_tMS = ha_prairie * rendement_tMS_ha
    production_totale_kgMS = production_totale_tMS * 1000
    besoins_totaux_kgMS = besoins_kgMS_jour * nb_jours
    couverture_jours = production_totale_kgMS / besoins_kgMS_jour if besoins_kgMS_jour > 0 else 0
    return production_totale_tMS, besoins_totaux_kgMS, couverture_jours


# =========================================================
# ETAT DE SESSION
# =========================================================

if "df_assolement" not in st.session_state:
    st.session_state.df_assolement = None
if "df_cultures_edit" not in st.session_state:
    st.session_state.df_cultures_edit = None
if "df_refs" not in st.session_state:
    st.session_state.df_refs = None
if "df_resultats" not in st.session_state:
    st.session_state.df_resultats = None
if "df_synthese" not in st.session_state:
    st.session_state.df_synthese = None


# =========================================================
# UI PRINCIPALE (ONGLETS)
# =========================================================

st.title("🌾 IA agricole – marges & conseils")
st.caption(f"Version {APP_VERSION} – Outil pédagogique pour aider les agriculteurs à piloter leur ferme.")

tab_marges, tab_exploit, tab_technique, tab_elevage, tab_aide = st.tabs([
    "📊 Marges par culture",
    "🏠 Synthèse exploitation",
    "🧠 Conseils cultures",
    "🐄 Elevage & fourrages",
    "🧰 Aide & évolution"
])


# ---------------------------------------------------------
# ONGLET 1 : MARGES PAR CULTURE
# ---------------------------------------------------------
with tab_marges:
    st.header("1️⃣ Marges par culture à partir d’un dossier + références")

    col_left, col_right = st.columns(2)

    with col_left:
        pdf_file = st.file_uploader("🧾 Dossier PDF (type Cerfrance, cabinet...)", type=["pdf"])
        if pdf_file is not None:
            if st.button("📌 Extraire l’assolement depuis le PDF"):
                df_assolement = extraire_assolement_cerfrance_file(pdf_file, debug=False)
                if df_assolement.empty:
                    st.error("Impossible de détecter l’assolement automatiquement. Tu pourras créer le tableau à la main.")
                else:
                    st.success("Assolement détecté.")
                    st.session_state.df_assolement = df_assolement

        st.markdown("Ou tu peux **entrer toi-même** les cultures plus bas si l’extraction ne marche pas.")

    with col_right:
        csv_ref_file = st.file_uploader("📂 Références de charges par culture (CSV)", type=["csv"])
        if csv_ref_file is not None:
            if st.button("📥 Charger les références de charges"):
                df_refs = charger_references_charges_file(csv_ref_file)
                st.session_state.df_refs = df_refs
                st.success("Références chargées.")
                st.subheader("Aperçu des références")
                st.dataframe(df_refs, use_container_width=True)

    st.subheader("Assolement de base (Culture + Surface_ha)")
    if st.session_state.df_assolement is None:
        st.info("➡️ Aucun assolement extrait pour l’instant. Tu peux créer ton propre tableau ci-dessous.")
        df_base_assolement = pd.DataFrame(columns=["Culture", "Surface_ha"])
    else:
        df_base_assolement = st.session_state.df_assolement.copy()
        st.dataframe(df_base_assolement, use_container_width=True)

    st.subheader("2️⃣ Paramétrer cultures, surfaces, rendements, prix, aides")

    if st.session_state.df_cultures_edit is None:
        if df_base_assolement.empty:
            df_base = pd.DataFrame({
                "Culture": [],
                "Surface_ha": [],
                "Unité_rendement": [],
                "Rendement_par_ha": [],
                "Prix_vente_€/unité": [],
                "Aides_€/ha": []
            })
        else:
            df_base = df_base_assolement.copy()
            df_base["Unité_rendement"] = "q/ha"
            df_base["Rendement_par_ha"] = 70.0
            df_base["Prix_vente_€/unité"] = 18.0
            df_base["Aides_€/ha"] = 150.0
    else:
        df_prev = st.session_state.df_cultures_edit
        df_base = df_base_assolement.merge(
            df_prev.drop(columns=["Surface_ha"], errors="ignore"),
            on="Culture",
            how="left",
            suffixes=("", "_old")
        )
        for col in ["Unité_rendement", "Rendement_par_ha", "Prix_vente_€/unité", "Aides_€/ha"]:
            col_old = col + "_old"
            if col_old in df_base.columns:
                df_base[col] = df_base[col_old].fillna(df_base.get(col, None))
                df_base = df_base.drop(columns=[col_old])

    st.write("✏️ Tu peux ajouter des lignes, changer les surfaces, les rendements, les prix, les aides…")
    df_edit = st.data_editor(
        df_base,
        num_rows="dynamic",
        use_container_width=True
    )
    st.session_state.df_cultures_edit = df_edit

    st.subheader("3️⃣ Calculer les marges par culture")

    if st.session_state.df_cultures_edit is None or st.session_state.df_cultures_edit.empty:
        st.info("➡️ Remplis d’abord le tableau des cultures ci-dessus.")
    elif st.session_state.df_refs is None:
        st.info("➡️ Charge d’abord le CSV de références de charges (semences, engrais, phyto, etc.).")
    else:
        if st.button("✅ Calculer les marges"):
            df_cultures = st.session_state.df_cultures_edit.copy()
            df_refs = st.session_state.df_refs.copy()

            df_merged = fusionner_cultures_et_references(df_cultures, df_refs)
            sans_ref = df_merged[df_merged["_merge"] != "both"] if "_merge" in df_merged.columns else pd.DataFrame()
            if not sans_ref.empty:
                st.warning("Certaines cultures n'ont pas de référence de charges (voir colonne _merge).")

            if "_merge" in df_merged.columns:
                df_merged = df_merged.drop(columns=["_merge"])

            try:
                df_resultats, df_synthese = calculer_marges_par_culture(df_merged)
                st.session_state.df_resultats = df_resultats
                st.session_state.df_synthese = df_synthese
                st.success("Calcul des marges terminé.")
            except Exception as e:
                st.error(f"Erreur lors du calcul des marges : {e}")

    if st.session_state.df_resultats is not None:
        st.subheader("📊 Marges par culture (détail)")
        st.dataframe(st.session_state.df_resultats, use_container_width=True)

    if st.session_state.df_synthese is not None:
        st.subheader("🧮 Synthèse système grandes cultures")
        st.dataframe(st.session_state.df_synthese, use_container_width=True)

    # Export CSV pour Canva / Excel
    st.subheader("4️⃣ Export des données (pour Canva, Excel, etc.)")
    if st.session_state.df_resultats is not None:
        csv_detail = st.session_state.df_resultats.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Télécharger le tableau détaillé (CSV)",
            data=csv_detail,
            file_name="marges_par_culture_detail.csv",
            mime="text/csv"
        )
    if st.session_state.df_synthese is not None:
        csv_synth = st.session_state.df_synthese.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Télécharger la synthèse (CSV)",
            data=csv_synth,
            file_name="synthese_systeme_grandes_cultures.csv",
            mime="text/csv"
        )

    # Graphiques
    st.subheader("5️⃣ Schémas & graphiques simples")

    if st.session_state.df_resultats is not None:
        df_res = st.session_state.df_resultats

        st.markdown("**Marge brute totale par culture**")
        fig1, ax1 = plt.subplots()
        ax1.bar(df_res["Culture"], df_res["Marge_brute_totale_€"])
        ax1.set_xlabel("Culture")
        ax1.set_ylabel("Marge brute totale (€)")
        ax1.set_title("Marge brute totale par culture")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig1)

        st.markdown("**Produit /ha vs Charges op /ha**")
        fig2, ax2 = plt.subplots()
        largeur = 0.35
        x = range(len(df_res["Culture"]))
        ax2.bar([i - largeur/2 for i in x], df_res["Produit_€/ha"], width=largeur, label="Produit €/ha")
        ax2.bar([i + largeur/2 for i in x], df_res["Charges_op_€/ha"], width=largeur, label="Charges op €/ha")
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(df_res["Culture"], rotation=45, ha="right")
        ax2.set_ylabel("€ / ha")
        ax2.set_title("Produit vs charges op par ha")
        ax2.legend()
        st.pyplot(fig2)
    else:
        st.info("➡️ Lance un calcul de marges pour afficher des graphiques.")


# ---------------------------------------------------------
# ONGLET 2 : SYNTHESE EXPLOITATION
# ---------------------------------------------------------
with tab_exploit:
    st.header("🏠 Synthèse simple de l’exploitation")

    st.markdown("Renseigne les grandes masses de ton exploitation pour un diagnostic rapide :")

    col1, col2 = st.columns(2)

    with col1:
        produit_total = st.number_input("Produit total (€ / an)", value=300000.0, step=1000.0)
        charges_op = st.number_input("Charges opérationnelles (€ / an)", value=150000.0, step=1000.0)
        charges_structure = st.number_input("Charges de structure (€ / an)", value=120000.0, step=1000.0)

    with col2:
        annuites = st.number_input("Annuités (€ / an)", value=40000.0, step=1000.0)
        sau_ha = st.number_input("SAU (ha)", value=100.0, step=1.0)
        uth = st.number_input("Main d’œuvre (UTH)", value=1.0, step=0.1)

    if st.button("📌 Analyser l’exploitation"):
        df_montants, df_indic, df_com = analyser_exploitation_simple(
            produit_total=produit_total,
            charges_op=charges_op,
            charges_structure=charges_structure,
            annuites=annuites,
            sau_ha=sau_ha,
            uth=uth
        )

        st.subheader("Montants annuels (€)")
        st.dataframe(df_montants, use_container_width=True)

        st.subheader("Indicateurs par ha / UTH")
        st.dataframe(df_indic, use_container_width=True)

        st.subheader("Commentaires automatiques (à discuter avec un conseiller)")
        st.dataframe(df_com, use_container_width=True)

        st.markdown(
            "> ⚠️ Ces résultats restent indicatifs. Toujours confronter à un conseiller (Cerfrance, chambre, banquier...)."
        )


# ---------------------------------------------------------
# ONGLET 3 : CONSEILS CULTURES
# ---------------------------------------------------------
with tab_technique:
    st.header("🧠 Conseils techniques de base par culture")

    culture_choisie = st.selectbox(
        "Choisis une culture",
        options=["Blé tendre", "Colza", "Maïs fourrage"]
    )

    texte_fiche, fiche = get_fiche_culture(culture_choisie)
    st.text(texte_fiche)

    st.markdown(
        """
        💬 Cette partie n’est pas là pour remplacer un technicien,
        mais pour te rappeler les **bases importantes** à vérifier.
        """
    )


# ---------------------------------------------------------
# ONGLET 4 : ELEVAGE & FOURRAGES
# ---------------------------------------------------------
with tab_elevage:
    st.header("🐄 Elevage & stock fourrager (approximation)")

    st.markdown("Estimation simple de ton stock en prairies par rapport aux besoins du troupeau.")

    colg, cold = st.columns(2)
    with colg:
        ha_prairie = st.number_input("Ha de prairies productives", value=20.0, step=1.0)
        rendement_tMS_ha = st.number_input("Rendement moyen (t MS / ha / an)", value=6.0, step=0.5)

    with cold:
        besoins_kgMS_jour = st.number_input("Besoins totaux du troupeau (kg MS / jour)", value=1500.0, step=50.0)
        nb_jours = st.number_input("Durée visée (jours)", value=180.0, step=10.0)

    if st.button("🌱 Calculer la couverture fourragère"):
        prod_tMS, besoins_totaux_kg, couverture_jours = calcul_stock_fourrager(
            ha_prairie=ha_prairie,
            rendement_tMS_ha=rendement_tMS_ha,
            besoins_kgMS_jour=besoins_kgMS_jour,
            nb_jours=nb_jours
        )

        st.write(f"✅ Production totale estimée : **{prod_tMS:.1f} t MS**")
        st.write(f"📌 Besoins sur {nb_jours:.0f} jours : **{besoins_totaux_kg/1000:.1f} t MS**")
        st.write(f"📆 Couverture théorique : **{couverture_jours:.0f} jours**")

        if couverture_jours < nb_jours:
            st.warning("⚠️ Couverture insuffisante : risque de manque de fourrage. Envisager d’augmenter la surface, le rendement, ou d’acheter.")
        else:
            st.success("👍 A priori, le stock prairies couvre la période visée (à confirmer avec un bilan plus complet).")


# ---------------------------------------------------------
# ONGLET 5 : AIDE & EVOLUTION
# ---------------------------------------------------------
with tab_aide:
    st.header("🧰 Aide, limites & évolution de l’outil")

    st.markdown(
        f"""
        ### ℹ️ Ce que fait cette IA agricole

        - Analyse les **marges par culture** à partir :
          - d’un assolement (PDF ou manuel)
          - de références de charges (CSV)
        - Donne une **synthèse économique simple** de l’exploitation (EBE, revenu, €/ha, €/UTH)
        - Fournit des **rappels techniques de base** sur quelques cultures
        - Propose un **petit outil fourrager** pour se situer

        ### ⚠️ Ce que l’outil NE FAIT PAS (volontairement)

        - Il ne se propage pas tout seul, ne s’installe nulle part sans toi.
        - Il ne remplace pas :
          - un conseiller de gestion
          - un technicien cultures / élevage
          - ton banquier / ton comptable

        ### 🔁 Comment tu peux le faire évoluer

        - Ajouter des cultures dans `FICHES_CULTURES` (avec objectifs, sols, points clés)
        - Ajouter des colonnes dans tes fichiers CSV de références
        - Modifier les seuils dans l’analyse économique
        - Créer d’autres onglets (par ex. environnement, irrigation, machinisme…)

        Chaque fois que tu modifies `app.py` sur GitHub :
        - Streamlit Cloud relancera une nouvelle version
        - Ton lien restera le même
        """
    )

    st.markdown(
        """
        💚 Ton objectif “aider les agriculteurs au maximum” est très beau.  
        Cet outil est une **base solide**. Il ne sera jamais “100% complet”,  
        mais tu peux l’améliorer petit à petit, comme une ferme qu’on fait évoluer chaque année.
        """
    )
