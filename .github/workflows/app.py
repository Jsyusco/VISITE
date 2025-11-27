import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
from datetime import timedelta, date

# --- CONFIGURATION DES NOMS DE COLONNES ---

REFERENCE_COL = 'Intitulé'
LATITUDE_COL = 'Lat [Info Site]'
LONGITUDE_COL = 'Long [Info Site]'
col_date_ouv = "Ouverture commerciale estimée"
col_date_trvx = "Début des travaux [Travaux]"

# -----------------------------------------------------------------


# --- 1. FONCTION DE CALCUL DE DISTANCE (Haversine) ---

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


# --- 2. CONFIGURATION DE LA PAGE ---

st.set_page_config(page_title="Site à visiter", layout="wide")
st.title("📍 Localisation des Sites")


# --- 3. CHARGEMENT DES DONNÉES ---

with st.sidebar:
    st.header("1. Données")
    uploaded_file = st.file_uploader("Charger votre fichier Excel", type=["xlsx", "xls"])

if uploaded_file is None:
    st.info("👋 Veuillez charger un fichier Excel (.xlsx)")
    st.stop()

try:
    df = pd.read_excel(uploaded_file)
except Exception as e:
    st.error(f"Erreur lors de la lecture du fichier : {e}")
    st.stop()


# --- 4. NETTOYAGE ET CONVERSION ---

required_columns = [REFERENCE_COL, LATITUDE_COL, LONGITUDE_COL, col_date_ouv, col_date_trvx]
missing_cols = [col for col in required_columns if col not in df.columns]

if missing_cols:
    st.error(f"⚠️ Colonnes manquantes : {', '.join(missing_cols)}")
    st.stop()


# Conversion Lat/Lon
try:
    df[LATITUDE_COL] = df[LATITUDE_COL].astype(str).str.replace(',', '.', regex=False)
    df[LONGITUDE_COL] = df[LONGITUDE_COL].astype(str).str.replace(',', '.', regex=False)
    df[LATITUDE_COL] = pd.to_numeric(df[LATITUDE_COL], errors='coerce')
    df[LONGITUDE_COL] = pd.to_numeric(df[LONGITUDE_COL], errors='coerce')
except Exception as e:
    st.error(f"Erreur conversion coordonnées : {e}")
    st.stop()


# AJOUT : Conversion des colonnes dates en datetime pour éviter les erreurs
df[col_date_ouv] = pd.to_datetime(df[col_date_ouv], errors='coerce')
df[col_date_trvx] = pd.to_datetime(df[col_date_trvx], errors='coerce')

df = df.dropna(subset=[LATITUDE_COL, LONGITUDE_COL])

if df.empty:
    st.error("Aucune donnée valide après nettoyage.")
    st.stop()


# --- 5. PARAMÈTRES UTILISATEUR ---

with st.sidebar:
    st.header("2. Paramètres")

    # A. Sélection du site référence
    site_options = df[REFERENCE_COL].unique()
    site_ref = st.selectbox("Choisir le site référence :", options=site_options)
    
    # On récupère tout de suite la ligne du site sélectionné
    ref_row = df[df[REFERENCE_COL] == site_ref].iloc[0]

    # On récupère les deux dates possibles
    date_ouv_val = ref_row[col_date_ouv]
    date_trvx_val = ref_row[col_date_trvx]
    
    st.markdown("---")
    st.write("**Sélection de la Date de visite**")
    
    # Choix de la source de date via un bouton Radio
    choix_date = st.radio(
        "Sur quelle base fixer la date ?",
        options=[col_date_ouv, col_date_trvx],
        captions=["Date d'ouverture", "Début chantier"]
    )

    # Définition de la valeur par défaut selon le choix
    if choix_date == col_date_ouv:
        default_date = date_ouv_val
    else:
        default_date = date_trvx_val
        
    # Gestion des cas où la date est vide (NaT) dans l'Excel
    if pd.isna(default_date):
        st.warning(f"⚠️ Pas de date trouvée pour '{choix_date}'. Date du jour utilisée par défaut.")
        default_date = pd.Timestamp.today()

    # B. Le champ Date de visite (pré-rempli avec le choix ci-dessus)
    # Note: st.date_input retourne un objet 'date' (sans heure), mais pandas utilise des Timestamps
    visit_date = st.date_input("Sélectionner une autre date", value=default_date)
    st.markdown("---")

    # C. Rayon et Tolérance
    rayon_km = st.slider("Rayon de recherche (km)", 1, 500, 50, 1)
    tolerance_days = st.number_input("Tolérance (jours calendaire) +/-", min_value=1, value=5, step=1)

    # Calcul de la fenêtre (objets datetime.date)
    date_min = visit_date - timedelta(days=tolerance_days)
    date_max = visit_date + timedelta(days=tolerance_days)


# --- 6. LOGIQUE DE CALCUL (Distance et Filtrage initial) ---

ref_lat = ref_row[LATITUDE_COL]
ref_lon = ref_row[LONGITUDE_COL]

# Calculer la distance
df['Distance_km'] = haversine_distance(ref_lat, ref_lon, df[LATITUDE_COL], df[LONGITUDE_COL])

# Filtrer par distance
df_filtered = df[df['Distance_km'] <= rayon_km].sort_values(by='Distance_km')


# --- 7. LOGIQUE DE CRITÈRES D'ÉLIGIBILITÉ ET MISE À JOUR DES VOISINS (CORRECTION CLÉ) ---

