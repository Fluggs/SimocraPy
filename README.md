# SimocraPy
Pythontools für Simocracy (im Wesentlichen Wikistuff)

### datum.py
Datumsrechner-Modul.
Enthält die zwei Datumsrechner-Funktionen (RL->SY und SY->RL).
Diese erwarten eine 5-stellige Liste mit dem Datum und gibt eine solche auch wieder zurück:
`[Tag, Monat, Jahr, Stunde, Minute]`

Liegt ein Datum nicht in der Simocracy-Epoche, wird die `SyEpocheException` geworfen.

Keine Abhängigkeiten.


##### rltosy(datum)
Konvertiert ein RL-Datum ins entsprechende SY-Datum.


##### sytorl(datum)
Konvertiert ein SY-Datum ins entsprechende RL-Datum.



### wiki.py
Sammlung von Funktionen für das Arbeiten im Wiki.


##### login(username, password)
Loggt das Modul ins Wiki ein. Kann auch als login() aufgerufen werden; dies verwendet
dann die am Anfang des Moduls eingetragenen Logindaten.


##### readVZ()
Liest das Wikiportal aus.
Gibt ein Dictionary mit drei Einträgen (`staaten`, `buendnisse`, `spielerlos`) zurück, welche wiederum je eine Liste von Dictionaries enthalten.
Der Zugriff auf den Namen des (alphabetisch) ersten Staats im Portal sieht z.B. wie folgt aus:
```
r = wiki.readVZ()
name = r["staaten"][0]["name"]
```

Keys von `staaten` und `spielerlos`:
* `nummer`
* `flagge` (bild-URL)
* `name`
* `uri` (Artikelname)
* `buendnis` (flaggen-URL)
* `ms`
* `as`
* `spieler`
* `zweitstaat` (Boolescher Wert)

Keys `buendnisse`:
* `flagge`
* `name`


##### openArticle(article)
Öffnet einen Artikel (mithilfe von `opener.open()`); löst insb. Redirections auf.
Erwartet den Artikelnamen als Argument.


##### editArticle(article, text)
Schreibt `text` in den Wikiartikel `article`.


##### globalizeLinks(s, article)
Macht alle lokalen Links in s global.
Nimmt article als Artikelnamen für die lokalen Links an.
Berücksichtigt auch Dateilinks, z.B.
[[Datei:file.png|30px|link=#whatever]]


##### parseLinks(s)
Gibt alle Wikilinks (`[[ ... ]]`) im String s als Liste von dicts zurück:

Zwingend vorhanden:
* `"uri"`:Ziel des Links
* `"file"`:boolescher Wert; gibt an, ob Link eine Datei ist

Vorhanden, falls im Link vorhanden:
* `"filelink"`:Link der "belinkten" Datei (|link=filelink)
* `"name"`:Name des Links bzw. Größenangabe der Datei


##### buildLink(s)
Baut einen Link-String aus einem dict wie in parseLinks() zusammen.


##### parseTemplate(template, site)
Parst das erste Vorkommen der Vorlage template auf der Seite site (Rückgabe von `openArticle()`) und gibt ein Dictionary mit den Werten zurück.
Das Auslesen der flugghischen Infobox geschieht z.B. wie folgt:
```
infobox = wiki.parseTemplate("Infobox Staat", wiki.openArticle("Flugghingen"))
```


##### removeLinks(s)
Ersetzt alle Wikilinks im String s durch den Namen des Links,
d.h. entfernt alle Wikilinks.


### IAS.py
Modul für das Internationale Amt für Statistiken. Enthät lediglich `updateArticle()` und dafür notwendige Hilfsfunktionen.
`updateArticle()` loggt sich ins Wiki ein, liest das Wiki aus, liest die Infoboxen aller dort eingetragenen Staaten aus und updatet folgende Artikel:
* [Vorlage:IAS](simocracy.de/Vorlage:IAS)
* [Vorlage:Anzahl_Staaten](simocracy.de/Vorlage:Anzahl_Staaten)
* [Vorlage:Anzahl_Freie_Staaten](simocracy.de/Vorlage:Anzahl_Freie_Staaten)
* [Vorlage:Anzahl_Bespielte_Staaten](simocracy.de/Vorlage:Anzahl_Bespielte_Staaten)
* [Vorlage:Anzahl_Spieler](simocracy.de/Vorlage:Anzahl_Spieler)

Abhängigkeiten:
* datum.py
* wiki.py
