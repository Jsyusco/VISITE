import streamlit as st
import pandas as pd
import uuid
import urllib.parse
from datetime import datetime

# Import des fonctions et constantes depuis utils.py
# (Assurez-vous que utils.py est dans le même répertoire)
import utils

# --- CONFIGURATION ET STYLE ---
st.set_page_config(page_title="Formulaire Dynamique - Firestore", layout="centered")

# CSS pour le thème sombre et les couleurs spécifiques
st.markdown("""
<style>
    .stApp { background-color: #121212; color: #e0e0e0; }
    .main-header { background-color: #1e1e1e; padding: 20px; border-radius: 10px; margin-bottom: 20px; text-align: center; border-bottom: 3px solid #E9630C; }
    .block-container { max-width: 800px; }
    .phase-block { background-color: #1e1e1e; padding: 25px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #333; }
    .question-card { background-color: transparent; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 3px solid #E9630C; }
    h1, h2, h3 { color: #ffffff !important; }
    .description { font-size: 0.9em; color: #EB6408; margin-bottom: 10px; }
    .mandatory { color: #F4B400; font-weight: bold; margin-left: 5px; }
    .success-box { background-color: #1e4620; padding: 15px; border-radius: 8px; border-left: 5px solid #4caf50; color: #fff; margin: 10px 0; }
    .error-box { background-color: #3d1f1f; padding: 15px; border-radius: 8px; border-left: 5px solid #ff6b6b; color: #ffdad9; margin: 10px 0; }
    .stButton > button { border-radius: 8px; font-weight: bold; padding: 0.5rem 1rem; }
    div[data-testid="stButton"] > button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- GESTION DE L'ÉTAT ---
def init_session_state():
    """Initialise l'état de session avec les valeurs par défaut."""
    defaults = {
        'step': 'PROJECT_LOAD',
        'project_data': None,
        'collected_data': [],
        'current_phase_temp': {},
        'current_phase_name': None,
        'iteration_id': str(uuid.uuid4()), 
        'identification_completed': False,
        'data_saved': False,
        'id_rendering_ident': None,
        'form_start_time': None,
        'submission_id': None,
        'show_comment_on_error': False,
        'df_struct': None,
        'df_site': None,
        'last_validation_errors': None 
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- FLUX PRINCIPAL ---

st.markdown('<div class="main-header"><h1>📝Formulaire Chantier </h1></div>', unsafe_allow_html=True)

# 1. CHARGEMENT
if st.session_state['step'] == 'PROJECT_LOAD':
    st.info("Tentative de chargement de la structure des formulaires...")
    with st.spinner("Chargement en cours..."):
        df_struct = utils.load_form_structure_from_firestore()
        utils.load_site_data_from_firestore.clear() 
        df_site = utils.load_site_data_from_firestore()
        
        if df_struct is not None and df_site is not None:
            st.session_state['df_struct'] = df_struct
            st.session_state['df_site'] = df_site
            st.session_state['step'] = 'PROJECT'
            st.rerun()
        else:
            st.error("Impossible de charger les données. Vérifiez votre connexion et les secrets Firebase.")
            if st.button("Réessayer le chargement"):
                utils.load_form_structure_from_firestore.clear() 
                utils.load_site_data_from_firestore.clear() 
                st.session_state['step'] = 'PROJECT_LOAD'
                st.rerun()

# 2. SELECTION PROJET
elif st.session_state['step'] == 'PROJECT':
    df_site = st.session_state['df_site']
    st.markdown("### 🏗️ Sélection du Chantier")
    
    if 'Intitulé' not in df_site.columns:
        st.error("Colonne 'Intitulé' manquante dans les données 'Sites'.")
    else:
        search_term = st.text_input("Rechercher un projet (Veuillez renseigner au minimum 3 caractères pour le nom de la ville)", key="project_search_input").strip()
        filtered_projects = []
        selected_proj = None
        
        if len(search_term) >= 3:
            mask = df_site['Intitulé'].str.contains(search_term, case=False, na=False)
            filtered_projects_df = df_site[mask]
            filtered_projects = [""] + filtered_projects_df['Intitulé'].dropna().unique().tolist()
            if filtered_projects:
                selected_proj = st.selectbox("Résultats de la recherche", filtered_projects)
            else:
                st.warning(f"Aucun projet trouvé pour **'{search_term}'**.")
        elif len(search_term) > 0 and len(search_term) < 3:
            st.info("Veuillez entrer au moins **3 caractères** pour lancer la recherche.")
        
        if selected_proj:
            row = df_site[df_site['Intitulé'] == selected_proj].iloc[0]
            st.info(f"Projet sélectionné : **{selected_proj}**")
            if st.button("✅ Démarrer l'identification"):
                st.session_state['project_data'] = row.to_dict()
                st.session_state['form_start_time'] = datetime.now() 
                st.session_state['submission_id'] = str(uuid.uuid4())
                st.session_state['step'] = 'IDENTIFICATION'
                st.session_state['current_phase_temp'] = {}
                st.session_state['iteration_id'] = str(uuid.uuid4())
                st.session_state['show_comment_on_error'] = False
                st.session_state['last_validation_errors'] = None
                st.rerun()

# 3. IDENTIFICATION
elif st.session_state['step'] == 'IDENTIFICATION':
    df = st.session_state['df_struct']
    ID_SECTION_NAME = df['section'].iloc[0]
    st.markdown(f"### 👤 Étape unique : {ID_SECTION_NAME}")
    
    identification_questions = df[df['section'] == ID_SECTION_NAME].copy()
    
    # 1. Assurer que l'ID est numérique
    identification_questions['id_temp'] = pd.to_numeric(identification_questions['id'], errors='coerce').fillna(0)
    
    # 2. Trier par ID numérique croissant pour la logique conditionnelle
    identification_questions = identification_questions.sort_values(by='id_temp')

    if st.session_state['id_rendering_ident'] is None: st.session_state['id_rendering_ident'] = str(uuid.uuid4())
    rendering_id = st.session_state['id_rendering_ident']
    
    for idx, (index, row) in enumerate(identification_questions.iterrows()):
        if utils.check_condition(row, st.session_state['current_phase_temp'], st.session_state['collected_data']):
            utils.render_question(row, st.session_state['current_phase_temp'], ID_SECTION_NAME, rendering_id, idx, st.session_state['project_data'])
            

    # --- AFFICHAGE PERSISTANT DES ERREURS DE VALIDATION (IDENTIFICATION) ---
    if st.session_state['last_validation_errors']:
        st.markdown(
            f'<div class="error-box"><b>⚠️ Erreur de validation :</b><br>Les questions suivantes nécessitent une réponse ou une correction :<br>{st.session_state["last_validation_errors"]}</div>', 
            unsafe_allow_html=True
        )
    # ------------------------------------------------------------------------

    st.markdown("---")
    if st.button("✅ Valider l'identification"):
        st.session_state['last_validation_errors'] = None # Réinitialisation à la tentative de validation
        
        # --- CORRECTION ROBUSTESSE IDENTIFICATION (Vérification df_struct) ---
        df_struct = st.session_state.get('df_struct')
        if df_struct is None:
            st.error("Structure du formulaire manquante. Veuillez recharger le projet.")
            st.rerun() # <--- CORRECTION ICI
        # --------------------------------------------------------------------
        
        # NOTE: On n'utilise pas le try/except ici pour ne pas masquer d'erreur dans l'étape initiale
        is_valid, errors = utils.validate_section(df_struct, ID_SECTION_NAME, st.session_state['current_phase_temp'], st.session_state['collected_data'], st.session_state['project_data'])
        
        if is_valid:
            id_entry = {"phase_name": ID_SECTION_NAME, "answers": st.session_state['current_phase_temp'].copy()}
            st.session_state['collected_data'].append(id_entry)
            st.session_state['identification_completed'] = True
            st.session_state['step'] = 'LOOP_DECISION'
            st.session_state['current_phase_temp'] = {}
            st.session_state['show_comment_on_error'] = False
            st.session_state['last_validation_errors'] = None 
            st.success("Identification validée.")
            st.rerun()
        else:
            # --- CORRECTION ROBUSTESSE D'ERREUR V2 ---
            cleaned_errors = [str(e) for e in errors if e is not None]

            html_errors = '<br>'.join([f"- {e}" for e in cleaned_errors])
            st.session_state['last_validation_errors'] = html_errors
            st.rerun() # <--- CORRECTION ICI
            # -----------------------------------------

# 4. BOUCLE PHASES
elif st.session_state['step'] in ['LOOP_DECISION', 'FILL_PHASE']:
    project_intitule = st.session_state['project_data'].get('Intitulé', 'Projet Inconnu')
    with st.expander(f"📍 Projet : {project_intitule}", expanded=False):
        project_details = st.session_state['project_data']
        st.markdown(":orange-badge[**Détails du Projet sélectionné :**]")
        
        # Affichage des détails du projet (récupéré des données 'Sites')
        with st.container(border=True):
            st.markdown("**Informations générales**")
            cols1 = st.columns([1, 1, 1]) 
            fields_l1 = utils.DISPLAY_GROUPS[0]
            for i, field_key in enumerate(fields_l1):
                renamed_key = utils.PROJECT_RENAME_MAP.get(field_key, field_key)
                value = project_details.get(field_key, 'N/A')
                with cols1[i]: st.markdown(f"**{renamed_key}** : {value}")
                    
        with st.container(border=True):
            st.markdown("**Points de charge Standard**")
            cols2 = st.columns([1, 1, 1])
            fields_l2 = utils.DISPLAY_GROUPS[1]
            for i, field_key in enumerate(fields_l2):
                renamed_key = utils.PROJECT_RENAME_MAP.get(field_key, field_key)
                value = project_details.get(field_key, 'N/A')
                with cols2[i]: st.markdown(f"**{renamed_key}** : {value}")

        with st.container(border=True):
            st.markdown("**Points de charge Pré-équipés**")
            cols3 = st.columns([1, 1, 1])
            fields_l3 = utils.DISPLAY_GROUPS[2]
            for i, field_key in enumerate(fields_l3):
                renamed_key = utils.PROJECT_RENAME_MAP.get(field_key, field_key)
                value = project_details.get(field_key, 'N/A')
                with cols3[i]: st.markdown(f"**{renamed_key}** : {value}")
        
        st.write(":orange-badge[**Phases et Identification déjà complétées :**]")
        for idx, item in enumerate(st.session_state['collected_data']):
            st.write(f"• **{item['phase_name']}** : {len(item['answers'])} réponses")

    if st.session_state['step'] == 'LOOP_DECISION':
        st.markdown("### 🔄 Gestion des Phases")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Ajouter une phase"):
                st.session_state['step'] = 'FILL_PHASE'
                st.session_state['current_phase_temp'] = {}
                st.session_state['current_phase_name'] = None
                st.session_state['iteration_id'] = str(uuid.uuid4())
                st.session_state['show_comment_on_error'] = False
                st.session_state['last_validation_errors'] = None
                st.rerun()
        with col2:
            if st.button("🏁 Terminer l'audit"):
                st.session_state['step'] = 'FINISHED'
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state['step'] == 'FILL_PHASE':
        df = st.session_state['df_struct']
        ID_SECTION_NAME = df['section'].iloc[0]
        ID_SECTION_CLEAN = str(ID_SECTION_NAME).strip().lower()
        # Exclure la section d'identification et la ligne de question 'phase' si elle existe
        SECTIONS_TO_EXCLUDE_CLEAN = {ID_SECTION_CLEAN, "phase"} 
        all_sections_raw = df['section'].unique().tolist()
        available_phases = []
        for sec in all_sections_raw:
            if pd.isna(sec) or not sec or str(sec).strip().lower() in SECTIONS_TO_EXCLUDE_CLEAN: continue
            available_phases.append(sec)
        
        if not st.session_state['current_phase_name']:
              st.markdown("### 📑 Sélection de la phase")
              phase_choice = st.selectbox("Quelle phase ?", [""] + available_phases)
              if phase_choice:
                  st.session_state['current_phase_name'] = phase_choice
                  st.session_state['show_comment_on_error'] = False 
                  st.session_state['last_validation_errors'] = None
                  st.rerun()
              if st.button("⬅️ Retour"):
                  st.session_state['step'] = 'LOOP_DECISION'
                  st.session_state['current_phase_temp'] = {}
                  st.session_state['show_comment_on_error'] = False
                  st.session_state['last_validation_errors'] = None
                  st.rerun()
        else:
            current_phase = st.session_state['current_phase_name']
            st.markdown(f"### 📝 {current_phase}")
            if st.button("🔄 Changer de phase"):
                st.session_state['current_phase_name'] = None
                st.session_state['current_phase_temp'] = {}
                st.session_state['iteration_id'] = str(uuid.uuid4())
                st.session_state['show_comment_on_error'] = False
                st.session_state['last_validation_errors'] = None
                st.rerun()
            st.divider()
            
            section_questions = df[df['section'] == current_phase].copy()
            section_questions['id_temp'] = pd.to_numeric(section_questions['id'], errors='coerce').fillna(0)
            section_questions = section_questions.sort_values(by='id_temp')

            visible_count = 0
            for idx, (index, row) in enumerate(section_questions.iterrows()):
                if int(row.get('id', 0)) == utils.COMMENT_ID: continue
                
                if utils.check_condition(row, st.session_state['current_phase_temp'], st.session_state['collected_data']):
                    utils.render_question(row, st.session_state['current_phase_temp'], current_phase, st.session_state['iteration_id'], idx, st.session_state['project_data'])
                    visible_count += 1
            
            if visible_count == 0 and not st.session_state.get('show_comment_on_error', False):
                st.warning("Aucune question visible dans cette phase.")

            if st.session_state.get('show_comment_on_error', False):
                st.markdown("---")
                st.markdown("### ✍️ Justification de l'Écart")
                comment_row = pd.Series({'id': utils.COMMENT_ID, 'type': 'text'}) 
                utils.render_question(comment_row, st.session_state['current_phase_temp'], current_phase, st.session_state['iteration_id'], 999, st.session_state['project_data']) 
            
            # --- AFFICHAGE PERSISTANT DES ERREURS DE VALIDATION (PHASE) ---
            if st.session_state['last_validation_errors']:
                st.markdown(
                    f'<div class="error-box"><b>⚠️ Erreurs :</b><br>Les questions suivantes nécessitent une réponse ou une correction :<br>{st.session_state["last_validation_errors"]}</div>', 
                    unsafe_allow_html=True
                )
            # ------------------------------------------------------------------------

            st.markdown("---")
            c1, c2 = st.columns([1, 2])
            with c1:
                if st.button("❌ Annuler"):
                    st.session_state['step'] = 'LOOP_DECISION'
                    st.session_state['current_phase_temp'] = {}
                    st.session_state['show_comment_on_error'] = False
                    st.session_state['last_validation_errors'] = None
                    st.rerun()
            with c2:
                if st.button("💾 Valider la phase"):
                    st.session_state['show_comment_on_error'] = False
                    st.session_state['last_validation_errors'] = None

                    # --- CORRECTION ROBUSTESSE PHASE (Vérification df_struct) ---
                    df_struct = st.session_state.get('df_struct')
                    if df_struct is None:
                        st.error("Structure du formulaire manquante. Veuillez recharger le projet.")
                        st.rerun() # <--- CORRECTION ICI
                        st.stop()
                    # -------------------------------------------------------------
                    
                    # --- NOUVEAU BLOC TRY/EXCEPT POUR ISOLER L'ATTRIBUTERROR ---
                    try:
                        is_valid, errors = utils.validate_section(
                            df_struct, 
                            current_phase, 
                            st.session_state['current_phase_temp'], 
                            st.session_state['collected_data'], 
                            st.session_state['project_data']
                        )
                    except AttributeError as e:
                        # Si l'erreur se produit DANS la fonction de validation
                        st.session_state['last_validation_errors'] = f"Erreur critique dans la validation (AttributeError) : {e}"
                        st.error(f"Erreur interne : {e}. Veuillez contacter le support. (Code: ATTRIB-VALID)")
                        st.session_state['show_comment_on_error'] = True 
                        st.rerun() # <--- CORRECTION IMPORTANTE ICI (Ligne qui plantait)
                        st.stop()

                    if is_valid:
                        new_entry = {"phase_name": current_phase, "answers": st.session_state['current_phase_temp'].copy()}
                        st.session_state['collected_data'].append(new_entry)
                        st.success("Phase validée et enregistrée !")
                        st.session_state['step'] = 'LOOP_DECISION'
                        st.session_state['last_validation_errors'] = None
                        st.rerun()
                    else:
                        # --- CORRECTION ROBUSTESSE D'ERREUR V2 ---
                        cleaned_errors = [str(e) for e in errors if e is not None]

                        # Vérifie si l'erreur est liée au manque de justification pour les photos
                        is_photo_error = any(f"Commentaire (ID {utils.COMMENT_ID})" in e for e in cleaned_errors)
                        if is_photo_error: st.session_state['show_comment_on_error'] = True
                        
                        html_errors = '<br>'.join([f"- {e}" for e in cleaned_errors])
                        st.session_state['last_validation_errors'] = html_errors
                        st.rerun() # <--- CORRECTION ICI
                        # -----------------------------------------
            st.markdown('</div>', unsafe_allow_html=True)

# 5. FIN / EXPORTS
elif st.session_state['step'] == 'FINISHED':
    st.markdown("## 🎉 Formulaire Terminé")
    project_name = st.session_state['project_data'].get('Intitulé', 'Projet Inconnu')
    st.write(f"Projet : **{project_name}**")
    st.warning('Il est attendu que vous téléchargiez le rapport Word ci-dessous pour le transmettre à votre interlocuteur.', icon="⚠️")
    
    
    # 1. SAUVEGARDE FIREBASE
    if not st.session_state['data_saved']:
        with st.spinner("Sauvegarde des réponses dans Firestore..."):
            success, result_message = utils.save_form_data(
                st.session_state['collected_data'], 
                st.session_state['project_data'],
                st.session_state['submission_id'],
                st.session_state['form_start_time']
            )

            if success:
                st.session_state['data_saved'] = True
                st.session_state['submission_id_final'] = result_message
            else:
                st.error(f"Erreur lors de la sauvegarde : {result_message}")
                if st.button("Réessayer la sauvegarde"):
                    st.rerun()
    else:
        st.info(f"Les données sont sauvegardées dans Firestore (ID: {st.session_state.get('submission_id_final', 'N/A')})")

    if st.session_state['data_saved']:
        # Préparation des exports
        csv_data = utils.create_csv_export(
            st.session_state['collected_data'], 
            st.session_state['df_struct'], 
            project_name, 
            st.session_state['submission_id'], 
            st.session_state['form_start_time']
        )
        zip_buffer = utils.create_zip_export(st.session_state['collected_data'])
        date_str = datetime.now().strftime('%Y%m%d_%H%M')
        
        # --- 2. TÉLÉCHARGEMENT DIRECT ---
        st.markdown("### 📥 Télécharger les fichiers")
        
        col_csv, col_zip, col_word = st.columns(3)
        
        file_name_csv = f"Export_{project_name}_{date_str}.csv"
        with col_csv:
            st.download_button(
                label="📄 CSV", 
                data=csv_data, 
                file_name=file_name_csv, 
                mime='text/csv',
                use_container_width=True
            )

        if zip_buffer:
            file_name_zip = f"Photos_{project_name}_{date_str}.zip"
            with col_zip:
                st.download_button(
                    label="📸 ZIP Photos", 
                    data=zip_buffer.getvalue(), 
                    file_name=file_name_zip, 
                    mime='application/zip',
                    use_container_width=True
                )
        
        # Génération du rapport Word
        with st.spinner("Génération du rapport Word..."):
            try:
                word_buffer = utils.create_word_report(
                    st.session_state['collected_data'],
                    st.session_state['df_struct'],
                    st.session_state['project_data'],
                    st.session_state['form_start_time']
                )
                
                file_name_word = f"Rapport_{project_name}_{date_str}.docx"
                with col_word:
                    st.download_button(
                        label="📋 Rapport Word", 
                        data=word_buffer.getvalue(), 
                        file_name=file_name_word, 
                        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Erreur lors de la génération du rapport Word : {e}")
    
        # --- 3. OUVERTURE DE L'APPLICATION NATIVE (MAILTO) ---
        st.markdown("---")
        st.markdown("### 📧 Partager par Email")
        st.info("💡 Téléchargez d'abord les fichiers ci-dessus, puis cliquez sur le bouton ci-dessous pour ouvrir votre application email.")
        
        subject = f"Rapport Audit : {project_name}"
        body = (
            f"Bonjour,\n\n"
            f"Veuillez trouver ci-joint le rapport d'audit pour le projet {project_name}.\n"
            f"Fichiers à joindre :\n"
            f"- {file_name_csv}\n"
            f"- {file_name_zip}\n"
            f"- {file_name_word}\n\n"
            f"Cordialement."
        )
        
        mailto_link = (
            f"mailto:?" 
            f"subject={urllib.parse.quote(subject)}" 
            f"&body={urllib.parse.quote(body)}"
        )
        
        st.markdown(
            f'<a href="{mailto_link}" target="_blank" style="text-decoration: none;">'
            f'<button style="background-color: #E9630C; color: white; border: none; padding: 10px 20px; border-radius: 8px; width: 100%; font-size: 16px; cursor: pointer;">'
            f'📧 Ouvrir l\'application Email'
            f'</button>'
            f'</a>',
            unsafe_allow_html=True
        )

    st.markdown("---")
    if st.button("🔄 Recommencer l'audit"):
        st.session_state.clear()
        st.rerun()