def is_date_in_tolerance(date_val, date_min, date_max):
    """Vérifie si une date (Timestamp) est dans l'intervalle [date_min, date_max] (datetime.date)"""
    if pd.isna(date_val) or not isinstance(date_val, pd.Timestamp):
        return False
    target_date = date_val.date()
    return date_min <= target_date <= date_max

# Créer la colonne booléenne pour l'éligibilité de la date (Ouv OU Trvx)
df_filtered['Eligible_Date'] = df_filtered.apply(
    lambda row: is_date_in_tolerance(row[col_date_ouv], date_min, date_max) or 
                is_date_in_tolerance(row[col_date_trvx], date_min, date_max),
    axis=1
)

# CORRECTION: On définit Voisins APRES avoir calculé 'Eligible_Date' sur df_filtered
voisins = df_filtered[df_filtered[REFERENCE_COL] != site_ref]


# Filtrer les sites qui sont éligibles en distance ET en date (et ne sont pas le site de référence)
sites_eligibles = voisins[voisins['Eligible_Date'] == True].sort_values(by='Distance_km')


# --- 8. AFFICHAGE DES RÉSULTATS ---

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader(f"Carte des résultats ({len(voisins)} voisins)")
    m = folium.Map(location=[ref_lat, ref_lon], zoom_start=10)

    # Zone Rayon
    folium.Circle(
        location=[ref_lat, ref_lon],
        radius=rayon_km * 1000,
        color="#3186cc", fill=True, fill_opacity=0.1,
        tooltip=f"Rayon {rayon_km} km"
    ).add_to(m)

    # Site Référence (Rouge)
    folium.Marker(
        [ref_lat, ref_lon],
        tooltip=f"REF: {site_ref}",
        icon=folium.Icon(color="red", icon="star")
    ).add_to(m)

    # Voisins (Bleu/Vert selon éligibilité)
    for _, row in voisins.iterrows():
        # Ligne corrigée: 'Eligible_Date' est maintenant disponible dans 'row'
        marker_color = "green" if row['Eligible_Date'] else "blue"
        marker_icon = "check" if row['Eligible_Date'] else "info-sign"

        tooltip_txt = f"{row[REFERENCE_COL]} ({row['Distance_km']:.1f} km)"
        folium.Marker(
            [row[LATITUDE_COL], row[LONGITUDE_COL]],
            tooltip=tooltip_txt,
            icon=folium.Icon(color=marker_color, icon=marker_icon)
        ).add_to(m)

    st_folium(m, width="100%", height=500)


with col2:
    
    st.subheader("Synthèse des sites à visiter")
    
    # --- ENCADRÉ RÉSUMÉ ---
    if not sites_eligibles.empty:
        # Affichage des sites éligibles
        site_names = sites_eligibles[REFERENCE_COL].tolist()
        summary_text = f"**{len(site_names)} site(s)** répondent aux deux critères (distance et date) :\n\n- " + "\n- ".join(site_names)
        st.success(summary_text)
    else:
        st.info("🤷‍♂️ Aucun site voisin n'est éligible (distance et date).")
    
    st.markdown("---")
    st.subheader("Détail des sites à proximité")

    # Affichage personnalisé (on retire la colonne technique 'Eligible_Date')
    cols_base = [REFERENCE_COL, 'Distance_km', col_date_ouv, col_date_trvx]
    other_cols = [c for c in df_filtered.columns if c not in cols_base + [LATITUDE_COL, LONGITUDE_COL, 'Eligible_Date']]
    
    # Création du DataFrame d'affichage
    # On utilise df_filtered (qui inclut tous les sites dans le rayon)
    display_df = df_filtered[cols_base + other_cols].copy()

    # --- LOGIQUE DE STYLE ---
    
    # 1. Fonction pour colorer en vert si dans la tolérance
    def style_green_date(val):
        """
        Applique un fond vert si la date est comprise entre date_min et date_max.
        """
        # On utilise la fonction 'is_date_in_tolerance' globale pour la vérification
        if is_date_in_tolerance(val, date_min, date_max):
            return 'background-color: #90ee90; color: black; font-weight: bold'  # Vert clair
        return ''

    # 2. Fonction pour colorer la ligne référence en rouge clair
    def boldfirstlign(s):
        return ['font-weight: 900' if s[REFERENCE_COL] == site_ref else '' for _ in s]
   #def highlight_ref(s):
       # return ['background-color: #ffcccc' if s[REFERENCE_COL] == site_ref else '' for _ in s]

    # Application des styles   """.apply(highlight_ref, axis=1)"""
    styled_df = (display_df.style
                 .apply(boldfirstlign, axis=1)
                 .map(style_green_date, subset=[col_date_ouv, col_date_trvx])
                 .format({'Distance_km': "{:.1f}"}))

    # Affichage avec configuration des colonnes pour un format de date propre (JJ/MM/AAAA)
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            col_date_ouv: st.column_config.DateColumn(
                "Ouverture Est.",
                format="DD/MM/YYYY"
            ),
            col_date_trvx: st.column_config.DateColumn(
                "Début Travaux",
                format="DD/MM/YYYY"
            ),
            'Distance_km': st.column_config.NumberColumn(
                "Distance (km)",
                format="%.1f km"
            )
        }
    )

    st.info(f"Site référence : **{site_ref}**\n\nDate cible (visite) : **{visit_date}**\n\nFenêtre tolérée : **{date_min}** au **{date_max}**")
