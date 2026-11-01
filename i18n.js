/** ASTRA cockpit UI localisation. Browser locale wins unless the pilot selects a language. */
export const supportedLocales=['en','it','es','fr','de','pt'];
export function browserLocale(languages){
 for(const entry of languages||[]){const lang=String(entry).split('-')[0].toLowerCase();if(supportedLocales.includes(lang))return lang;}
 return 'en';
}
// Columns: original interface caption, Italian, English, Spanish, French, German, Portuguese.
const entries=[
['GIOCA','GIOCA','PLAY','JUGAR','JOUER','SPIELEN','JOGAR'],
['GUIDA ON','GUIDA ON','GUIDE ON','GUÍA SÍ','GUIDE OUI','HILFE AN','GUIA ON'],
['GUIDA OFF','GUIDA OFF','GUIDE OFF','GUÍA NO','GUIDE NON','HILFE AUS','GUIA OFF'],
['GRATIS · OPEN SIM','GRATIS · OPEN SIM','FREE · OPEN SIM','GRATIS · SIM ABIERTA','GRATUIT · SIM OUVERTE','KOSTENLOS · OPEN SIM','GRÁTIS · SIM ABERTA'],
['AVVIA MISSIONE','AVVIA MISSIONE','START MISSION','INICIAR MISIÓN','LANCER LA MISSION','MISSION STARTEN','INICIAR MISSÃO'],
['RIPRENDI MISSIONE','RIPRENDI MISSIONE','RESUME MISSION','REANUDAR MISIÓN','REPRENDRE LA MISSION','MISSION FORTSETZEN','RETOMAR MISSÃO'],
['MISSIONE PRONTA','MISSIONE PRONTA','MISSION READY','MISIÓN LISTA','MISSION PRÊTE','MISSION BEREIT','MISSÃO PRONTA'],
['IN PAUSA','IN PAUSA','PAUSED','EN PAUSA','EN PAUSE','PAUSIERT','EM PAUSA'],
['MISSIONE','MISSIONE','MISSION','MISIÓN','MISSION','MISSION','MISSÃO'],
['VEICOLO','VEICOLO','VEHICLE','VEHÍCULO','VÉHICULE','FAHRZEUG','VEÍCULO'],
['MODELLO DINAMICO','MODELLO DINAMICO','DYNAMICS MODEL','MODELO DINÁMICO','MODÈLE DYNAMIQUE','DYNAMIKMODELL','MODELO DINÂMICO'],
['PROFILO DI VOLO','PROFILO DI VOLO','FLIGHT PROFILE','PERFIL DE VUELO','PROFIL DE VOL','FLUGPROFIL','PERFIL DE VOO'],
['SPAZIO','SPAZIO','SPACE','ESPACIO','ESPACE','RAUMFAHRT','ESPAÇO'],
['AEREO','AEREO','AIRCRAFT','AVIÓN','AVION','FLUGZEUG','AVIÃO'],
['DRONE','DRONE','UAV','DRON','DRONE','DROHNE','DRONE'],
['AIRSPEED','VELOCITÀ ARIA','AIRSPEED','VELOCIDAD AIRE','VITESSE AIR','FLUGGESCHWINDIGKEIT','VELOCIDADE AR'],
['ALTITUDE','QUOTA','ALTITUDE','ALTITUD','ALTITUDE','HÖHE','ALTITUDE'],
['FLIGHT ENVELOPE WARNING','ATTENZIONE INVILUPPO DI VOLO','FLIGHT ENVELOPE WARNING','ALERTA ENVOLVENTE DE VUELO','ALERTE DOMAINE DE VOL','FLUGBEREICH WARNUNG','ALERTA ENVELOPE DE VOO'],
['TRASCINA PER ORBITARE','TRASCINA PER ORBITARE','DRAG TO ORBIT','ARRASTRA PARA ORBITAR','GLISSER POUR ORBITER','ZIEHEN ZUM DREHEN','ARRASTE PARA ORBITAR'],
['SCROLL PER ZOOM','SCROLL PER ZOOM','SCROLL TO ZOOM','RUEDA PARA ZOOM','MOLETTE POUR ZOOMER','SCROLLEN ZUM ZOOMEN','ROLAR PARA ZOOM'],
['DATI','DATI','DATA','DATOS','DONNÉES','DATEN','DADOS'],
['SYSTEM TELEMETRY','TELEMETRIA DI SISTEMA','SYSTEM TELEMETRY','TELEMETRÍA DEL SISTEMA','TÉLÉMÉTRIE SYSTÈME','SYSTEMTELEMETRIE','TELEMETRIA DO SISTEMA'],
['GUIDANCE · NAVIGATION · CONTROL','GUIDA · NAVIGAZIONE · CONTROLLO','GUIDANCE · NAVIGATION · CONTROL','GUIADO · NAVEGACIÓN · CONTROL','GUIDAGE · NAVIGATION · CONTRÔLE','FÜHRUNG · NAVIGATION · REGELUNG','GUIAGEM · NAVEGAÇÃO · CONTROLE'],
['GNC AUTO','GNC AUTO','GNC AUTO','GNC AUTO','GNC AUTO','GNC AUTO','GNC AUTO'],
['MANUAL','MANUALE','MANUAL','MANUAL','MANUEL','MANUELL','MANUAL'],
['CODE API','API CODICE','CODE API','API CÓDIGO','API CODE','CODE API','API CÓDIGO'],
['AUTONOMOUS','AUTONOMO','AUTONOMOUS','AUTÓNOMO','AUTONOME','AUTONOM','AUTÔNOMO'],
['MANUAL OVERRIDE','CONTROLLO MANUALE','MANUAL OVERRIDE','CONTROL MANUAL','CONTRÔLE MANUEL','MANUELLE STEUERUNG','CONTROLE MANUAL'],
['PROPULSIONE','PROPULSIONE','PROPULSION','PROPULSIÓN','PROPULSION','ANTRIEB','PROPULSÃO'],
['ASSETTO','ASSETTO','ATTITUDE','ACTITUD','ATTITUDE','FLUGLAGE','ATITUDE'],
['MANETTA','MANETTA','THROTTLE','ACELERADOR','GAZ','SCHUB','ACELERADOR'],
['IMBARDATA','IMBARDATA','YAW','GUIÑADA','LACET','GIEREN','GUINADA'],
['Regolazioni precise e freni','Regolazioni precise e freni','Fine adjustments and brakes','Ajustes finos y frenos','Réglages fins et freins','Feineinstellung und Bremsen','Ajustes finos e freios'],
['FRENI RUOTE','FRENI RUOTE','WHEEL BRAKES','FRENOS','FREINS','RADBREMSEN','FREIOS'],
['CALCOLA MODELLO','CALCOLA MODELLO','RUN ANALYSIS','CALCULAR MODELO','CALCULER LE MODÈLE','MODELL BERECHNEN','CALCULAR MODELO'],
['ESPORTA JSON','ESPORTA JSON','EXPORT JSON','EXPORTAR JSON','EXPORTER JSON','JSON EXPORTIEREN','EXPORTAR JSON'],
['DISCIPLINA','DISCIPLINA','DISCIPLINE','DISCIPLINA','DISCIPLINE','FACHGEBIET','DISCIPLINA'],
['Scegli un guasto e avvia la missione: ASTRA applica il degrado alla propulsione e registra il residuo nel tempo.','Scegli un guasto e avvia la missione: ASTRA applica il degrado alla propulsione e registra il residuo nel tempo.','Choose a fault and start the mission to study system degradation.','Elige una falla e inicia la misión para estudiar la degradación.','Choisissez une panne et lancez la mission pour étudier la dégradation.','Fehler auswählen und Mission starten, um Degradation zu untersuchen.','Escolha uma falha e inicie a missão para estudar a degradação.'],
['SIMULATION ENVIRONMENT','AMBIENTE DI SIMULAZIONE','SIMULATION ENVIRONMENT','ENTORNO DE SIMULACIÓN','ENVIRONNEMENT DE SIMULATION','SIMULATIONSUMGEBUNG','AMBIENTE DE SIMULAÇÃO'],
['MISSION SIMULATION','SIMULAZIONE DI MISSIONE','MISSION SIMULATION','SIMULACIÓN DE MISIÓN','SIMULATION DE MISSION','MISSIONSSIMULATION','SIMULAÇÃO DE MISSÃO'],
['MISSION CONTROL','CONTROLLO MISSIONE','MISSION CONTROL','CONTROL DE MISIÓN','CONTRÔLE MISSION','MISSIONSKONTROLLE','CONTROLE DA MISSÃO'],
['MISSION ELAPSED','TEMPO MISSIONE','MISSION ELAPSED','TIEMPO DE MISIÓN','TEMPS DE MISSION','MISSIONSZEIT','TEMPO DE MISSÃO'],
['MISSION DATA LAB','LABORATORIO DATI MISSIONE','MISSION DATA LAB','LABORATORIO DE DATOS','LABORATOIRE DE DONNÉES','MISSIONSDATENLABOR','LABORATÓRIO DE DADOS'],
['TRUSTED LIVE TELEMETRY','TELEMETRIA IN DIRETTA','TRUSTED LIVE TELEMETRY','TELEMETRÍA EN VIVO','TÉLÉMÉTRIE EN DIRECT','LIVE-TELEMETRIE','TELEMETRIA AO VIVO'],
['ENGINEERING STUDIO','LABORATORIO INGEGNERISTICO','ENGINEERING STUDIO','ESTUDIO DE INGENIERÍA','STUDIO D’INGÉNIERIE','ENGINEERING STUDIO','ESTÚDIO DE ENGENHARIA'],
['PREPARE TAKEOFF','PREPARA DECOLLO','PREPARE TAKEOFF','PREPARAR DESPEGUE','PRÉPARER DÉCOLLAGE','START VORBEREITEN','PREPARAR DECOLAGEM'],
['TAKE CONTROL','PRENDI IL CONTROLLO','TAKE CONTROL','TOMAR CONTROL','PRENDRE LE CONTRÔLE','STEUERUNG ÜBERNEHMEN','ASSUMIR CONTROLE'],
['PILOT ACTIVE','PILOTA ATTIVO','PILOT ACTIVE','PILOTO ACTIVO','PILOTE ACTIF','PILOT AKTIV','PILOTO ATIVO'],
['FLIGHT CONTROLS','COMANDI DI VOLO','FLIGHT CONTROLS','CONTROLES DE VUELO','COMMANDES DE VOL','FLUGSTEUERUNG','CONTROLES DE VOO'],
['HIDE DATA','NASCONDI DATI','HIDE DATA','OCULTAR DATOS','MASQUER DONNÉES','DATEN AUSBLENDEN','OCULTAR DADOS'],
['SHOW DATA','MOSTRA DATI','SHOW DATA','MOSTRAR DATOS','AFFICHER DONNÉES','DATEN ANZEIGEN','MOSTRAR DADOS'],
['CARICA MODELLO GLB','CARICA MODELLO GLB','LOAD GLB MODEL','CARGAR MODELO GLB','CHARGER MODÈLE GLB','GLB-MODELL LADEN','CARREGAR MODELO GLB'],
['RIMUOVI','RIMUOVI','REMOVE','QUITAR','SUPPRIMER','ENTFERNEN','REMOVER'],
['ESPORTA CSV','ESPORTA CSV','EXPORT CSV','EXPORTAR CSV','EXPORTER CSV','CSV EXPORTIEREN','EXPORTAR CSV'],
['PROVA','PROVA','TRIAL','PRUEBA','ESSAI','VERSUCH','TESTE'],
['REGISTRA OSSERVAZIONE','REGISTRA OSSERVAZIONE','LOG OBSERVATION','REGISTRAR OBSERVACIÓN','NOTER UNE OBSERVATION','BEOBACHTUNG NOTIEREN','REGISTRAR OBSERVAÇÃO'],
['PILOTA','PILOTA','PILOT','PILOTO','PILOTE','PILOT','PILOTO'],
['INGEGNERE','INGEGNERE','ENGINEER','INGENIERO','INGÉNIEUR','INGENIEUR','ENGENHEIRO'],
['SCIENZIATO','SCIENZIATO','SCIENTIST','CIENTÍFICO','SCIENTIFIQUE','WISSENSCHAFTLER','CIENTISTA'],
['Rientro suborbitale','Rientro suborbitale','Suborbital re-entry','Reentrada suborbital','Rentrée suborbitale','Suborbitaler Wiedereintritt','Reentrada suborbital'],
['Circuito di volo','Circuito di volo','Aircraft traffic pattern','Circuito de vuelo','Tour de piste','Platzrunde','Circuito de voo'],
['Missione di ispezione UAV','Missione di ispezione UAV','UAV inspection mission','Misión de inspección UAV','Mission d’inspection UAV','Drohneninspektion','Missão de inspeção UAV'],
['LANCIO · COAST · RIENTRO · RECUPERO','LANCIO · COSTA · RIENTRO · RECUPERO','LAUNCH · COAST · RE-ENTRY · RECOVERY','LANZAMIENTO · INERCIA · REENTRADA · RECUPERACIÓN','LANCEMENT · INERTIE · RENTRÉE · RÉCUPÉRATION','START · FREIFLUG · WIEDEREINTRITT · BERGUNG','LANÇAMENTO · INÉRCIA · REENTRADA · RECUPERAÇÃO'],
['DECOLLO · CIRCUITO · AVVICINAMENTO · ATTERRAGGIO','DECOLLO · CIRCUITO · AVVICINAMENTO · ATTERRAGGIO','TAKEOFF · PATTERN · APPROACH · LANDING','DESPEGUE · CIRCUITO · APROXIMACIÓN · ATERRIZAJE','DÉCOLLAGE · CIRCUIT · APPROCHE · ATTERRISSAGE','START · PLATZRUNDE · ANFLUG · LANDUNG','DECOLAGEM · CIRCUITO · APROXIMAÇÃO · POUSO'],
['DECOLLO VTOL · ISPEZIONE · ATTERRAGGIO','DECOLLO VTOL · ISPEZIONE · ATTERRAGGIO','VTOL TAKEOFF · INSPECTION · LANDING','DESPEGUE VTOL · INSPECCIÓN · ATERRIZAJE','DÉCOLLAGE VTOL · INSPECTION · ATTERRISSAGE','VTOL-START · INSPEKTION · LANDUNG','DECOLAGEM VTOL · INSPEÇÃO · POUSO'],
['LANCIO E RECUPERO','LANCIO E RECUPERO','LAUNCH AND RECOVERY','LANZAMIENTO Y RECUPERACIÓN','LANCEMENT ET RÉCUPÉRATION','START UND BERGUNG','LANÇAMENTO E RECUPERAÇÃO'],
['VOLO CON ATTERRAGGIO','VOLO CON ATTERRAGGIO','FLIGHT AND LANDING','VUELO Y ATERRIZAJE','VOL ET ATTERRISSAGE','FLUG UND LANDUNG','VOO E POUSO'],
['ISPEZIONE CON RIENTRO','ISPEZIONE CON RIENTRO','INSPECTION AND RETURN','INSPECCIÓN Y REGRESO','INSPECTION ET RETOUR','INSPEKTION UND RÜCKKEHR','INSPEÇÃO E RETORNO'],
['LANCIO · VOLO SUBORBITALE','LANCIO · VOLO SUBORBITALE','LAUNCH · SUBORBITAL FLIGHT','LANZAMIENTO · VUELO SUBORBITAL','LANCEMENT · VOL SUBORBITAL','START · SUBORBITALFLUG','LANÇAMENTO · VOO SUBORBITAL'],
['PISTA · MISSIONE AUTOMATICA','PISTA · MISSIONE AUTOMATICA','RUNWAY · AUTONOMOUS MISSION','PISTA · MISIÓN AUTOMÁTICA','PISTE · MISSION AUTONOME','STARTBAHN · AUTOMATISCHE MISSION','PISTA · MISSÃO AUTOMÁTICA'],
['PIAZZOLA · VOLO VTOL','PIAZZOLA · VOLO VTOL','PAD · VTOL FLIGHT','PLATAFORMA · VUELO VTOL','AIRE · VOL VTOL','STARTFLÄCHE · VTOL-FLUG','PLATAFORMA · VOO VTOL'],
['NED · LOCALE','NED · LOCALE','NED · LOCAL','NED · LOCAL','NED · LOCAL','NED · LOKAL','NED · LOCAL'],
['NED · BODY','NED · CORPO','NED · BODY','NED · CUERPO','NED · CORPS','NED · KÖRPER','NED · CORPO'],
['MISSION PHASES','FASI MISSIONE','MISSION PHASES','FASES DE MISIÓN','PHASES DE MISSION','MISSIONSPHASEN','FASES DA MISSÃO'],
['ALTITUDE MSL','QUOTA MSL','ALTITUDE MSL','ALTITUD MSL','ALTITUDE MSL','HÖHE ÜBER MEER','ALTITUDE MSL'],
['ALTITUDE AGL','QUOTA AGL','ALTITUDE AGL','ALTITUD AGL','ALTITUDE AGL','HÖHE ÜBER GRUND','ALTITUDE AGL'],
['GROUND SPEED','VELOCITÀ SUOLO','GROUND SPEED','VELOCIDAD SUELO','VITESSE SOL','GESCHWINDIGKEIT ÜBER GRUND','VELOCIDADE SOLO'],
['TRUE AIRSPEED','VELOCITÀ ARIA VERA','TRUE AIRSPEED','VELOCIDAD AÉREA REAL','VITESSE AIR VRAIE','EIGENGESCHWINDIGKEIT','VELOCIDADE AÉREA VERDADEIRA'],
['FUEL REMAINING','CARBURANTE RESIDUO','FUEL REMAINING','COMBUSTIBLE RESTANTE','CARBURANT RESTANT','RESTKRAFTSTOFF','COMBUSTÍVEL RESTANTE'],
['PROPELLANT','PROPELLENTE','PROPELLANT','PROPELENTE','ERGOLS','TREIBSTOFF','PROPELENTE'],
['BATTERY','BATTERIA','BATTERY','BATERÍA','BATTERIE','BATTERIE','BATERIA'],
['INERTIAL SPEED','VELOCITÀ INERZIALE','INERTIAL SPEED','VELOCIDAD INERCIAL','VITESSE INERTIELLE','INERTIALGESCHWINDIGKEIT','VELOCIDADE INERCIAL'],
['ASTRA FLIGHT DIRECTOR','DIRETTORE DI VOLO ASTRA','ASTRA FLIGHT DIRECTOR','DIRECTOR DE VUELO ASTRA','DIRECTEUR DE VOL ASTRA','ASTRA FLUGDIREKTOR','DIRETOR DE VOO ASTRA'],
['Pilota con due joystick. Inizia con piccoli movimenti: la telemetria scientifica resta visibile qui sopra.','Pilota con due joystick. Inizia con piccoli movimenti: la telemetria scientifica resta visibile qui sopra.','Use two joysticks. Begin with small inputs; live telemetry remains available above.','Pilota con dos joysticks. Empieza con movimientos pequeños; la telemetría está arriba.','Pilotez avec deux joysticks. Commencez par de petits mouvements ; télémétrie au-dessus.','Mit zwei Joysticks steuern. Kleine Bewegungen; Telemetrie bleibt oben sichtbar.','Pilote com dois joysticks. Comece devagar; a telemetria continua acima.'],
['Registra osservazione','Registra osservazione','Log observation','Registrar observación','Noter une observation','Beobachtung notieren','Registrar observação'],
['LEO RENDEZVOUS','LEO RENDEZVOUS','LEO RENDEZVOUS','ENCUENTRO LEO','RENDEZ-VOUS LEO','LEO RENDEZVOUS','ENCONTRO LEO'],
['QUALITÀ ADATTIVA','QUALITÀ ADATTIVA','ADAPTIVE QUALITY','CALIDAD ADAPTATIVA','QUALITÉ ADAPTATIVE','ADAPTIVE QUALITÄT','QUALIDADE ADAPTATIVA'],
['REGOLAZIONI','REGOLAZIONI','ADJUSTMENTS','AJUSTES','RÉGLAGES','EINSTELLUNGEN','AJUSTES'],
['IMPORTA IL TUO VEICOLO 3D · CATEGORIA','IMPORTA IL TUO VEICOLO 3D · CATEGORIA','IMPORT YOUR 3D VEHICLE · TYPE','IMPORTA TU VEHÍCULO 3D · TIPO','IMPORTER VOTRE VÉHICULE 3D · TYPE','3D-FAHRZEUG IMPORTIEREN · TYP','IMPORTE SEU VEÍCULO 3D · TIPO'],
['VEICOLO SPAZIALE','VEICOLO SPAZIALE','SPACECRAFT','NAVE ESPACIAL','VAISSEAU SPATIAL','RAUMFAHRZEUG','NAVE ESPACIAL'],
['VEICOLO CON MOTORE','VEICOLO CON MOTORE','POWERED VEHICLE','VEHÍCULO MOTORIZADO','VÉHICULE MOTORISÉ','MOTORFAHRZEUG','VEÍCULO MOTORIZADO'],
['NESSUNA · SOLO VENTO MEDIO','NESSUNA · SOLO VENTO MEDIO','NONE · MEAN WIND ONLY','NINGUNO · SOLO VIENTO MEDIO','AUCUNE · VENT MOYEN','KEINE · NUR MITTLERER WIND','NENHUMA · SÓ VENTO MÉDIO'],
['SEED RIPRODUCIBILE','SEED RIPRODUCIBILE','REPRODUCIBLE SEED','SEMILLA REPRODUCIBLE','GRAINE REPRODUCTIBLE','REPRODUZIERBARER SEED','SEMENTE REPRODUTÍVEL'],
['MISSIONE · VEICOLO · MODELLO','MISSIONE · VEICOLO · MODELLO','MISSION · VEHICLE · MODEL','MISIÓN · VEHÍCULO · MODELO','MISSION · VÉHICULE · MODÈLE','MISSION · FAHRZEUG · MODELL','MISSÃO · VEÍCULO · MODELO'],
['Orbita bassa terrestre','Orbita bassa terrestre','Low Earth orbit','Órbita terrestre baja','Orbite terrestre basse','Niedrige Erdumlaufbahn','Órbita terrestre baixa'],
['AVVICINAMENTO · RENDEZVOUS · LEO','AVVICINAMENTO · RENDEZVOUS · LEO','APPROACH · RENDEZVOUS · LEO','APROXIMACIÓN · ENCUENTRO · LEO','APPROCHE · RENDEZ-VOUS · LEO','ANFLUG · RENDEZVOUS · LEO','APROXIMAÇÃO · ENCONTRO · LEO'],
['ASTRA CAREER · SFIDE CON FISICA REALE','ASTRA CARRIERA · SFIDE CON FISICA REALE','ASTRA CAREER · REAL-PHYSICS CHALLENGES','CARRERA ASTRA · RETOS FÍSICOS','CARRIÈRE ASTRA · DÉFIS PHYSIQUES','ASTRA KARRIERE · PHYSIK-HERAUSFORDERUNGEN','CARREIRA ASTRA · DESAFIOS FÍSICOS'],
['PROGRESSIONE','PROGRESSIONE','PROGRESSION','PROGRESIÓN','PROGRESSION','FORTSCHRITT','PROGRESSÃO'],
['Cadetto','Cadetto','Cadet','Cadete','Cadet','Kadett','Cadete'],
['Completa la missione e riporta il veicolo a terra in sicurezza.','Completa la missione e riporta il veicolo a terra in sicurezza.','Finish the mission and land the vehicle safely.','Completa la misión y aterriza el vehículo con seguridad.','Terminez la mission et posez le véhicule en sécurité.','Mission abschließen und sicher landen.','Conclua a missão e pouse o veículo com segurança.'],
['PROSSIMO GRADO · PILOTA','PROSSIMO GRADO · PILOTA','NEXT RANK · PILOT','SIGUIENTE RANGO · PILOTO','PROCHAIN GRADE · PILOTE','NÄCHSTER RANG · PILOT','PRÓXIMO NÍVEL · PILOTO'],
['PUNTEGGIO —','PUNTEGGIO —','SCORE —','PUNTUACIÓN —','SCORE —','PUNKTE —','PONTUAÇÃO —'],
['＋ REGISTRA OSSERVAZIONE','＋ REGISTRA OSSERVAZIONE','＋ LOG OBSERVATION','＋ REGISTRAR OBSERVACIÓN','＋ NOTER UNE OBSERVATION','＋ BEOBACHTUNG NOTIEREN','＋ REGISTRAR OBSERVAÇÃO'],
['GUIDANCE','GUIDA','GUIDANCE','GUIADO','GUIDAGE','FÜHRUNG','GUIAGEM'],
['NAVIGATION','NAVIGAZIONE','NAVIGATION','NAVEGACIÓN','NAVIGATION','NAVIGATION','NAVEGAÇÃO'],
['CONTROL','CONTROLLO','CONTROL','CONTROL','CONTRÔLE','REGELUNG','CONTROLE'],
['MISSION MODE','MODALITÀ MISSIONE','MISSION MODE','MODO DE MISIÓN','MODE DE MISSION','MISSIONSMODUS','MODO DE MISSÃO'],
['LEO','LEO','LEO','LEO','LEO','LEO','LEO'],
['AVVIA','AVVIA','START','INICIAR','DÉMARRER','START','INICIAR'],
['Riavvia','Riavvia','Restart','Reiniciar','Redémarrer','Neustart','Reiniciar'],
['Impostazioni','Impostazioni','Settings','Ajustes','Paramètres','Einstellungen','Configurações'],
['Missione','Missione','Mission','Misión','Mission','Mission','Missão'],
['Veicolo','Veicolo','Vehicle','Vehículo','Véhicule','Fahrzeug','Veículo'],
['Esplora il sistema solare','Esplora il sistema solare','Explore Solar System','Explorar el Sistema Solar','Explorer le Système solaire','Sonnensystem erkunden','Explorar o Sistema Solar'],
['Discipline aerospaziali','Discipline aerospaziali','Aerospace disciplines','Disciplinas aeroespaciales','Disciplines aérospatiales','Luft- und Raumfahrtdisziplinen','Disciplinas aeroespaciais']
];
// Shared with the offline Godot mission board by tools/export_mission_i18n.mjs.
export const missionMessages={
 board:['BACHECA MISSIONI','MISSION BOARD'], search:['Cerca missione, luogo o obiettivo…','Search mission, location or objective…'],
 all:['Tutte le missioni','All missions'], story:['Campagne storia','Story campaigns'], contracts:['Contratti','Contracts'],
 daily:['Giornalieri','Daily'], weekly:['Settimanali','Weekly'], favorites:['Preferiti','Favorites'], recent:['Recenti','Recent'],
 difficulty:['Tutte le difficoltà','All difficulties'], duration:['Qualsiasi durata','Any duration'], type:['Tutti i tipi','All types'],
 sort_difficulty:['Difficoltà crescente','Difficulty ascending'], sort_duration:['Durata crescente','Duration ascending'], sort_reward:['Ricompensa decrescente','Reward descending'],
 previous:['← Precedenti','← Previous'], next:['Successive →','Next →'], count:['missioni disponibili','missions available'],
 brief:['BRIEFING','BRIEFING'], objectives:['OBIETTIVI MISURATI','MEASURED OBJECTIVES'], constraints:['VINCOLI DI VOLO','FLIGHT CONSTRAINTS'],
 reward:['RICOMPENSA','REWARD'], credits:['crediti','credits'], reputation:['reputazione','reputation'], science:['scienza','science'],
 requirements:['REQUISITI','REQUIREMENTS'], launch:['AVVIA MISSIONE','START MISSION'], locked:['COMPLETA I REQUISITI','COMPLETE REQUIREMENTS'],
 new:['NUOVA','NEW'], in_progress:['IN CORSO','IN PROGRESS'], completed:['COMPLETATA','COMPLETED'], failed:['NON COMPLETATA','INCOMPLETE'],
 bronze:['BRONZO','BRONZE'], silver:['ARGENTO','SILVER'], gold:['ORO','GOLD'], select:['Seleziona una missione per leggere il briefing.','Select a mission to read its briefing.'],
 favorite:['☆ AGGIUNGI AI PREFERITI','☆ ADD TO FAVORITES'], unfavorite:['★ NEI PREFERITI','★ FAVORITED'],
 empty:['Nessuna missione corrisponde ai filtri.','No missions match these filters.'], loading:['Caricamento…','Loading…'],
 retry:['RIPROVA SUBITO','RETRY NOW'], checkpoint:['SALVA CHECKPOINT','SAVE CHECKPOINT'], restore:['RIPARTI DAL CHECKPOINT','RESTORE CHECKPOINT'],
 saved:['Checkpoint salvato per questa sessione.','Checkpoint saved for this session.'], resume:['RIPRENDI VOLO','RESUME FLIGHT'],
 result:['RISULTATO MISSIONE','MISSION RESULT'], measured:['METRICHE DEL MOTORE','ENGINE METRICS'], next_mission:['MISSIONE SUCCESSIVA','NEXT MISSION'],
 board_action:['TORNA ALLA BACHECA','BACK TO MISSION BOARD'], time:['Tempo simulato','Simulation time'], distance:['Distanza percorsa','Distance flown'],
 resource:['Risorsa residua','Remaining resource'], landing_speed:['Velocità touchdown','Touchdown speed'], elapsed_s:['Tempo simulato','Simulation time'],
 distance_m:['Distanza percorsa','Distance flown'], resource_pct:['Risorsa residua','Remaining resource'], touchdown_speed_m_s:['Velocità touchdown','Touchdown speed'],
 tutorial:['PRIMO VOLO','FIRST FLIGHT'], hint:['SUGGERIMENTO','TIP'], close:['CHIUDI','CLOSE'], language:['Lingua','Language'],
 campaign:['CAMPAGNA','CAMPAIGN'], contract:['CONTRATTO','CONTRACT'], minutes:['min','min'], details:['DETTAGLI','DETAILS'],
 progress:['OBIETTIVI DI VOLO','FLIGHT OBJECTIVES'], career:['CARRIERA','CAREER'], attempts:['tentativi','attempts'],
 controls:['WASD / Q E assetto · Shift/Ctrl spinta · Spazio pausa','WASD / Q E attitude · Shift/Ctrl throttle · Space pause'],
 reset_notice:['Riprovare riavvia il volo; i premi già ottenuti non vengono duplicati.','Retry restarts the flight; previously earned rewards are not duplicated.'],
 max_altitude_m:['Quota massima','Maximum altitude'], max_load_factor_g:['Carico massimo','Maximum load factor'], min_resource_pct:['Riserva minima','Minimum reserve'],
 relative_range_m:['Distanza dal bersaglio','Target distance'], relative_speed_m_s:['Velocità relativa','Relative speed'],
 deadline_s:['Tempo limite · s','Time limit · s'], max_speed_m_s:['Velocità massima · m/s','Maximum speed · m/s'], max_elapsed_s:['Tempo massimo per bonus · s','Bonus time limit · s'],
 bonus:['OBIETTIVI BONUS','BONUS OBJECTIVES'], medal_rules:['Bronzo: obiettivi primari. Argento: almeno un bonus. Oro: tutti i bonus.','Bronze: primary objectives. Silver: at least one bonus. Gold: all bonuses.'],
 CRASHED:['Il veicolo ha subito un impatto.','The vehicle crashed.'], ABORTED:['Volo interrotto.','Flight aborted.'],
 DEADLINE_EXCEEDED:['Tempo limite superato.','Time limit exceeded.'], RESOURCE_RESERVE_EXCEEDED:['Riserva minima esaurita.','Minimum resource reserve exhausted.'],
 SPEED_LIMIT_EXCEEDED:['Limite di velocità superato.','Speed limit exceeded.'], OBJECTIVES_INCOMPLETE_AT_LANDING:['Atterraggio concluso con obiettivi ancora da completare.','Landed with outstanding objectives.'],
 failures:['Voli non completati','Incomplete flights'], flight_seconds:['Tempo di volo totale · s','Total flight time · s'], completed_count:['Missioni completate','Completed missions'],
 mission_requirement:['Completa prima','Complete first'], space_skyward:['SKYWARD · Ascesa suborbitale','SKYWARD · Suborbital ascent'],
 space_pulsar:['PULSAR · Rendezvous in LEO','PULSAR · LEO rendezvous'], space_depot:['WAYFARER · Prossimità orbitale','WAYFARER · Orbital proximity'],
 space_selene:['SELENE · Discesa di precisione','SELENE · Precision descent'], space_shackleton:['SHACKLETON · Campionamento','SHACKLETON · Sampling'],
 space_vesta:['VESTA · Recupero campioni','VESTA · Sample recovery'], air_blue_line:['BLUE LINE · Circuito','BLUE LINE · Circuit'],
 air_alpine:['ALPINE WINDOW · Rotta in quota','ALPINE WINDOW · Altitude route'], air_recovery:['RUNWAY 27 · Rientro','RUNWAY 27 · Recovery'],
 drone_grid:['GRID 04 · Ispezione','GRID 04 · Inspection'], drone_tower:['TOWER ECHO · Rilievo','TOWER ECHO · Survey'], drone_med:['AEROSOL-3 · Campionamento','AEROSOL-3 · Sampling']
};
for(const values of Object.values(missionMessages))entries.push([values[0],...values]);
const columns={it:1,en:2,es:3,fr:4,de:5,pt:6};
const dictionary=new Map(entries.map(row=>[row[0],row]));
function norm(value){return value.replace(/\s+/g,' ').trim();}
function preferredLocale(){
 let selected='auto';try{selected=localStorage.getItem('astra-locale')||'auto'}catch{}
 return selected==='auto'?(typeof navigator!=='undefined'?browserLocale(navigator.languages?.length?navigator.languages:[navigator.language]):'en'):selected;
}
let locale=preferredLocale();
export function translate(source,lang=locale){const row=dictionary.get(norm(source));return row?.[columns[lang]]||source;}
const originals=new WeakMap();
function localizeText(node){
 if(node.nodeType!==3)return;
 const current=node.nodeValue||'';
 if(!current.trim()||current.length>180)return;
 const match=/^(\s*)(.*?)(\s*)$/s.exec(current);
 const middle=norm(match[2]);
 const stored=originals.get(node);
 let source;
 if(stored && current===stored.value) source=stored.source;
 else if(dictionary.has(middle)) source=middle;
 else { originals.delete(node); return; }
 const translated=translate(source,locale);
 const wanted=match[1]+translated+match[3];
 originals.set(node,{source,value:wanted});
 if(current!==wanted)node.nodeValue=wanted;
}
function walk(root){if(!root)return;if(root.nodeType===3){localizeText(root);return;}
 if(root.nodeType!==1 && root.nodeType!==9)return;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 while(walker.nextNode())localizeText(walker.currentNode);
}
if(typeof document!=='undefined'){
const selector=document.querySelector('#astraLocale');
if(selector){try{selector.value=(localStorage.getItem('astra-locale')||'auto')}catch{selector.value='auto'};selector.addEventListener('change',()=>{
 try{localStorage.setItem('astra-locale',selector.value)}catch{};locale=selector.value==='auto'?(typeof navigator!=='undefined'?browserLocale(navigator.languages?.length?navigator.languages:[navigator.language]):'en'):selector.value;document.documentElement.lang=locale;
 walk(document.body);
});}
document.documentElement.lang=locale;
walk(document.body);
// Dynamic labels (play/pause, mission changes) may be rewritten by the simulation.
// Translate only matching captions; numeric telemetry is left untouched.
new MutationObserver(mutations=>{for(const m of mutations){if(m.type==='characterData')localizeText(m.target);else for(const item of m.addedNodes)walk(item);}}).observe(document.body,{subtree:true,childList:true,characterData:true});

}
