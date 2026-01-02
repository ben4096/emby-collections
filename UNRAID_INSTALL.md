# Installation sur Unraid

Ce guide explique comment installer et configurer Emby Collections Sync sur Unraid en utilisant un User Script.

## Prérequis

1. **Python 3** doit être installé sur Unraid
   - Allez dans **Settings** → **Plugins** → cherchez "Python"
   - Ou installez via **NerdTools** ou **Community Applications**
   - Vérifiez l'installation avec `python3 --version`

2. **User Scripts Plugin**
   - Installez depuis Community Applications si pas déjà fait
   - Cherchez "User Scripts" par Andrew Zawadzki

3. **Git** (généralement déjà installé sur Unraid)

## Installation

### Méthode 1 : Installation automatique avec le script

1. **Créez un nouveau User Script**
   - Allez dans **Settings** → **User Scripts**
   - Cliquez sur **Add New Script**
   - Nommez-le `emby-collections`

2. **Copiez le script**
   - Éditez le script que vous venez de créer
   - Copiez le contenu de `unraid_user_script.sh` dans l'éditeur
   - **IMPORTANT** : Modifiez les variables en haut du script :
     ```bash
     INSTALL_DIR="/mnt/user/appdata/emby-collections"  # Chemin d'installation
     REPO_URL="https://github.com/VOTRE_USERNAME/emby-collections.git"  # Votre repo
     ```

3. **Sauvegardez et rendez le script exécutable**
   - Cliquez sur **Save**
   - Le script est automatiquement exécutable

4. **Première exécution**
   - Cliquez sur **Run Script**
   - Le script va :
     - Cloner le repository
     - Créer un environnement virtuel Python
     - Installer les dépendances
     - Créer un fichier `config.yaml` à partir de l'exemple

5. **Configurez votre fichier config**
   - Éditez `/mnt/user/appdata/emby-collections/config.yaml`
   - Ajoutez vos clés API Emby, MDBList, Trakt
   - Configurez vos collections

6. **Lancez à nouveau le script**
   - Retournez dans User Scripts
   - Cliquez sur **Run Script** pour lancer le premier sync

### Méthode 2 : Installation manuelle

```bash
# Connectez-vous en SSH à Unraid

# Créez le répertoire d'installation
mkdir -p /mnt/user/appdata/emby-collections
cd /mnt/user/appdata/emby-collections

# Clonez le repository
git clone https://github.com/VOTRE_USERNAME/emby-collections.git .

# Créez l'environnement virtuel
python3 -m venv venv

# Activez l'environnement virtuel
source venv/bin/activate

# Installez les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# Créez votre config (exemple fonctionnel ou template vierge)
cp config.yaml.example config.yaml  # Exemple fonctionnel recommandé
# OU: cp config.yaml.template config.yaml  # Template vierge
nano config.yaml  # Éditez avec vos paramètres

# Test manuel
python emby_collections.py --once

# Désactivez l'environnement
deactivate
```

## Configuration du planning

Une fois que tout fonctionne :

1. Allez dans **Settings** → **User Scripts**
2. Trouvez votre script `emby-collections`
3. Cliquez sur **Schedule Disabled**
4. Choisissez une fréquence :
   - **Daily** : Chaque jour à une heure précise (recommandé)
   - **Hourly** : Toutes les heures
   - **Custom** : Cron personnalisé

### Exemple de cron personnalisé

Pour exécuter tous les jours à 2h du matin :
```
0 2 * * *
```

Pour exécuter toutes les 6 heures :
```
0 */6 * * *
```

## Structure des fichiers

Après installation, voici la structure dans `/mnt/user/appdata/emby-collections/` :

```
emby-collections/
├── venv/                      # Environnement virtuel Python (créé automatiquement)
├── src/                       # Code source
├── emby_collections.py        # Script principal
├── config.yaml               # Votre configuration
├── requirements.txt          # Dépendances Python
└── emby_collections.log      # Fichier de logs
```

## Vérification des logs

Pour voir les logs de votre dernière exécution :

```bash
tail -f /mnt/user/appdata/emby-collections/emby_collections.log
```

Ou depuis User Scripts, cliquez sur le bouton de logs de votre script.

## Mise à jour

Le script se met à jour automatiquement à chaque exécution via `git pull`.

Pour forcer une mise à jour :
```bash
cd /mnt/user/appdata/emby-collections
git pull
source venv/bin/activate
pip install -r requirements.txt --upgrade
deactivate
```

## Dépannage

### Python 3 non trouvé
```bash
# Vérifiez où est Python 3
which python3

# Si différent de /usr/bin/python3, modifiez PYTHON_BIN dans le script
```

### Erreur de module venv
```bash
# Python 3 minimal, installez le package complet depuis NerdTools
```

### Permission denied
```bash
# Rendez le script exécutable
chmod +x /boot/config/plugins/user.scripts/scripts/emby-collections/script
```

### Erreur de connexion à Emby
- Vérifiez l'URL Emby dans `config.yaml`
- Vérifiez que la clé API est correcte
- Assurez-vous qu'Emby est accessible depuis Unraid

## Test manuel

Pour tester manuellement sans User Scripts :

```bash
cd /mnt/user/appdata/emby-collections
source venv/bin/activate
python emby_collections.py --once --dry-run
deactivate
```

L'option `--dry-run` permet de tester sans modifier Emby.

## Désinstallation

```bash
# Supprimez le User Script depuis l'interface web
# Puis supprimez les fichiers
rm -rf /mnt/user/appdata/emby-collections
```
