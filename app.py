import streamlit as st
import pandas as pd
import os
import time
from email_sender import EmailSender
from gmail_sender import GmailSender
from utils import validate_email, validate_csv_columns, process_uploaded_file
import threading
import queue
import json
import hashlib
import random

# Page configuration
st.set_page_config(
    page_title="LBK-DevTools Sender",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for background image
st.markdown("""
    <style>
    .stApp {
        background-image: url("https://jazzy-cocada-7b049f.netlify.app/t%C3%A9l%C3%A9chargement.png");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    
    /* Améliorer la lisibilité du contenu sur l'image */
    .main .block-container {
        background-color: rgba(255, 255, 255, 0.95);
        padding: 2rem;
        border-radius: 10px;
    }
    
    /* Style pour la sidebar - plus transparent avec effet de flou */
    [data-testid="stSidebar"] {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.4), rgba(240, 240, 255, 0.5)) !important;
        backdrop-filter: blur(15px) saturate(180%);
        -webkit-backdrop-filter: blur(15px) saturate(180%);
        border-right: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    [data-testid="stSidebar"] > div:first-child {
        background: transparent !important;
    }
    
    /* Améliorer le contraste du texte dans la sidebar */
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: #1a1a1a !important;
        font-weight: 500 !important;
    }
    
    /* Style pour les inputs dans la sidebar */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] select,
    [data-testid="stSidebar"] textarea {
        background-color: rgba(255, 255, 255, 0.8) !important;
        border: 1px solid rgba(0, 0, 0, 0.2) !important;
    }
    </style>
""", unsafe_allow_html=True)

# Create unique session ID for each user
if 'session_id' not in st.session_state:
    # Create unique session ID using timestamp and random number
    session_data = f"{time.time()}_{random.randint(1000, 9999)}"
    st.session_state.session_id = hashlib.md5(session_data.encode()).hexdigest()[:8]

# Initialize session state
if 'email_sender' not in st.session_state:
    st.session_state.email_sender = None
if 'gmail_sender' not in st.session_state:
    st.session_state.gmail_sender = None
if 'contacts_df' not in st.session_state:
    st.session_state.contacts_df = None
if 'sending_status' not in st.session_state:
    st.session_state.sending_status = {'active': False, 'progress': 0, 'total': 0, 'success': 0, 'errors': []}
if 'send_logs' not in st.session_state:
    st.session_state.send_logs = []
if 'send_method' not in st.session_state:
    st.session_state.send_method = 'SMTP'
if 'attachments' not in st.session_state:
    st.session_state.attachments = []

def main():
    st.title("📧 LBK-DevTools Sender")
    st.markdown("*Développé par Mr LeBurkinabe*")
    
    # Display session info for debugging
    with st.expander("🔧 Informations de Session (Debug)", expanded=False):
        st.code(f"ID de Session: {st.session_state.session_id}")
        st.info("Chaque utilisateur a un ID de session unique pour éviter les conflits.")
    
    st.markdown("---")

    # Initialize variables with defaults
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = True
    use_ssl = False
    sender_email = os.getenv("SENDER_EMAIL", "")
    sender_password = os.getenv("SENDER_PASSWORD", "")
    sender_name = os.getenv("SENDER_NAME", "")
    reply_to_email = ""
    gmail_sender_name = os.getenv("GMAIL_SENDER_NAME", "")

    # Sidebar for email configuration
    with st.sidebar:
        st.header("⚙️ Configuration Email")

        # Choose sending method
        send_method = st.radio(
            "Méthode d'envoi",
            ["SMTP", "Gmail API"],
            help="Choisissez SMTP pour serveur email classique ou Gmail API pour utiliser l'API Google"
        )
        st.session_state.send_method = send_method

        st.markdown("---")

        if send_method == "SMTP":
            st.subheader("📧 Configuration SMTP")
            
            # Preset SMTP servers
            smtp_preset = st.selectbox(
                "Serveur prédéfini (optionnel)",
                ["Personnalisé", "Gmail", "Outlook/Hotmail", "Yahoo", "Office 365", "iCloud"],
                help="Sélectionnez un serveur prédéfini ou choisissez 'Personnalisé'"
            )
            
            # Set defaults based on preset
            preset_configs = {
                "Gmail": {"server": "smtp.gmail.com", "port": 587, "security": "STARTTLS"},
                "Outlook/Hotmail": {"server": "smtp-mail.outlook.com", "port": 587, "security": "STARTTLS"},
                "Yahoo": {"server": "smtp.mail.yahoo.com", "port": 465, "security": "SSL"},
                "Office 365": {"server": "smtp.office365.com", "port": 587, "security": "STARTTLS"},
                "iCloud": {"server": "smtp.mail.me.com", "port": 587, "security": "STARTTLS"}
            }
            
            if smtp_preset != "Personnalisé":
                preset = preset_configs[smtp_preset]
                default_server = preset["server"]
                default_port = preset["port"]
                default_security = preset["security"]
            else:
                default_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
                default_port = int(os.getenv("SMTP_PORT", "587"))
                default_security = "STARTTLS"

            smtp_server = st.text_input(
                "Serveur SMTP",
                value=default_server,
                help="Exemple: smtp.gmail.com, smtp.outlook.com"
            )

            smtp_port = st.number_input(
                "Port SMTP",
                min_value=1,
                max_value=65535,
                value=default_port,
                help="Port communs: 587 (STARTTLS), 465 (SSL), 25 (non-sécurisé)"
            )

            security_type = st.selectbox(
                "Type de sécurité",
                ["STARTTLS", "SSL", "Aucune"],
                index=["STARTTLS", "SSL", "Aucune"].index(default_security),
                help="STARTTLS (port 587) ou SSL (port 465) recommandés pour la sécurité"
            )
            
            use_tls = security_type == "STARTTLS"
            use_ssl = security_type == "SSL"

            sender_email = st.text_input(
                "Email expéditeur",
                value=os.getenv("SENDER_EMAIL", ""),
                help="Votre adresse email"
            )

            sender_password = st.text_input(
                "Mot de passe",
                type="password",
                value=os.getenv("SENDER_PASSWORD", ""),
                help="Mot de passe ou mot de passe d'application"
            )

            sender_name = st.text_input(
                "Nom de l'expéditeur",
                value=os.getenv("SENDER_NAME", ""),
                help="Nom qui apparaîtra dans l'email"
            )

            reply_to_email = st.text_input(
                "Email de réponse (Reply-To)",
                value=os.getenv("REPLY_TO_EMAIL", ""),
                help="Adresse email sur laquelle les destinataires pourront répondre (laissez vide pour utiliser l'email expéditeur)",
                placeholder="exemple@domaine.com"
            )

            # Test SMTP connection
            if st.button("🔍 Tester la Connexion SMTP"):
                if sender_email and sender_password:
                    with st.spinner("Test de connexion..."):
                        test_sender = EmailSender(
                            smtp_server, smtp_port, use_tls,
                            sender_email, sender_password, sender_name, use_ssl, reply_to_email
                        )
                        if test_sender.test_connection():
                            st.success("✅ Connexion SMTP réussie!")
                        else:
                            st.error("❌ Échec de la connexion SMTP. Vérifiez vos paramètres.")
                else:
                    st.warning("⚠️ Veuillez remplir l'email et le mot de passe.")

        else:  # Gmail API
            st.subheader("🔐 Configuration Gmail API")

            st.info("📝 Pour utiliser Gmail API, vous devez créer un projet Google Cloud et télécharger le fichier credentials.json")
            st.warning("⚠️ L'authentification Gmail API se fera via un code d'autorisation que vous devrez copier-coller.")

            # Sender name for Gmail API
            gmail_sender_name = st.text_input(
                "Nom de l'expéditeur Gmail",
                value=os.getenv("GMAIL_SENDER_NAME", ""),
                help="Nom qui apparaîtra dans l'email pour vos destinataires"
            )

            # Upload credentials file
            credentials_file = st.file_uploader(
                "Fichier credentials.json",
                type=['json'],
                help="Téléchargez le fichier credentials.json depuis Google Cloud Console"
            )

            gmail_authenticated = False

            if credentials_file is not None:
                try:
                    credentials_content = credentials_file.read().decode('utf-8')
                    credentials_data = json.loads(credentials_content)

                    # Initialize Gmail sender
                    if 'gmail_sender' not in st.session_state or st.session_state.gmail_sender is None:
                        st.session_state.gmail_sender = GmailSender(sender_name=gmail_sender_name, session_id=st.session_state.session_id)

                    col_auth_gen1, col_auth_gen2 = st.columns([3, 1])
                    
                    with col_auth_gen1:
                        if st.button("🔐 Étape 1: Générer le lien d'autorisation"):
                            auth_result = st.session_state.gmail_sender.start_auth_flow(credentials_content)

                            if auth_result == "ALREADY_AUTHENTICATED":
                                st.success("✅ Déjà authentifié avec Gmail API!")
                                gmail_authenticated = True
                            elif auth_result.startswith("ERROR"):
                                st.error(f"❌ {auth_result}")
                            else:
                                st.session_state.auth_url = auth_result
                                st.success("🔗 Lien d'autorisation généré!")
                                
                                # Instructions détaillées avec étapes numérotées
                                st.markdown("### 📋 Instructions détaillées :")
                                st.markdown("**1.** Cliquez sur ce lien : [Autoriser Gmail API]({})".format(auth_result))
                                
                                with st.expander("📖 Guide détaillé - Étapes à suivre dans Google", expanded=True):
                                    st.markdown("""
                                    **Étape 2 :** Google va vous montrer une page avec des permissions à autoriser
                                    
                                    **Étape 3 :** 🚨 **CRITIQUE** - Vous DEVEZ cocher **TOUTES** les cases suivantes :
                                    - ✅ **"Afficher l'adresse e-mail associée à votre compte"**
                                    - ✅ **"Afficher vos e-mails et paramètres de messagerie"** 
                                    - ✅ **"Envoyer des e-mails en votre nom"** ← **ESSENTIEL pour l'envoi**
                                    
                                    **Étape 4 :** Cliquez sur **"Continuer"** ou **"Allow"**
                                    
                                    **Étape 5 :** Google va afficher un code d'autorisation - copiez-le ENTIÈREMENT
                                    
                                    **⚠️ ATTENTION :** Si vous ne cochez pas TOUTES les cases, l'authentification échouera !
                                    """)
                                
                                st.warning("🔴 **ERREUR FRÉQUENTE** : Ne pas cocher toutes les permissions = échec garanti !")

                    with col_auth_gen2:
                        if st.button("🗑️ Reset", help="Effacer le token existant"):
                            # Clear Gmail sender completely
                            if st.session_state.gmail_sender:
                                st.session_state.gmail_sender.clear_token()
                            st.session_state.gmail_sender = None
                            if hasattr(st.session_state, 'auth_url'):
                                delattr(st.session_state, 'auth_url')
                            # Recreate Gmail sender with current session
                            st.session_state.gmail_sender = GmailSender(sender_name=gmail_sender_name, session_id=st.session_state.session_id)
                            # Clear any previous authentication errors
                            st.session_state.gmail_sender.last_auth_error = None
                            st.success("Token effacé et session réinitialisée!")
                            st.rerun()

                    # Step 2: Enter authorization code
                    if hasattr(st.session_state, 'auth_url'):
                        col_auth1, col_auth2 = st.columns([3, 1])

                        with col_auth1:
                            auth_code = st.text_input(
                                "Code d'autorisation Google",
                                help="Copiez le code complet de la page d'autorisation Google (commençant généralement par '4/')",
                                placeholder="4/0AcvDMrXXXXXXXXXXXXXXXXXXXXXX..."
                            )
                            
                            # Add validation hints
                            if auth_code:
                                if len(auth_code.strip()) < 10:
                                    st.warning("⚠️ Le code semble trop court. Assurez-vous de copier le code complet.")
                                elif not auth_code.strip().startswith(('4/', '1/')):
                                    st.info("💡 Les codes d'autorisation commencent généralement par '4/' ou '1/'")
                                else:
                                    st.success("✅ Format du code validé")

                        with col_auth2:
                            if st.button("🔄 Nouveau lien"):
                                # Clear the current auth URL to force regeneration
                                if hasattr(st.session_state, 'auth_url'):
                                    delattr(st.session_state, 'auth_url')
                                st.rerun()

                        if st.button("🔐 Étape 2: Finaliser l'authentification"):
                            if auth_code and len(auth_code.strip()) > 5:
                                with st.spinner("Finalisation de l'authentification..."):
                                    success = st.session_state.gmail_sender.complete_authentication(auth_code)
                                    if success:
                                        st.success("✅ Authentification Gmail API réussie!")
                                        # Clean up auth URL
                                        if hasattr(st.session_state, 'auth_url'):
                                            delattr(st.session_state, 'auth_url')
                                        gmail_authenticated = True
                                        st.rerun()  # Refresh the page to show success
                                    else:
                                        # Display specific error message based on error type
                                        error_type = getattr(st.session_state.gmail_sender, 'last_auth_error', 'UNKNOWN_ERROR')
                                        
                                        if error_type == "CODE_EXPIRED_OR_INVALID":
                                            st.error("❌ Code d'autorisation invalide ou expiré.")
                                            st.info("⏰ **Solution** : Générez un nouveau lien d'autorisation et utilisez le code immédiatement.")
                                        elif error_type == "MISSING_GMAIL_SEND":
                                            st.error("❌ Permissions insuffisantes pour envoyer des emails.")
                                            st.warning("🚫 **Cause** : Vous avez refusé la permission 'Envoyer des e-mails en votre nom'")
                                            
                                            with st.expander("🔧 Solution détaillée", expanded=True):
                                                st.markdown("""
                                                **Ce qui s'est passé :**
                                                - ❌ Vous avez décoché ou refusé la permission d'envoi d'emails
                                                - ✅ Votre Google Cloud Console est bien configuré (comme votre capture d'écran le montre)
                                                - ❌ Mais vous n'avez pas autorisé toutes les permissions lors de l'OAuth
                                                
                                                **Solution :**
                                                1. Cliquez sur **'Reset'** ci-dessus
                                                2. Générez un nouveau lien d'autorisation
                                                3. **IMPORTANT** : Cette fois, cochez **TOUTES** les 3 cases :
                                                   - ✅ Afficher l'adresse e-mail
                                                   - ✅ Afficher vos e-mails et paramètres  
                                                   - ✅ **Envoyer des e-mails en votre nom** ← OBLIGATOIRE
                                                4. Cliquez "Continuer" puis collez le nouveau code
                                                """)
                                        elif error_type == "SCOPE_MISMATCH":
                                            st.error("❌ Problème de permissions détecté.")
                                            st.warning("🔐 **Action requise** : Les permissions ont changé. Cliquez sur 'Reset' puis générez un nouveau lien d'autorisation.")
                                            st.info("💡 **Important** : Assurez-vous d'autoriser TOUTES les permissions demandées par Google (email + envoi Gmail).")
                                            
                                            # Auto-reset pour simplifier le processus
                                            if st.button("🔄 Auto-Reset et Regénérer", type="primary"):
                                                # Clear Gmail sender completely
                                                if st.session_state.gmail_sender:
                                                    st.session_state.gmail_sender.clear_token()
                                                st.session_state.gmail_sender = None
                                                if hasattr(st.session_state, 'auth_url'):
                                                    delattr(st.session_state, 'auth_url')
                                                # Recreate Gmail sender
                                                st.session_state.gmail_sender = GmailSender(sender_name=gmail_sender_name, session_id=st.session_state.session_id)
                                                st.session_state.gmail_sender.last_auth_error = None
                                                st.success("✅ Session réinitialisée ! Cliquez maintenant sur 'Générer le lien d'autorisation'")
                                                st.rerun()
                                        elif error_type == "REDIRECT_MISMATCH":
                                            st.error("❌ Problème de configuration OAuth.")
                                            st.warning("🔧 **Configuration requise** : Vérifiez la configuration de votre Console Google.")
                                        elif error_type == "INVALID_CREDENTIALS":
                                            st.error("❌ Fichier credentials.json invalide.")
                                            st.warning("📄 **Solution** : Vérifiez et re-téléchargez votre fichier credentials.json.")
                                        else:
                                            st.error("❌ Code d'autorisation invalide ou expiré.")
                                            st.warning("⚠️ Problème de permissions détecté. Cliquez sur 'Reset' puis générez un nouveau lien d'autorisation.")
                                        
                                        with st.expander("🔍 Guide de dépannage complet"):
                                            st.markdown("""
                                            **Causes fréquentes :**
                                            - ⏰ **Code expiré** : Les codes Google expirent en 10 minutes
                                            - 🔄 **Code déjà utilisé** : Chaque code ne peut être utilisé qu'une seule fois
                                            - 🔐 **Problème de permissions** : Configuration OAuth incorrecte
                                            - 📱 **Format incorrect** : Copiez le code complet sans espaces supplémentaires
                                            
                                            **Solutions :**
                                            1. Cliquez sur **'Reset'** pour effacer l'ancien token
                                            2. Cliquez sur **'Générer le lien d'autorisation'** pour un nouveau lien
                                            3. Suivez le lien **immédiatement** après génération
                                            4. Copiez le code **entier** sans modifications
                                            5. Collez le code et finalisez **rapidement**
                                            
                                            **Note** : Si le problème persiste, vérifiez votre fichier credentials.json et la configuration OAuth dans Google Console.
                                            """)
                            else:
                                st.warning("⚠️ Veuillez entrer le code d'autorisation.")

                    # Test Gmail API connection
                    if st.session_state.gmail_sender and st.session_state.gmail_sender.service:
                        if st.button("🔍 Tester la Connexion Gmail API"):
                            with st.spinner("Test de connexion..."):
                                if st.session_state.gmail_sender.test_connection():
                                    st.success("✅ Connexion Gmail API réussie!")
                                    st.info(f"📧 Email connecté: {st.session_state.gmail_sender.sender_email}")
                                else:
                                    st.error("❌ Échec du test de connexion Gmail API.")

                except json.JSONDecodeError:
                    st.error("❌ Le fichier JSON est invalide.")
                except Exception as e:
                    st.error(f"❌ Erreur lors du chargement du fichier: {str(e)}")

            if not credentials_file:
                st.warning("⚠️ Veuillez uploader le fichier credentials.json pour utiliser Gmail API.")

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("📋 Upload des Contacts")

        uploaded_file = st.file_uploader(
            "Choisissez un fichier CSV, Excel ou TXT",
            type=['csv', 'xlsx', 'xls', 'txt'],
            help="Le fichier doit contenir au minimum une colonne 'email' (CSV/Excel) ou une liste d'emails (TXT)"
        )

        if uploaded_file is not None:
            try:
                df = process_uploaded_file(uploaded_file)

                if validate_csv_columns(df):
                    st.session_state.contacts_df = df
                    st.success(f"✅ {len(df)} contacts chargés avec succès!")

                    # Display preview
                    st.subheader("Aperçu des contacts")
                    st.dataframe(df.head(10), use_container_width=True)

                    # Show column info
                    st.info(f"📊 Colonnes détectées: {', '.join(df.columns.tolist())}")

                else:
                    st.error("❌ Le fichier doit contenir au minimum une colonne 'email'")

            except Exception as e:
                st.error(f"❌ Erreur lors du chargement du fichier: {str(e)}")

    with col2:
        st.header("✉️ Configuration des Emails")

        email_subject = st.text_input(
            "Objet de l'email",
            value="",
            help="Objet qui apparaîtra dans l'email"
        )

        # Email content options
        content_type = st.radio(
            "Type de contenu",
            ["Texte simple", "HTML"],
            help="Format du contenu de l'email"
        )

        if content_type == "Texte simple":
            email_content = st.text_area(
                "Contenu de l'email",
                height=200,
                help="Contenu en texte simple"
            )
        else:
            email_content = st.text_area(
                "Contenu HTML de l'email",
                height=200,
                help="Contenu en format HTML",
                value="""<html>
<body>
    <h2>Bonjour {{nom}},</h2>
    <p>Votre message personnalisé ici.</p>
    <p>Cordialement,<br>{{sender_name}}</p>
</body>
</html>"""
            )

        # Template variables info
        st.info("💡 Vous pouvez utiliser des variables comme {{nom}}, {{email}}, {{entreprise}} selon les colonnes de votre fichier.")

        # Attachments section
        st.subheader("📎 Pièces Jointes (Optionnel)")
        
        uploaded_attachments = st.file_uploader(
            "Ajouter des fichiers en pièce jointe",
            accept_multiple_files=True,
            help="Vous pouvez ajouter plusieurs fichiers qui seront joints à tous les emails"
        )
        
        if uploaded_attachments:
            st.session_state.attachments = []
            total_size = 0
            for uploaded_file in uploaded_attachments:
                file_content = uploaded_file.read()
                file_size = len(file_content)
                total_size += file_size
                st.session_state.attachments.append({
                    'filename': uploaded_file.name,
                    'content': file_content
                })
                uploaded_file.seek(0)
            
            st.success(f"✅ {len(uploaded_attachments)} fichier(s) ajouté(s) ({total_size / 1024:.2f} KB au total)")
            
            with st.expander("📋 Voir les fichiers ajoutés"):
                for att in st.session_state.attachments:
                    st.text(f"• {att['filename']} ({len(att['content']) / 1024:.2f} KB)")
        else:
            st.session_state.attachments = []
        
        # Preview section
        if st.session_state.contacts_df is not None and email_content and email_subject:
            st.subheader("👀 Aperçu de l'email")

            # Select a contact for preview
            preview_index = st.selectbox(
                "Choisir un contact pour l'aperçu",
                range(min(5, len(st.session_state.contacts_df))),
                format_func=lambda x: f"{st.session_state.contacts_df.iloc[x].get('email', 'Email non trouvé')}"
            )

            if st.button("🔍 Générer l'aperçu"):
                contact = st.session_state.contacts_df.iloc[preview_index]

                # Create email sender for preview based on method
                if st.session_state.send_method == "SMTP":
                    preview_sender = EmailSender(
                        smtp_server, smtp_port, use_tls,
                        sender_email, sender_password, sender_name, use_ssl, reply_to_email
                    )
                    preview_subject, preview_content = preview_sender.prepare_email_content(
                        email_subject, email_content, contact
                    )
                else:  # Gmail API
                    if st.session_state.gmail_sender and st.session_state.gmail_sender.service:
                        # Update sender name if it has changed
                        st.session_state.gmail_sender.sender_name = gmail_sender_name
                        preview_subject, preview_content = st.session_state.gmail_sender.prepare_email_content(
                            email_subject, email_content, contact
                        )
                    else:
                        st.error("❌ Veuillez d'abord vous authentifier avec Gmail API.")
                        return

                st.markdown("**Objet:**")
                st.code(preview_subject)

                st.markdown("**Contenu:**")
                if content_type == "HTML":
                    st.markdown(preview_content, unsafe_allow_html=True)
                else:
                    st.text(preview_content)

    st.markdown("---")

    # Sending section
    st.header("🚀 Envoi en Masse")

    col3, col4 = st.columns([2, 1])

    with col3:
        # Check if all required fields are filled based on method
        ready_to_send = False
        if st.session_state.contacts_df is not None and email_content and email_subject:
            if st.session_state.send_method == "SMTP":
                ready_to_send = sender_email and sender_password
            else:  # Gmail API
                ready_to_send = st.session_state.gmail_sender and st.session_state.gmail_sender.service

        if ready_to_send:

            # Sending options
            delay_between_emails = st.slider(
                "Délai entre les emails (secondes)",
                min_value=0.1,
                max_value=10.0,
                value=1.0,
                step=0.1,
                help="Délai pour éviter d'être marqué comme spam"
            )

            if not st.session_state.sending_status['active']:
                if st.button("📤 Lancer l'Envoi en Masse", type="primary"):
                    # Initialize email sender based on method
                    if st.session_state.send_method == "SMTP":
                        st.session_state.email_sender = EmailSender(
                            smtp_server, smtp_port, use_tls,
                            sender_email, sender_password, sender_name, use_ssl, reply_to_email
                        )
                    # Gmail sender is already initialized

                    # Start sending process
                    st.session_state.sending_status = {
                        'active': True,
                        'progress': 0,
                        'total': len(st.session_state.contacts_df),
                        'success': 0,
                        'errors': []
                    }

                    # Process emails one by one with real-time updates
                    progress_bar = st.progress(0)
                    status_placeholder = st.empty()
                    
                    for index, contact in st.session_state.contacts_df.iterrows():
                        if not st.session_state.sending_status['active']:
                            break

                        current_email = contact.get('email', '')
                        status_placeholder.info(f"📧 Envoi vers: {current_email}")

                        try:
                            # Choose sender based on method
                            if st.session_state.send_method == "SMTP":
                                success = st.session_state.email_sender.send_email(
                                    contact.to_dict(), email_subject, email_content, content_type == "HTML",
                                    st.session_state.attachments if st.session_state.attachments else None
                                )
                            else:  # Gmail API
                                # Update sender name before sending
                                if st.session_state.gmail_sender:
                                    st.session_state.gmail_sender.sender_name = gmail_sender_name
                                    success = st.session_state.gmail_sender.send_email(
                                        contact.to_dict(), email_subject, email_content, content_type == "HTML",
                                        st.session_state.attachments if st.session_state.attachments else None
                                    )
                                else:
                                    success = False
                                    st.error("❌ Gmail sender non configuré")

                            if success:
                                st.session_state.sending_status['success'] += 1
                                st.session_state.send_logs.append({
                                    'email': current_email,
                                    'status': 'Succès',
                                    'timestamp': time.strftime('%H:%M:%S'),
                                    'error': ''
                                })
                                status_placeholder.success(f"✅ Envoyé vers: {current_email}")
                            else:
                                st.session_state.sending_status['errors'].append(current_email)
                                st.session_state.send_logs.append({
                                    'email': current_email,
                                    'status': 'Échec',
                                    'timestamp': time.strftime('%H:%M:%S'),
                                    'error': 'Erreur d\'envoi'
                                })
                                status_placeholder.error(f"❌ Échec pour: {current_email}")

                        except Exception as e:
                            st.session_state.sending_status['errors'].append(current_email)
                            st.session_state.send_logs.append({
                                'email': current_email,
                                'status': 'Erreur',
                                'timestamp': time.strftime('%H:%M:%S'),
                                'error': str(e)
                            })
                            status_placeholder.error(f"⚠️ Erreur pour {current_email}: {str(e)}")

                        st.session_state.sending_status['progress'] += 1
                        progress_percentage = st.session_state.sending_status['progress'] / st.session_state.sending_status['total']
                        progress_bar.progress(progress_percentage)
                        
                        time.sleep(delay_between_emails)

                    st.session_state.sending_status['active'] = False
                    status_placeholder.success("🎉 Envoi terminé !")
                    st.balloons()  # Animation de célébration
            else:
                if st.button("⏹️ Arrêter l'Envoi", type="secondary"):
                    st.session_state.sending_status['active'] = False
                    st.rerun()
        else:
            if st.session_state.send_method == "SMTP":
                st.warning("⚠️ Veuillez compléter la configuration SMTP et charger les contacts avant de lancer l'envoi.")
            else:
                st.warning("⚠️ Veuillez vous authentifier avec Gmail API et charger les contacts avant de lancer l'envoi.")

    with col4:
        # Sending status
        if st.session_state.sending_status['progress'] > 0:
            st.subheader("📊 Statut d'Envoi")

            progress = st.session_state.sending_status['progress']
            total = st.session_state.sending_status['total']
            success = st.session_state.sending_status['success']
            errors = len(st.session_state.sending_status['errors'])

            # Progress bar
            progress_percentage = progress / total if total > 0 else 0
            st.progress(progress_percentage)

            # Stats
            st.metric("Progression", f"{progress}/{total}")
            st.metric("Succès", success)
            st.metric("Erreurs", errors)

            if st.session_state.sending_status['active']:
                st.info("🔄 Envoi en cours...")
            else:
                if progress == total:
                    st.success("✅ Envoi terminé!")
                else:
                    st.warning("⚠️ Envoi interrompu")

    # Logs section
    if st.session_state.send_logs:
        st.markdown("---")
        st.header("📋 Historique des Envois")

        # Convert logs to DataFrame
        logs_df = pd.DataFrame(st.session_state.send_logs)

        # Filter options
        col5, col6 = st.columns([1, 3])

        with col5:
            status_filter = st.selectbox(
                "Filtrer par statut",
                ["Tous", "Succès", "Échec", "Erreur"]
            )

        # Apply filter
        if status_filter != "Tous":
            filtered_logs = logs_df[logs_df['status'] == status_filter]
        else:
            filtered_logs = logs_df

        # Display logs
        st.dataframe(
            filtered_logs,
            use_container_width=True,
            column_config={
                'email': 'Email',
                'status': 'Statut',
                'timestamp': 'Heure',
                'error': 'Erreur'
            }
        )

        # Download logs
        csv = filtered_logs.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Télécharger les logs",
            data=csv,
            file_name=f"email_logs_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        # Clear logs button
        if st.button("🗑️ Effacer l'historique"):
            st.session_state.send_logs = []
            st.rerun()

if __name__ == "__main__":
    main()
