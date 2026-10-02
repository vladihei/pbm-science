# Kuukausipäivitys: Ongoing studies

Käytä tätä ohjetta kuun ensimmäisenä päivänä. Tavoite on päivittää tutkimuslista alkuperäisrekistereistä ja samalla mitata, kuinka lähelle laajaa kansainvälistä hakua päästään. Älä käsittele aiempaa ICTRP-pohjaista 489 tietueen otosta julkaistavana aineistona.

## Aloitusviesti uudessa keskustelussa

> Päivitä pbm.science-sivuston Ongoing studies -aineisto tiedoston `data/direct-sources/MONTHLY-UPDATE.md` mukaan. Hae ClinicalTrials.govista suoraan API:lla, tarkista ReBEC, ChiCTR, CTRI, IRCT ja muut `registry-coverage.csv`-listan rekisterit niiden omista lähteistä, päivitä statukset ja vertaa kattavuutta viime kuuhun. Käytä WHO ICTRP:tä vain puuttuvien rekisteritunnisteiden löytämiseen ja kattavuuden vertailuun; älä kopioi sen tietueita julkaistavaan aineistoon. Tee itse kaikki onnistuvat haut ja käsittely. Pyydä minulta vain täsmällinen selaintoimi tai tiedosto, jota et pysty tekemään, ja anna siihen suora linkki. Julkaise vain ne lähteet, joiden käyttöehdot on tarkistettu ja joista 50 tietueen lähdekohtainen laatutarkistus on tehty.

Lue ensin tämä ohje, `search-strategy.json`, `snapshot-metadata.json`, `registry-coverage.csv`, edellinen julkinen salattu snapshot jos sellainen on sekä nykyinen sivu- ja prosessorikoodi.

## Kuukausittainen keruu

1. Kirjaa paikallinen hakupäivä, lähde, täsmällinen hakulauseke, rajapinta tai lataustapa, tulosmäärä sekä käyttöehtojen tila.
2. Hae ClinicalTrials.govista suoralla API v2 -haulla komennolla `python scripts/fetch_clinicaltrials_gov.py --retrieved-on YYYY-MM-DD`. Haku kerää kaikki statukset ja kaikki sivut. Vertaa raakarivien määrää, yksilöllisten NCT-tunnisteiden määrää sekä aiemman kuun aineistoa. Älä julkaise API:n raakavastauksia.
3. Hae ReBEC, ChiCTR, CTRI, IRCT ja muut kattavuuslistan lähteet kunkin omalla hakusivulla tai dokumentoidulla rajapinnalla. Jos haku tai vienti epäonnistuu, tallenna tarkka virhe ja pyydä minulta vain yksi konkreettinen toimi: tarkka URL, hakutermi, painike ja haluttu CSV/XLSX/XML. Älä merkitse rekisteriä haetuksi, jos siitä on vain hakukoneosuma tai ICTRP-tietue.
4. Tallenna lähdekohtainen raakavienti sellaisenaan `data/direct-sources/raw/`-hakemistoon. Se on pois Gitistä, koska raakavienneissä voi olla yhteystietoja. Yksittäistietueiden lataukset nimeä tunnisteen ja hakupäivän mukaan.
5. Päivitä aiempien ehdokkaiden statukset alkuperäisrekisteristä. Tallenna sellaisenaan lähteen status ja viimeisin päivityspäivä. Älä päättele “Recruitment completed” -tilasta että tutkimus on valmis, tai “Not recruiting” -tilasta että se on päättynyt. Jos rekrytoinnin ilmoitettu loppupäivä on jo ohitettu tai status on muuten ristiriidassa aikataulun kanssa, aseta tietue tarkistukseen.
6. Erota rekisteritietueet tutkimuksista. Yhdistä automaattisesti vain saman rekisterin täsmällinen ID tai rekisterin dokumentoima ristiviittaus. Samankaltainen nimi on vain mahdollinen duplikaatti.
7. Päivitä `registry-coverage.csv`: jokaiselle rekisterille hakupäivä, queryt, API-/vientitoimivuus, osumat, käyttöehtojen tarkistus ja seuraava konkreettinen askel. ICTRP:n hakutuloksia voidaan verrata ID-tasolla; ICTRP:n tietuekenttiä ei tuoda julkaistavaan JSONiin.
8. Kun lähdejoukko tai hakustrategia muuttuu, tee uusi 50 tietueen kerrostettu relevanssi- ja statustarkistus. Merkitse epäselvät tietueet review-jonoon, älä pakota sisällyttämisratkaisua.
9. Tarkista kunkin lähteen käyttöehdot, API-ehdot ja mahdolliset automaattisen lataamisen rajoitukset. Kirjaa myös lähteen vaatima päivitystiheys, käsittely-/julkaisupäivä, lähdemerkintä ja muutoskuvaus. ClinicalTrials.govin ehdoissa vaaditaan ajantasaista aineistoa ja lähteen käsittelypäivän näyttämistä; tämän pilotin API-vienti ei sisältänyt yleistä käsittelypäivää, eikä kuukausittainen päivitys takaa tietueiden jatkuvaa ajantasaisuutta. Älä merkitse lähdettä hyväksytyksi ennen kuin nämä ehdot voidaan täyttää tai lähde vahvistaa hyväksyttävän toteutustavan. `snapshot-metadata.json`-tiedoston `reuse_review` on läpäistävä jokaisen sivulle tuotavan rekisterin osalta. Julkinen sivu ei saa käyttää rekisteriä, jonka uudelleenjulkaisun peruste on yhä epäselvä.
10. Aja `python scripts/process_direct_sources.py`, tarkista paikallinen tarkistusjono ja tulosteen kentät, tarkista ettei mukana ole nimiä, sähköposteja, puhelinnumeroita tai katuosoitteita, ja aja kaikki testit. Kun molemmat julkaisuehdot täyttyvät, salaa tulos `PBM_STUDIES_DATA_KEY`-salaisuudella ja päivitä vain salattu `dist/studies/ongoing-studies.json`.

