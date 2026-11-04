# T.Flight HOTAS One — PC

Prima di collegare il cavo USB scegliere **PC** sul selettore della base.
Installare il driver PC ufficiale Thrustmaster e controllare il dispositivo nel
pannello del produttore. Non è lo stesso modello del HOTAS X.
[Manuale ufficiale](https://ts.thrustmaster.com/download/accessories/Manuals/TFHOne/T-Flight_HO_Manual.pdf)
[Driver e supporto](https://support.thrustmaster.com/en/product/t-flight-hotas-one-en/)

In ASTRA: CONTROLLER → Primario → T.Flight Hotas One. Il nome è riconosciuto e
carica il profilo One, anche se prima era selezionato HOTAS X. È disponibile anche
**PROFILO T.FLIGHT HOTAS ONE · PC** per sceglierlo esplicitamente.
Stick e manetta usano un unico dispositivo Primario; non duplicarlo nella manetta
separata. Calibrare centro con stick e torsione rilasciati, poi l'escursione.
Salvare il profilo e armare. La manetta assoluta acquisisce la spinta corrente
solo quando la leva raggiunge quel valore, evitando salti all'armamento.

## Assi e pulsanti ASTRA

Indici iniziali da0: roll0, pitch1, manetta2, torsione3. Il driver può enumerare gli
assi diversamente: controllare il monitor grezzo (assi0–7) e usare **RILEVA**,
muovendo un solo asse, poi **SALVA PROFILO**. Inverti pitch/manetta correggono il verso.
Le assegnazioni iniziali ASTRA, tutte modificabili, sono: SAS0, prossimo SAS1,
freni2, arma/disarma4, GNC/pausa sicura7, pausa8. Gli indici software non sono
promessi come equivalenti alle etichette Xbox: premere il pulsante e leggere il
numero nel monitor, quindi assegnarlo al comando desiderato.
I pulsanti HOTAS non attivano simultaneamente i menu Xbox. Menu con mouse/tastiera.

Il pulsante GUIDE hardware cambia modalità4/6assi (LED acceso, timone combinato)
e5/8assi (LED spento, assi indipendenti) secondo il manuale ufficiale; non viene
usato come comando ASTRA. In modalità indipendente bilanciere e pedali RJ12 sono
assi del Primario: assegnare quello desiderato come yaw con RILEVA. Non viene
aggiunta una simulazione dei freni differenziali.

Le impostazioni One sono salvate per categoria nel gruppo `categoria/hotas_one`
separato dal profilo Xbox/HOTAS X. I dati e le calibrazioni esistenti sono conservati.

## Verifiche

Test Godot di riconoscimento modello, salvataggi separati/ripristino,
assi calibrati, pitch, manetta assoluta con inversione e pickup, input pulsanti
SAS/pausa/GNC senza azioni menu, regressioni HOTAS X e Xbox.
Nessun HOTAS One fisico disponibile nella macchina di build: le verifiche software
non sostituiscono la prova del dispositivo/driver. RILEVA e monitor consentono di
adattare le assegnazioni del proprio PC.
