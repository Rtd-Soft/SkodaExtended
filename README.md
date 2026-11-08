# Škoda Extended voor Home Assistant

Custom integratie die **alle** gegevens uit de officiële MyŠkoda Public API in Home Assistant zet, ook voor benzine-, diesel- en hybride auto's. Hij draait naast de officiële `skoda`-integratie (eigen domein `skoda_extended`) en gebruikt dezelfde bibliotheek (`skoda-public-api`).

## Wat je krijgt

Alleen entiteiten die jouw auto ondersteunt worden aangemaakt.

| Groep | Entiteiten |
|---|---|
| Rijden | kilometerstand, brandstofniveau, totale actieradius, actieradius brandstof, elektrische actieradius (PHEV), AdBlue-actieradius (diesel), aandrijving |
| Slot & carrosserie | slot, vergrendelstatus (incl. "kofferbak open"), deuren, ramen, kofferbak, motorkap, schuifdak, verlichting |
| Locatie | device tracker (parkeerpositie), parkeeradres, geparkeerd/rijdt |
| Klimaat | status klimaatregeling, doeltemperatuur, klaar-tijdstip, voor-/achterruitverwarming, klimaat bij ontgrendelen |
| Standkachel | status, modus, duur, doeltemperatuur, klaar-tijdstip |
| Ventilatie | status, duur |
| Laden (PHEV/EV) | accu %, laadstatus, laadtype, vermogen, laadsnelheid, resterende tijd, stekker, laadlimiet, laadmodus, max. stroom, op laadlocatie |
| Diagnose | kenteken, laatste update van auto (met `render_url`-attribuut), resterende API-verzoeken, verloopdatum API-sleutel, API-meldingen |

Knoppen (alleen als de auto de opdracht ondersteunt): gegevens verversen, klimaat start/stop, standkachel start (verwarmen of ventileren) / stop, ventilatie start/stop, laden start/stop.

## Installatie

**Marketplace (HA 2026.11+, alleen als de repo publiek is):** Instellingen > Marketplace > *Add from link* > plak de repo-URL > installeer *Škoda Extended* > herstart HA.

**Handmatig (werkt altijd, ook met een privé repo):** kopieer `custom_components/skoda_extended` naar `/config/custom_components/` en herstart HA.

## Instellen

1. MyŠkoda-app > **Profiel > Smart Home** > maak een API-sleutel voor je auto (kopieer hem meteen, je ziet hem maar één keer).
2. HA > Instellingen > Apparaten & diensten > Integratie toevoegen > **Škoda Extended**.
3. Vul VIN en API-sleutel in.

Je kunt dezelfde sleutel gebruiken als voor de officiële integratie, maar beide tellen dan mee voor hetzelfde quotum (zie hieronder). Zet de officiële integratie liever uit.

### Opties
- **Ophaalinterval** (standaard 5 min, minimaal 4).
- **S-PIN**: alleen nodig om de standkachel te starten. Wordt opgeslagen in de HA-configuratie.
- **Standkachel-duur** (10–60 min).

## Limieten

- De API staat **20 verzoeken per uur per auto** toe. Elke ophaalronde, druk op *Gegevens verversen* en elke opdracht kost er één. Na een opdracht wordt na 90 s automatisch ververst (ook één verzoek). Bij 5 minuten interval blijven er 8 per uur over.
- API-sleutels verlopen. De sensor *API-sleutel verloopt* laat zien wanneer; daarna vraagt HA om een nieuwe sleutel (herauthenticatie).
- Gegevens zijn zo vers als de auto ze laatst heeft doorgegeven, zie *Laatste update van auto*.
- Alleen voor persoonlijk gebruik (voorwaarde van Škoda).
