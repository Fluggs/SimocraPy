#!/usr/bin/env python3.4

import simocracy.wiki as wiki
import re, sys
import simocracy.datum as sydatum

from datetime import datetime

unknown = "Unbekannt"

"""
Wird geworfen, falls in einer Infobox Staat wichtige
Daten fehlen
"""
class InfoboxException(Exception):
    pass

"""
' 103.534.464,36 xyz' -> 103534454.36
"""
def parseNumberToInt(string):
    if string is None:
        return None
    #zB 103.534.464,36 xyz
    p = re.compile(r'\s*([\d\.]+)')
    if p.match(string) is not None:
        i = p.split(string)[1]
        i = i.replace(".", '')
        
        #Fehlerabfang
        if re.match(r'\d*', i) is None:
            return None

        return int(i)

"""
12,649,437.32 -> '12.649.437,32'
"""
def parseNumberToString(n):
    format = None
    if isinstance(n, int):
        format = "{:,}"
    elif isinstance(n, float):
        format = "{:,.2f}"
    else:
        raise TypeError("n is not int or float")
    r = format.format(n).replace(".","+").replace(",",".")
    return r.replace("+",",")

def parseEwBip(staat):
    #EW und BIP-EW parsen
    bip_ew = None
    ew = None
    bip = None
    ew = parseNumberToInt(staat["infobox"]["Einwohnerzahl"])
    if "BIP-EW" in staat["infobox"]:
        bip_ew = parseNumberToInt(staat["infobox"]["BIP-EW"])

    #BIP ausrechnen
    if ew is not None:
        #Wenn BIP-EW gegeben, BIP hieraus errechnen
        if bip_ew is not None:
            bip = bip_ew*ew
        #Anderenfalls gegebenes BIP nehmen und BIP-EW berechnen
        elif "BIP" in staat["infobox"]:
            bip = parseNumberToInt(staat["infobox"]["BIP"])
            if bip is not None and ew != 0:
                bip_ew = float(bip) / float(ew)

    return {
        "ew":ew,
        "bip":bip,
        "bip-ew":bip_ew,
    }

"""
3.5025 => 3,5
"""
def niceFloatStr(n):
    i = round(n)
    if i >= 1000:
        return parseNumberToString(i)
    n = '{0:g}'.format(round(n,2))
    n = n.replace(',', '*').replace('.', ',')
    return n.replace('*', '.')

"""
Extrahiert den Währungsnamen aus Währungsstrings
aus Infoboxen, zB [[Staat#Währung|Ziegen (Z)]] => Ziegen
"""
def extractWaehrung(s):
    #Links auflösen
    p = re.compile(r'\[\[([^]]*)\]\]')
    while True:
        m = re.search(p, s)
        if m:
            tokens = m.group(1).split('|')
            repl = tokens[len(tokens) - 1]
            s = p.sub(repl, s, count=1)
        else:
            break

    #Notwendige Replacementliste
    s = s.replace('<br>', ' ')
   
    return re.split(r'([^({\d=]*)', s)[1].strip()

"""
Entfernt Klammerinhalte sowie kursives Zeug aus s.
"""
def remBrackets(s):
    patterns = [
        re.compile(r'\(.*?\)'),
        re.compile(r"''[^']*?''"),
    ]
    for p in patterns:
        while True:
            e = re.subn(p, "", s)
            s = e[0].strip()
            if e[1] == 0:
                break

    return s

"""
Normalisiert die Währungsangabe
"""
def normalizeWaehrung(s):
    #Links übernehmen; kriegt auch Oranje-[[Gulden]] mit
    #Match wird dafür in Teile zerteilt
    p = re.compile(r'(?P<pre>[^\s]*)\[\[(?P<in>[^]]*)\]\](?P<post>[^\s]*)')
    m = re.search(p, s)
    if m:
        s = m.groupdict()
    else:
        s = {"pre":s}

    #Abhacken vor bestimmten Zeichen
    for part in s:
        charlist = [r'\(', r'<', r'\{', r'/']
        for c in charlist:
            m = re.search(r'([^'+c+r']*)', s[part])
            if m:
                s[part] = m.group().strip()

    #Wieder zusammensetzen
    r = s["pre"]
    if "in" in s:
        r = r + "[[" + s["in"] + "]]"
    if "post" in s:
        r = r + s["post"]

    s = r

    #"1 Ziege = 4 Beine" =>  "Ziege"
    p = r'\d+\s*([^\s]*)'
    m = re.match(p, s)
    if m:
        s = m.group(1)

    return s