## Statusten käsittely

Sivu säilyttää lähteen alkuperäisen statusarvon ja näyttää erillisen suodatuksen. Ongoing-näkymään kuuluvat esimerkiksi Recruiting, Not yet recruiting, Enrolling by invitation, Active, not recruiting ja Suspended. Completed, terminated ja withdrawn pysyvät kaikissa tietueissa mutta vain “All records” -näkymässä. “Recruitment completed” ei yksin tarkoita, että tutkimus olisi päättynyt; jätä se tarkistusryhmään, kunnes rekisterin statusmääritelmä ja tietue vahvistavat asian. Tuntematon tai ristiriitainen status jää tarkistusjonoon.

## Hakukattavuuden mittaus

Raportoi erikseen (a) raakarivien määrä, (b) yksilölliset rekisteritietueet, (c) varmistetut eri tutkimukset, (d) suoraan haetut rekisterit ja (e) rekisterit joista puuttuu toimiva bulk-vienti/API. WHO ICTRP:n löydös on hyödyllinen vihje siitä, mihin alkuperäisrekisteriin mennä, mutta se ei ole kyseisen rekisterin suora haku eikä julkaistavan tietueen lähde.

## Pyydettävät käyttäjän toimet

Pyydä vain pieni, rajattu toimi, jota tekoäly ei pysty suorittamaan: esimerkiksi “Avaa [virallinen osoite], hae `photobiomodulation`, paina `Export CSV` ja lataa tulos tähän keskusteluun.” Kerro ennen pyyntöä, miksi lähteen oma automaattinen haku ei toiminut ja mitä sarakkeita/formaattia tarvitaan. Jos lähteen käyttöehdot eivät salli vientiä tai sivulla on CAPTCHA, älä pyydä kiertämään sitä.

## Kuukausiraportti

Ilmoita uudet tietueet, statuksen muutokset, vahvistetut duplikaatit, poissuljetut ja epäselvät osumat rekistereittäin. Vertaa suoraa rekisterihakuja ICTRP:stä löytyneisiin ID-tunnisteisiin. Anna käyttöehtojen avoimet kysymykset ja käyttäjälle korkeintaan muutama suora, täsmällinen pyyntö.
