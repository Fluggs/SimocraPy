# -*-coding: UTF-8 -*-

import simocracy.wiki as wiki
import re
import simocracy.datum as sydatum

from datetime import datetime

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
    if "Einwohnerzahl" in staat["infobox"]:
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


def updateArticle():
    unknown = "Unbekannt"

    #Infoboxen einlesen
    print("Lese Portal ein")
    opener = wiki.login(wiki.username, wiki.password)
    vz = wiki.readVZ(wiki.openArticle(wiki.vz, opener), opener)

    #Alle Staaten zusammensammeln
    alleStaaten = []
    for staat in vz["staaten"]:
        staat['spielerlos'] = False
        alleStaaten.append(staat)
    for staat in vz["spielerlos"]:
        staat['spielerlos'] = True
        alleStaaten.append(staat)

    alleStaaten =  sorted(alleStaaten, key=lambda k: k['sortname'])

    print("Lese Infoboxen ein")
    for staat in alleStaaten:
        infobox = wiki.parseTemplate("Infobox Staat", wiki.openArticle(staat["uri"], opener))
        if not infobox == None:
            staat["infobox"] = infobox
    
    #Einzeleinträge aufsetzen
    #Jahr ausrechnen
    heute = datetime.now()
    datum = [
        int(heute.day),
        int(heute.month),
        int(heute.year),
        int(heute.hour),
        int(heute.minute)
    ]
    jahr = sydatum.rltosy(datum)[2]

    gesamt = {
        "flaeche":[],
        "ew":[],
        "bip":[],
        "waehrung":[],
    }
    text = ""
    for staat in alleStaaten:
        
        #Fläche
        flaeche = None
        flaeche_int = None
        if not "infobox" in staat:
            pass
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
        if not "infobox" in staat:
            waehrung = unknown
        elif "Währung" in staat["infobox"]:
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
        waehrung = waehrung.replace('[[#', '[['+staat['uri']+'#')
        
        
        #Vorlagentext zusammensetzen
        flagge = "Flagge-None.png"
        if "infobox" in staat:
            flagge = staat["infobox"]["Flagge"]
        eintrag = "{{IAS Eintrag\n|Sortierungsname="+staat["sortname"]+"\n"
        eintrag = eintrag+"|Flagge="+flagge+"\n|Name="+staat["name"]+"\n"
        eintrag = eintrag+"|Artikel="+staat["uri"]+"\n|Fläche="+flaeche+"\n"
        eintrag = eintrag+"|Einwohnerzahl="+ew+"\n|EW-Fläche="+ew_flaeche+"\n"
        eintrag = eintrag+"|BIP="+bip+"\n|BIP-EW="+bip_ew+"\n|Währung="+waehrung+"}}\n"

        text = text + eintrag

    #Allgemeine Statistiken
    pre = "<onlyinclude>{{IAS Anfang\n|Jahr="+str(int(jahr))+"\n"

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

    text = pre + text
    text = text + "\n|}</onlyinclude>\n[[Kategorie:Internationales "
    text += "Amt für Statistiken]][[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:IAS", text, opener)

    #Vorlage:Anzahl Staaten
    text = "<onlyinclude><includeonly>" + str(len(alleStaaten))
    text = text + "</includeonly></onlyinclude>\n"
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der Staaten in Simocracy "
    text = text + "zurück. Gezählt werden alle Staaten des Planeten.<br>\nSie wird auf "
    text = text + "Basis der Staatenliste im [[Wikocracy:Portal|Portal]] berechnet.\n\n"
    text = text + "[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Staaten", text, opener)

    #Vorlage:Anzahl Freie Staaten
    text = "<onlyinclude><includeonly>" + str(len(vz["spielerlos"]))
    text = text + "</includeonly></onlyinclude>\n"
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der freien Staaten in "
    text = text + "Simocracy zurück. Gezählt werden alle Staaten des Planeten.<br>\nSie "
    text = text + "wird auf Basis der Staatenliste im [[Wikocracy:Portal|Portal]] berechnet."
    text = text + "\n\n[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Freie_Staaten", text, opener)

    #Vorlage:Anzahl Bespielte Staaten
    text = "<onlyinclude><includeonly>" + str(len(vz["staaten"]))
    text = text + "</includeonly></onlyinclude>\n"
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der bespielten Staaten in "
    text = text + "Simocracy zurück.<br>\nSie wird auf Basis der Staatenliste im "
    text = text + "[[Wikocracy:Portal|Portal]] berechnet.\n\n[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Bespielte_Staaten", text, opener)

    #Vorlage:Anzahl Spieler
    spielerliste = []
    for staat in vz["staaten"]:
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
    text = text + "Diese Vorlage gibt die aktuelle Anzahl der Staaten (inkl. Zweitstaaten) "
    text = text + "in Simocracy zurück.<br>\nSie wird auf Basis der Staatenliste im "
    text = text + "[[Wikocracy:Portal|Portal]] berechnet.<br>\n===Derzeitige Spieler===\n"
    for spieler in spielerliste:
        text = text + spieler + "<br>\n"
    text = text + "\n[[Kategorie:Fluggbot]]"
    wiki.editArticle("Vorlage:Anzahl_Spieler", text, opener)