"""
Normalisiert die Angabe der Amtssprache.
"""
def normalizeSprache(s):
    s = remBrackets(s)

    #Anhänge abhacken anhand von Signalstrings
    signals = []
    for el in [
        #Signalstringliste
        r'sowie',
        r'diverse',
        r'+',
    ]:
        signals.append(el+r'.*?$')

    for el in signals:
        s = s.replace(el, "").strip()

    #Einzelsprachen isolieren und normalisieren
    trenner = [
        r",",
        r";",
        r"/",
        r"&",
        r"<br>",
        r"und",
    ]

    for el in trenner:
        s = s.replace(el, ";")

    s = re.split(";", s)
    sprachen = []

    for el in s:
        el = el.strip()
        if el == "":
            continue

        #Capitalize
        el = el[0].upper() + el[1:]

        sprachen.append(el)

    s = ""
    for el in sprachen:
        s += " "+el+","

    # Sonderregel für Neuseeland
    s = re.sub(r"\s*mehrheitlich\s*", "", s)

    #Erstes " " und letztes "," abhacken
    return s[1:len(s)-1:1]

"""
Normalisiert die TLD-Angabe s
"""
def normalizeTLD(s):
    s = remBrackets(s)

    #Trenner vereinheitlichen
    trenner = [
        "/",
        ",",
        "<br>",
    ]
    for el in trenner:
        s = s.replace(el, " ")

    #TLD-Angaben rauspicken und String bauen
    tokens = re.findall(r"(\.[^\s]*)", s)
    s = ""
    for el in tokens:
        s += " " + el.strip().lower()

    return s[1:]

"""
Normalisiert KFZ-Kennzeichenangaben
"""
def normalizeKFZ(s):
    s = remBrackets(s)

    #Trenner vereinheitlichen
    s = s.replace("/", ", ")

    #Bilder skalieren
    size = 40
    links = wiki.parseLinks(s)
    for link in links:
        if link["file"]:
            toRepl = wiki.buildLink(link)
            newLink = "[["+link["uri"]
            newLink += "|" + str(size) + "px"
            if "filelink" in link:
                newLink += "|link=" + link["filelink"]
            newLink += "]]"

            #replace
            split = re.split(re.escape(toRepl), s)
            s = split[0]
            for i in range(1, len(split)):
                s += newLink + split[i]

    return s

"""
Normalisiert Vorwahlangaben
"""
def normalizeVorwahl(s):
    if s == unknown:
        return s

    s = remBrackets(s)

    split = re.split(",", s)

    #auf +xy-Angabe normalisieren
    s = ""
    for el in split:
        el = el.strip()
        if el.startswith("+"):
            s += " "+el+","
        elif el.startswith("00"):
            s += " +"+el[2:]+","
        else:
            s += " +"+el+","

    return s[1:len(s)-1:1]

"""
Hilfsfunktion für normalizeZeitzone()
"""
def remWhitespace(matchobject):
    return re.sub("\s+", "", matchobject.group())

"""
Normalisiert Zeitzonenangaben
"""
def normalizeZeitzone(s):
    if s == unknown:
        return s

    s = remBrackets(s)
    trenner = [
        "/",
        "und",
        "<br>",
    ]
    for el in trenner:
        s = s.replace(el, ",")

    s = s.replace("GMT", "UTC")

    s = re.sub(r"UTC\s*\+", "+", s)
    s = re.sub(r"UTC\s*-", "-", s)

    #"UTC" => "+0"
    s = re.sub(r"UTC\s*[^+\-\s]?", r"+0,", s)

    s = s.replace("UTC", "")

    #"+ 1" => "+1"
    s = re.sub("[+-]\s+\d*", remWhitespace, s)

    #Whitespaces normalisieren
    s = re.sub(r"\s{2,}", " ", s)

    #Splitten und wieder zusammensetzen
    split = re.split(r",", s)
    s = ""
    for el in split:
        if el == '' or re.match(r"\s*$", el):
            continue
        s += " " + el.strip() + ","

    return s[1:len(s)-1:1]

