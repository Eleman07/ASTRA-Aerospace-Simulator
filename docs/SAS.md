# SAS orbitale

Il pulsante **SAS ON/OFF** è sempre visibile e attivabile in SIMULATORE e GIOCA.
**T** attiva il mantenimento dell'assetto corrente; **Z/X** scorrono i preset
validi. L'anello offre Stability Assist, Prograde, Retrograde, Normal,
Anti-Normal, Radial In/Out, Target/Anti-Target e Maneuver Node.
Target richiede un bersaglio distinto; Maneuver richiede `maneuver_direction_eci`.
Le icone ASTRA sono disegnate proceduralmente e indicano vettori reali nel
riferimento corpo: +X davanti, +Y a destra, −Z in alto. I marker posteriori
sono attenuati sul bordo. Non vengono copiati asset o icone di altri giochi.

Nel controller manager si possono assegnare **SAS** e **prossimo preset**:
i valori predefiniti Xbox sono RB e pressione dello stick destro. Occorre
armare il controller; le assegnazioni riservate a menu, freni, GNC e pausa
sono rifiutate. I vecchi profili acquisiscono automaticamente questi default.
I campi di testo continuano ad assorbire i tasti durante la scrittura.

WASDQE e gli stick sovrascrivono temporaneamente tutti i preset con coppia
manuale. Al rilascio Stability Assist acquisisce l'assetto raggiunto; gli altri
preset riprendono l'inseguimento del vettore. Il ritorno GNC usa il precedente
controllore LVLH. G/X gamepad mantiene il comportamento preesistente di pausa
sicura in volo libero e ritorno al GNC nelle missioni tecniche.

```python
from astra_sdk import AstraClient
client = AstraClient()
client.free_flight('space', 'orbital', advanced_models=True)
client.sas_enable()                         # hold inerziale corrente
client.sas_mode('retrograde')
print(client.state()['sas'])                # modalità, marker, autorità, limiti
print(client.status()['sas'])
client.sas_mode('maneuver_node', maneuver_direction_eci=[1, 1, 0])
client.sas_enable(False)
client.orbital_attitude('prograde')          # API precedente conservata
```

Il controllore integra il quaternione e le velocità angolari con coppia e
momento angolare limitati dalle ruote di reazione del modello Python. Una
rotazione di 180° richiede tempo fisico. Queste ruote non consumano carburante
RCS: la telemetria lo dichiara, senza inventare un attuatore a propellente.
Su lanciatore, aereo, UAV e lander è disponibile Stability Assist: mantiene i riferimenti locali di assetto tramite i controllori fisici esistenti. Gli input manuali aggiornano il riferimento mantenuto al rilascio. Non è un controllo automatico di quota, posizione o manetta. I preset direzionali sono orbitali.

Verifica: `python -m unittest tools.test_orbital_sas` e
`python tools/test_input_routing.py`. Le prove di GUI iniettano eventi reali
Godot; non equivalgono a una prova fisica di Xbox/HOTAS collegato.
