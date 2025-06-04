#!/usr/bin/env python3

# Test simple pour vérifier les settings
import sys
import os

# Ajouter le répertoire backend au path
sys.path.insert(0, '/workspace/vigileos/backend')

try:
    # Import direct du module settings
    import vigileos.settings as settings
    print("Import réussi")
    
    # Vérifier DATABASES
    if hasattr(settings, 'DATABASES'):
        print("DATABASES trouvé:", settings.DATABASES)
    else:
        print("DATABASES non trouvé")
        
    # Lister tous les attributs qui contiennent 'DATA'
    attrs = [attr for attr in dir(settings) if 'DATA' in attr.upper()]
    print("Attributs contenant DATA:", attrs)
    
except Exception as e:
    print("Erreur lors de l'import:", e)
    import traceback
    traceback.print_exc()