"""
Prüft auf wichtige Werte 
Füllt Infobox-dicts mit unknown-Werten auf
"""
def normalizeInfobox(infobox, name):
    mandatoryList = [
        "Einwohnerzahl",
        "Fläche",
    ]
    unknownList = [
        "TLD",
        "Amtssprache",
        "KFZ",
        "Zeitzone",
        "Telefonvorwahl",
        "Kürzel",
    ]

    for key in mandatoryList:
        if not key in infobox or infobox[key] is None:
            raise InfoboxException(key + " fehlt in Infobox " + name)

    for key in unknownList:
        if not key in infobox or infobox[key] is None:
            infobox[key] = unknown

    return infobox


"""
Erstellt eine Liste der drei meistgenutzten (nach f(w))
Währungen in aufsteigender Reihenfolge:
[
  {
    "name":name
    "anz":anzahl
  }, x3
]
"""
def sumUpWaehrung(w, f):
    erg = []
    for el in w:
        #Währung in erg suchen; bei Fund inkrementieren
        found = False
        for i in range(0, len(erg)):
            if el["name"] == erg[i]["name"]:
                found = True
                break
        if found:
            erg[i]["anz"] += f(el)

        #Ansonsten neues dict für Währung hinzufügen
        else:
            erg.append({"name":el["name"], "anz":f(el),})

    erg = sorted(erg, key=lambda k:k["anz"])
    return erg[-3:]


