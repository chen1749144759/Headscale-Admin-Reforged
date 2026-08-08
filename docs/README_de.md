# ScaleForge Dokumentation

Diese historische Übersetzung wurde aus Sicherheitsgründen zurückgezogen. Die frühere Registrierung und die alten Client-Befehle entsprechen nicht mehr der aktuellen Konto- und Passwortarchitektur.

Die verbindliche Dokumentation befindet sich in der [README im Projektstamm](../README.md). Dort sind Architektur, Anmeldung, private Unix-Sockets, CAPTCHA, DNS, signierte OTA-Updates, Datenbankmigration und Upgrade-Schritte beschrieben.

Neue Clients melden sich mit `scaletail login --username ...` an. Für Automatisierung ist ausschließlich `--password-file` mit Dateirechten `0600` vorgesehen.
