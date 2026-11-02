# Thrustmaster T.Flight HOTAS X — ASTRA2.5.3

1. Prima del collegamento scegliere **PC** sull'interruttore hardware. Il manuale
raccomanda di collegare con manetta, stick e timone centrati e senza muoverli.
Usare il preset hardware automatico (PRESET spento). HOME rosso indica4assi,
verde5assi: nel secondo il bilanciere è indipendente dalla torsione.
Fonte: [manuale ufficiale](https://ts.thrustmaster.com/download/accessories/Manuals/TFHX/T-Flight_Hotas_X_Manual.pdf).
2. In CONTROLLER selezionare il HOTAS come **Primario**. Il nome T.Flight è
riconosciuto e abilita il profilo dedicato; il pulsante **PROFILO T.FLIGHT HOTAS X · PC**
consente di sceglierlo esplicitamente. Stick e manetta condividono il dispositivo:
non assegnarlo anche come Manetta separata.
3. Assi iniziali ASTRA (indici da0): roll0, pitch1, manetta2, timone3.
Sono modificabili: un driver o un preset hardware personalizzato può cambiarli.
**RILEVA** accanto a ciascun asse: muovere solo quell'asse; poi **SALVA PROFILO**.
Monitor assi grezzi e pulsanti premuti permette di verificare l'ordine sul proprio PC.
4. Calibrare centro a stick e torsione rilasciati, poi escursione muovendoli ai limiti.
La manetta resta assoluta0–100%; **Inverti manetta assoluta** corregge il verso.
Armare con stick centrato. Per acquisire la manetta portarla al valore di spinta
corrente: niente scatto al momento dell'armamento.

## Pulsanti del profilo

Indici software da0; con numerazione hardware standard il pulsante1 è indice0.
SAS0; prossimo preset1; freni2; pausa7; GNC/pausa sicura8; arma/disarma9.
Ogni assegnazione è modificabile nel pannello e salvata per categoria di veicolo.
Gli stessi pulsanti non attivano contemporaneamente le azioni Xbox dei menu,
anche nei pannelli secondari. Per i menu usare mouse e tastiera.
T/Z/X restano attivi per SAS; le modalità vengono saltate se non valide.

## Verifica e limiti

Test Godot con eventi simulati: endpoint/inversione manetta, pickup senza salti,
assi/profili/assegnazioni, triggerSAS e prossimo preset, pausa/GNC, assenza di
attivazioni Xbox involontarie nei menu principali e secondari; regressioni Xbox.
Nessun HOTAS fisico era collegato all'ambiente di build: non viene dichiarato un
test hardware completo. Se gli assi del driver differiscono, usare RILEVA e il
monitor invece di cambiare la calibrazione fisica o supporre un ordine fisso.
