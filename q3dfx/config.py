"""Configurazione di distribuzione.

GITHUB_REPO e' il repository da cui l'app scarica QEMU-3dfx gia' compilato
(release con tag che inizia per "qemu3dfx-"). Sostituisci il valore con il
tuo "utente/repository" prima di creare gli installer: e' l'unica modifica
necessaria. Chi usa l'app puo' comunque cambiarlo nelle Impostazioni.
"""

GITHUB_REPO = "Lugubre21/qemu3dfx-manager"

# Prefisso dei tag delle release che contengono QEMU-3dfx compilato.
QEMU_RELEASE_PREFIX = "qemu3dfx-"
