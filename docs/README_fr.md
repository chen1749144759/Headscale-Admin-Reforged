# Documentation ScaleForge

Cette ancienne traduction a été retirée pour des raisons de sécurité. Son ancien parcours d'enregistrement et ses commandes client ne correspondent plus à l'architecture actuelle fondée sur un compte et un mot de passe.

La documentation de référence se trouve dans le [README principal](../README.md). Elle décrit l'architecture, la connexion, les sockets Unix privés, CAPTCHA, DNS, les mises à jour OTA signées, les migrations et les mises à niveau.

Les nouveaux clients utilisent `scaletail login --username ...`. L'automatisation doit utiliser `--password-file` avec un fichier protégé en `0600`.
