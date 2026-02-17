# Code Review: CarboxySim - Wetenschappelijke Berekeningen en Aannames

**Datum:** 2026-02-16  
**Focus:** Wetenschappelijke correctheid van gas-vloeistof transfer model  
**Status:** Review bijgewerkt op basis van actuele code

---

## 1. Overzicht

CarboxySim implementeert een single-pass tubing model voor O2/N2 overdracht in PBS, met twee transfermodi:

- `kLa` mode: directe eerste-orde overdrachtscoefficienten (`kLa_o2_s_inv`, `kLa_n2_s_inv`)
- `permeability` mode: effectieve overdracht afgeleid uit slanggeometrie en permeabiliteit

Kernbouwstenen:

- Henry-evenwicht: `C* = S(T) * p`
- Residence time: `tau = V_tube / Q`
- Outletformule: `C_out = C* + (C_in - C*) * exp(-k_eff * tau)`
- Startup-delay in de tijdreeksen: voor `t < tau` blijft uitgang op `C_in`

---

## 2. Wat Is Wetenschappelijk Correct

### 2.1 Henry-wet implementatie

`compute_equilibrium_concentrations(...)` gebruikt correct:

- `p_i = y_i * P_total`
- `C_i* = S_i(T) * p_i`

Eenheden zijn consistent:

- `S` in `mmol/(L*kPa)`
- `p` in `kPa`
- resultaat `C*` in `mmol/L`

### 2.2 Buisvolume en verblijftijd

`compute_tube_volume_ml(...)` en `compute_residence_time_s(...)` zijn correct:

- `V = pi * r^2 * L`
- `tau = (V/Q) * 60`

Voor ID 3.2 mm en lengte 160 cm geeft dit ongeveer 12.868 mL, wat klopt.

### 2.3 Outletvergelijking

`compute_single_pass_outlet_concentration(...)` volgt de analytische eerste-orde oplossing:

- bij `k=0`: `C_out = C_in`
- bij groot `k*tau`: `C_out -> C*`
- met correcte richting voor opname en desorptie

### 2.4 Permeability mode

`compute_effective_kla_from_permeability(...)` zet permeabiliteit om naar een effectieve eerste-orde transferterm op basis van:

- wanddikte
- oppervlak/volume verhouding
- oplosbaarheid

Validaties in `validate_inputs(...)` forceren terecht:

- `tube_od_mm > tube_id_mm`
- aanwezigheid permeabiliteitsvelden in permeability mode

---

## 3. Belangrijkste Aannames En Beperkingen

1. **Constante temperatuur in solubility model**  
   `temperature_c` wordt nog niet gebruikt in de huidige `constant_solubility_model`.

2. **Ideale plug-flow front**  
   De tijdrespons is een stap na `tau` (geen axiale dispersie, geen sensorlag).

3. **Geen gasfase-dynamiek of terugkoppeling**  
   Gascompositie en druk worden als constant beschouwd.

4. **Geen reactiekinetiek in PBS**  
   Alleen fysische transfer van O2/N2.

Deze aannames zijn voor MVP acceptabel, maar moeten zichtbaar blijven voor gebruikers.

---

## 4. Bevindingen Met Prioriteit

## Hoog

1. **Temperatuurafhankelijkheid nog niet fysisch actief**  
   Impact: gebruikers kunnen denken dat temperatuur al volledig meeloopt.  
   Actie: ofwel T-afhankelijke solubility toevoegen, of expliciete UI-waarschuwing.

2. **Staprespons kan als "bug" worden gezien**  
   Impact: mismatch met gemeten sensorcurves die vaak geleidelijk verlopen.  
   Actie: optionele sensorlag/dispersion module toevoegen.

## Midden

3. **Permeabiliteitseenheden zijn gevoelig voor invoerfouten**  
   Positief: unitkeuze (`Barrer` vs SI-achtige eenheid) is al toegevoegd.  
   Actie: voeg referentieranges per materiaal toe in tooltip/documentatie.

4. **`volume_l` wordt vooral als context gebruikt in single-pass model**  
   Actie: expliciet labelen als metadata/context, of recirculatiemode later toevoegen.

## Laag

5. **Modelscope en validiteitsbereik kunnen scherper**  
   Actie: formeel bereik opnemen in docs, bv. aanbevolen ID-range en flowrange.

---

## 5. Testbaarheid En Dekking

Actuele tests dekken:

- parameter validatie (incl. permeability mode checks)
- geometrie en residence-time gedrag
- `kLa=0` randgeval
- flow-effect
- determinisme
- exportintegriteit

Status bij laatste run: alle tests groen.

---

## 6. Concrete Verbeteringen Die Nu Zinvol Zijn

1. Voeg in UI een expliciete waarschuwing toe:
- "Temperature input is currently not coupled to solubility constants."

2. Voeg optionele dynamiek toe op meetsignaal:
- first-order sensorlag (`tau_sensor`) op DO% output.

3. Voeg materiaal presets toe in permeability mode:
- bv. silicone preset met voorbeeldbereiken voor O2/N2 permeability.

4. Voeg in docs een "validity envelope" toe:
- aanbevolen ID, flow en temperatuurrange voor gebruik van dit model.

---

## 7. Conclusie

**Wetenschappelijke kwaliteit (MVP): goed.**

De kernvergelijkingen en eenheden zijn correct en de implementatie sluit logisch aan bij het gekozen single-pass concept. De grootste resterende risico's zitten niet in algebra, maar in modelaannames (temperatuurconstanten, ideale staprespons) en interpretatie door eindgebruikers.

**Release-oordeel:** geschikt voor onderzoeks-MVP, mits aannames duidelijk zichtbaar blijven en de genoemde hoge prioriteiten worden opgepakt.

---

**Beoordelaar:** bijgewerkt door Codex  
**Datum review-update:** 2026-02-16
