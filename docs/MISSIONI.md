# Missioni GIOCA

Il catalogo tecnico SIMULATORE conserva i suoi scenari. GIOCA aggiunge 18 template
in `astra/data/mission_templates.json`, sei per disciplina, con 64 seed ciascuno.
Il validatore conta 377 configurazioni distinte Spazio, 383 Aereo e 384 Drone;
384 voci per disciplina. Le 12 missioni storia conservano ID e progressione.

## Template e generazione

`generate_mission(template_id, seed, language)` usa SHA-256 e RNG locale, versione1.
Campi dati: id, vehicle, scenario, family, title/briefing IT/EN, parameters con
min/max/step o choices, setup, objectives, constraints, bonus, events, duration_s.
I riferimenti `$nome` sostituiscono parametri. Gli ID sono `proc1:template:seed`.
Setup modifica davvero orbita, stato iniziale lunare, vento o rotta N/E. Difficoltà
1–5 cambia precisione, tratte, finestre di quota e limiti, oltre allo sblocco.
Eventi di degrado propulsivo usano il modello guasti reale e sono registrati.
I settori sono locali sintetici: nessuna nuova cartografia o geografia implicita.

Le famiglie coprono ascesa/recupero suborbitale, prossimità orbitale, discesa e
campionamento lunare; circuito/rotta/vento/recupero aereo; ispezione, mappatura,
campionamento e consegna UAV con waypoint. SSO/GTO, contatto docking, rifornimento,
rimozione detriti e trasferimento del carico non sono meccaniche implementate.

## Obiettivi e ricompense

Evaluator: altitude, distance, hold_altitude continuo, safe_landing, rendezvous,
relative_waypoint, waypoint, route e fault_detected. La rotta manuale è misurata
da posizione e velocità effettive, indipendentemente dal GNC. Limiti di tempo,
riserva e velocità generano un risultato fallito misurato dal clock Python.

Crediti base: Spazio2400, Aereo1100, Drone650. Moltiplicatore:
`(1 + 0.28*(difficoltà-1)) * (0.75 + 0.5*sqrt(durata_s/300)) * (1 + 0.12*modificatori)`.
Crediti arrotondati a10; reputazione `2+2*difficoltà+modificatori`;
scienza `(3 Drone, 2 altri)+difficoltà+modificatori`.
Bronzo completa i primari, Argento almeno un bonus, Oro tutti i bonus.
Premi 1/1.1/1.2; ripetizioni pagano solo il miglioramento rispetto al record.

## Carriera e UX

Bacheca paginata con ricerca, filtri difficoltà/durata/famiglia, ordinamento,
preferiti e recenti. Daily/weekly derivano dalla data locale senza rete.
Briefing e HUD mostrano gli obiettivi, mappa N/E dei waypoint UAV, checkpoint,
retry, risultato con metriche, medaglie e missione successiva. Tutorial iniziale
per disciplina e suggerimenti dopo fallimenti ripetuti. Dizionario IT/EN nativo
esportato da `i18n.js` con `node tools/export_mission_i18n.mjs`.

Salvataggi carriera JSON compatibili aggiungono ID/template/seed e stato misurato,
mai briefing o obiettivi generati. I checkpoint copiano il vero stato del motore
in memoria e funzionano nella sessione corrente; riaprire l'app richiede retry,
non è implementato il ripristino fisico persistente tra processi.

## Verifiche riproducibili

`python tools/validate_missions.py --seeds 100`: 1800 configurazioni, zero invalide.
Il conteggio distinto esclude ID, seed, testo, premi e parametri non usati.
`python tools/mission_reference_flights.py --seeds 0,1,2,3,49 --workers 3`
integra voli reali per ciascuna famiglia; evidenze in `docs/validation/`.
`python -m unittest tools.test_gameplay tools.test_mission_flights`.
`python tools/verify_mission_ui.py --publish` cattura la UI Godot usando risposte
runtime registrate e un risultato ottenuto da una vera discesa lunare.

I controlli di inviluppo sono screening conservativi delle risorse, distinti dai
voli campionati: non dimostrano che ogni seed possibile sia risolvibile. Le
superfici di atterraggio locali e i modelli educativi conservano i propri limiti.