def updateArticle(staaten):

    #Ajin ignorieren
    #toRemove = []
    #for staat in alleStaaten:
    #    if "Singa Shang" in staat["uri"] or "Ajin" in staat["uri"]:
    #        toRemove.append(staat)
    #for el in toRemove:
    #    alleStaaten.remove(el)

    #Infoboxen normalisieren
    for staat in staaten:
        if not staat["infobox"] == None:
            staat["infobox"] = normalizeInfobox(staat["infobox"], staat["uri"])

    
    #Einzeleinträge aufsetzen
    #Jahr ausrechnen
    heute = datetime.now()
    datum = {
        "tag"    : int(heute.day),
        "monat"  : int(heute.month),
        "jahr"   : int(heute.year),
        "stunde" : int(heute.hour),
        "minute" : int(heute.minute)
    }
    jahr = sydatum.rltosy(datum)["jahr"]

    gesamt = {
        "flaeche":[],
        "ew":[],
        "bip":[],
        "waehrung":[],
    }

    #Infotabellen-dicts auslesen und Vorlageneinträge zusammensetzen
    text_stats = ""
    text_info = ""
    for staat in staaten:
        
        #Fläche
        flaeche = None
        flaeche_int = None
        if not "infobox" in staat:
            print("Warnung - "+staat["uri"]+" hat keine Infobox")
            continue
        elif "Fläche" in staat["infobox"]:
            flaeche = parseNumberToInt(staat["infobox"]["Fläche"])
            flaeche_int = flaeche
            if flaeche is None:
                flaeche = unknown
            gesamt["flaeche"].append(flaeche)
        #Nicht in Infobox oder nicht parsebar
        if flaeche is None or flaeche == 0 or flaeche == unknown:
            flaeche = unknown
        else:
            flaeche = parseNumberToString(flaeche)

        #BIP, BIP pro Kopf, EW
        bip_ew = None
        bip = None
        ew = None
        ew_int = None
        if "infobox" in staat:
            n = parseEwBip(staat)
            if n["bip"] is None:
                bip = unknown
            else:
                bip = parseNumberToString(n["bip"])

            if n["bip-ew"] is None:
                bip_ew = unknown
            else:
                bip_ew = parseNumberToString(n["bip-ew"])

            if n["ew"] is None:
                ew = unknown
            else:
                ew = parseNumberToString(n["ew"])
            ew_int = n["ew"]
            if n["bip"] is not None:
                gesamt["bip"].append(n["bip"])
            if n["ew"] is not None:
                gesamt["ew"].append(n["ew"])
        else:
            bip = unknown
            bip_ew = unknown
            ew = unknown
        if not "infobox" in staat:
            pass

        #EW pro Fläche
        ew_flaeche = None
        if ew_int is not None and flaeche_int is not None:
            ew_flaeche = float(ew_int) / float(flaeche_int)
            ew_flaeche = parseNumberToString(ew_flaeche)
        else:
            ew_flaeche = unknown

        #Währung
        waehrung = None
        if "Währung" in staat["infobox"]:
            waehrung = staat["infobox"]["Währung"]
            if waehrung is None or re.match(r'^\s*$', waehrung) is not None:
                waehrung = unknown
            else:
                d = {
                    "name":extractWaehrung(waehrung),
                    "ew":ew_int,
                }
                gesamt["waehrung"].append(d)
        else:
            waehrung = unknown
        waehrung = normalizeWaehrung(waehrung)

        #Amtssprache
        sprache = normalizeSprache(staat["infobox"]["Amtssprache"])

        #TLD
        tld = normalizeTLD(staat["infobox"]["TLD"])
        if tld is None or tld == "":
            tld = unknown

        #KFZ-Kennzeichen
        kfz = normalizeKFZ(staat["infobox"]["KFZ"])

        #Vorwahl
        vorwahl = normalizeVorwahl(staat["infobox"]["Telefonvorwahl"])

        #Zeitzone
        zeitzone = normalizeZeitzone(staat["infobox"]["Zeitzone"])
        
        #Vorlagentext zusammensetzen: Statistik
        flagge = "Flagge-None.png"
        flagge = staat["infobox"]["Flagge"]
        eintrag = "{{IAS Eintrag Statistik\n"
        eintrag += "|Sortierungsname="+staat["sortname"]+"\n"
        eintrag += "|Flagge="+flagge+"\n"
        eintrag += "|Name="+staat["name"]+"\n"
        eintrag += "|Artikel="+staat["uri"]+"\n"
        eintrag += "|Fläche="+flaeche+"\n"
        eintrag += "|Einwohnerzahl="+ew+"\n"
        eintrag += "|EW-Fläche="+ew_flaeche+"\n"
        eintrag += "|BIP="+bip+"\n"
        eintrag += "|BIP-EW="+bip_ew+"\n"
        eintrag += "}}\n"

        text_stats = text_stats + eintrag

        #Vorlagentext zusammensetzen: Allgemeine Informationen
        flagge = staat["infobox"]["Flagge"]
        eintrag = "{{IAS Eintrag Info\n"
        eintrag += "|Sortierungsname="+staat["sortname"]+"\n"
        eintrag += "|Flagge="+flagge+"\n"
        eintrag += "|Name="+staat["name"]+"\n"
        eintrag += "|Artikel="+staat["uri"]+"\n"
        eintrag += "|Kürzel="+staat["infobox"]["Kürzel"]+"\n"
        eintrag += "|Amtssprache="+sprache+"\n"
        eintrag += "|Währung="+waehrung+"\n"
        eintrag += "|TLD="+tld+"\n"
        eintrag += "|KFZ="+kfz+"\n"
        eintrag += "|Vorwahl="+vorwahl+"\n"
        eintrag += "|Zeitzone="+zeitzone+"\n"
        eintrag += "}}\n"

        text_info = text_info + eintrag

    #Allgemeine Statistiken
    pre = "<onlyinclude>{{IAS Anfang\n"
    pre += "|Jahr="+str(int(jahr))+"\n"

    flaeche_gesamt = 0
    for el in gesamt["flaeche"]:
        if el is not unknown:
            flaeche_gesamt += el
    flaeche_schnitt = flaeche_gesamt / len(gesamt["flaeche"])
    pre += "|Gesamt-Fläche="+parseNumberToString(flaeche_gesamt)+"\n"
    pre += "|Schnitt-Fläche="+parseNumberToString(flaeche_schnitt)+"\n"

    ew_gesamt = 0
    for el in gesamt["ew"]:
        ew_gesamt += el
    ew_schnitt = float(ew_gesamt) / float(len(gesamt["ew"]))
    pre += "|Gesamt-EW="+parseNumberToString(round(ew_gesamt))+"\n"
    pre += "|Schnitt-EW="+niceFloatStr(ew_schnitt)+"\n"

    bip_gesamt = 0
    for el in gesamt["bip"]:
        bip_gesamt += el
    bip_schnitt = bip_gesamt / len(gesamt["bip"])
    pre += "|Gesamt-BIP="+parseNumberToString(bip_gesamt)+"\n"
    pre += "|Schnitt-BIP="+parseNumberToString(bip_schnitt)+"\n"

    ew_fl_gesamt = float(ew_gesamt) / float(flaeche_gesamt)
    bip_ew_gesamt = float(bip_gesamt) / float(ew_gesamt)
    pre += "|EW-Fläche="+niceFloatStr(ew_fl_gesamt)+"\n"
    pre += "|BIP-EW="+parseNumberToString(int(bip_ew_gesamt))+"\n"

    #Währungen nach Anzahl Staaten
    erg = sumUpWaehrung(gesamt["waehrung"], lambda w:1)
    pre += "|WährungSt1="+erg[2]["name"]+"\n"
    pre += "|WährungStAnz1="+parseNumberToString(erg[2]["anz"])+"\n"
    pre += "|WährungSt2="+erg[1]["name"]+"\n"
    pre += "|WährungStAnz2="+parseNumberToString(erg[1]["anz"])+"\n"
    pre += "|WährungSt3="+erg[0]["name"]+"\n"
    pre += "|WährungStAnz3="+parseNumberToString(erg[0]["anz"])+"\n"

    #Währung nach EW
    erg = sumUpWaehrung(gesamt["waehrung"], lambda w:w["ew"])
    pre += "|WährungEw1="+erg[2]["name"]+"\n"
    pre += "|WährungEwAnz1="+parseNumberToString(erg[2]["anz"])+"\n"
    pre += "|WährungEw2="+erg[1]["name"]+"\n"
    pre += "|WährungEwAnz2="+parseNumberToString(erg[1]["anz"])+"\n"
    pre += "|WährungEw3="+erg[0]["name"]+"\n"
    pre += "|WährungEwAnz3="+parseNumberToString(erg[0]["anz"])+"\n}}\n"

    #IAS Anfang Statistik und Tabber
    pre += "<Tabber>\nStatistiken={{IAS Anfang Statistik}}"

    text = pre + text_stats
    text += "\n|}\n"
    text += "|-|\nWeitereInformationen="
    text += "{{IAS Anfang Info}}\n"
    text += text_info
    text += "|}\n"
    text += "|-|</tabber>\n\n"
    text += "</onlyinclude>\n"
    text += "[[Kategorie:Internationales Amt für Statistiken]]"
    text += "[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:IAS", text)

    #Staaten zählen
    bespielt = 0
    spielerlos = 0
    for staat in staaten:
        if staat["spielerlos"]:
            spielerlos += 1
        else:
            bespielt += 1
    
    #Vorlage:Anzahl Staaten
    text = "<onlyinclude><includeonly>" + str(len(staaten))
    text = text + "</includeonly></onlyinclude>\n"
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der Staaten in Simocracy "
    text = text + "zurück. Gezählt werden alle Staaten des Planeten.<br>\nSie wird auf "
    text = text + "Basis der Staatenliste im [[Wikocracy:Portal|Portal]] berechnet.\n\n"
    text = text + "[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Staaten", text)

    #Vorlage:Anzahl Freie Staaten
    text = "<onlyinclude><includeonly>" + str(spielerlos)
    text = text + "</includeonly></onlyinclude>\n"
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der freien Staaten in "
    text = text + "Simocracy zurück. Gezählt werden alle Staaten des Planeten.<br>\nSie "
    text = text + "wird auf Basis der Staatenliste im [[Wikocracy:Portal|Portal]] berechnet."
    text = text + "\n\n[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Freie_Staaten", text)

    #Vorlage:Anzahl Bespielte Staaten
    text = "<onlyinclude><includeonly>" + str(bespielt)
    text = text + "</includeonly></onlyinclude>\n"
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der bespielten Staaten in "
    text = text + "Simocracy zurück.<br>\nSie wird auf Basis der Staatenliste im "
    text = text + "[[Wikocracy:Portal|Portal]] berechnet.\n\n[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Bespielte_Staaten", text)

    #Vorlage:Anzahl Spieler
    spielerliste = []
    for staat in staaten:
        if staat["spielerlos"]:
            continue

        spieler = staat["spieler"]
        spieler = spieler.replace("[[", "").replace("]]", "")
        spieler = spieler.replace(",", ";").replace(" und ", ";")
        spieler = spieler.split(";")
        for el in spieler:
            el = el.strip()
            if not el in spielerliste:
                spielerliste.append(el)
        spielerliste = sorted(spielerliste, key=lambda s: s.lower())

    text = "<onlyinclude><includeonly>" + str(len(spielerliste))
    text = text + "</includeonly></onlyinclude>\n"
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der aktiven Spieler "
    text = text + "in Simocracy zurück.<br>\nSie wird auf Basis der Staatenliste im "
    text = text + "[[Wikocracy:Portal|Portal]] berechnet.<br>\n===Derzeitige Spieler===\n"
    for spieler in spielerliste:
        text = text + spieler + "<br>\n"
    text = text + "\n[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Spieler", text)
