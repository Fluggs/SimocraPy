#!/usr/bin/env python3.4

import simocracy.wiki as wiki
import re
import simocracy.datum as sydatum

from datetime import datetime

unknown = "Unbekannt"


class InfoboxException(Exception):
    """
    Wird geworfen, falls in einer Infobox Staat wichtige
    Daten fehlen
    """
    pass


def parse_numbertoint(string):
    """
    ' 103.534.464,36 xyz' -> 103534454.36
    """
    if string is None:
        return None
    # zB 103.534.464,36 xyz
    p = re.compile(r'\s*([\d\.]+)')
    if p.match(string) is not None:
        i = p.split(string)[1]
        i = i.replace(".", '')
        
        # Fehlerabfang
        if re.match(r'\d*', i) is None:
            return None

        return int(i)


def parse_numbertostring(n):
    """
    12,649,437.32 -> '12.649.437,32'
    """
    if isinstance(n, int):
        formatstr = "{:,}"
    elif isinstance(n, float):
        formatstr = "{:,.2f}"
    else:
        raise TypeError("n is not int or float")
    r = formatstr.format(n).replace(".", "+").replace(",", ".")
    return r.replace("+", ",")


def parse_ew_bip(staat):
    # EW und BIP-EW parsen
    bip_ew = None
    bip = None
    ew = parse_numbertoint(staat["infobox"]["Einwohnerzahl"])
    if "BIP-EW" in staat["infobox"]:
        bip_ew = parse_numbertoint(staat["infobox"]["BIP-EW"])

    # BIP ausrechnen
    if ew is not None:
        #  Wenn BIP-EW gegeben, BIP hieraus errechnen
        if bip_ew is not None:
            bip = bip_ew*ew
        # Anderenfalls gegebenes BIP nehmen und BIP-EW berechnen
        elif "BIP" in staat["infobox"]:
            bip = parse_numbertoint(staat["infobox"]["BIP"])
            if bip is not None and ew != 0:
                bip_ew = float(bip) / float(ew)

    return {
        "ew": ew,
        "bip": bip,
        "bip-ew": bip_ew,
    }


def nice_floatstr(n):
    """
    3.5025 => 3,5
    """
    i = round(n)
    if i >= 1000:
        return parse_numbertostring(i)
    r = '{0:g}'.format(round(n, 2))
    r = r.replace(',', '*').replace('.', ',').replace('*', '.')
    return r


def extract_waehrung(s):
    print("orig: "+s)
    """
    Extrahiert den Währungsnamen aus Währungsstrings
    aus Infoboxen, zB [[Staat#Währung|Ziegen (Z)]] => Ziegen
    """
    # Links auflösen
    p = re.compile(r'\[\[([^]]*)\]\]')
    while True:
        m = re.search(p, s)
        if m:
            tokens = m.group(1).split('|')
            repl = tokens[len(tokens) - 1]
            s = p.sub(repl, s, count=1)
        else:
            break

    # Notwendige Replacementliste
    print(s)
    s = s.replace('<br>', ' ')
   
    return re.split(r'([^({\d=]*)', s)[1].strip()


def normalize_waehrung2(s, article):
    """

    :param s: Währungsstring, der zu normalisieren ist
    :param article: Artikelname, in dem der Währungsstring aufgetaucht ist (für Linkglobalisierung)
    :return: {"string": Währungsstring mit Links, "name": Name der Währung}; None falls s leerer String ist
    """

    links = wiki.parse_links(s)
    link = None
    if len(links) > 0:
        link = links[0]
        wiki.globalize_link(link, article)

    currency = s.strip()
    if currency == "":
        return None

    currency = wiki.remove_links(currency)
    print(currency)

    split_list = [",", ";", "(", "<", "sowie", "'", "<br>",]
    for divider in split_list:
        parts = currency.split(divider)
        for part in parts:
            part = part.strip()
            if part != "":
                print("part: "+part)
                currency = part
                break
            raise Exception('we just divided a currency string and got nothing out of it, should not happen:\n"'+s+'"')

    # Währungssstring mit Link wieder zusammenbauen
    r = {"name": currency}
    if link is None:
        r["string"] = r["name"]
    if link is not None and "name" in link:
        linkname = link["name"]
    elif link is not None:
        linkname = link["uri"].split("#")[0]
    else:
        r["string"] = r["name"]
        return r

    if linkname in currency:
        parts = currency.split(linkname, maxsplit=1)
        linkstring = wiki.build_link(link)
        r["string"] = parts[0] + linkstring + parts[1]

    else:
        r["string"] = wiki.build_link(link, name=currency)

    return r


def normalize_waehrung(s):
    """
    Normalisiert die Währungsangabe
    """
    # Links übernehmen; kriegt auch Oranje-[[Gulden]] mit
    # Match wird dafür in Teile zerteilt
    p = re.compile(r'(?P<pre>[^\s]*)\[\[(?P<in>[^]]*)\]\](?P<post>[^\s]*)')
    m = re.search(p, s)
    if m:
        s = m.groupdict()
    else:
        s = {"pre": s}

    # Abhacken vor bestimmten Zeichen
    for part in s:
        charlist = [r'\(', r'<', r'\{', r'/', r',', r';']
        for c in charlist:
            m = re.search(r'([^'+c+r']*)', s[part])
            if m:
                s[part] = m.group().strip()

    # Wieder zusammensetzen
    r = s["pre"]
    if "in" in s:
        r = r + "[[" + s["in"] + "]]"
    if "post" in s:
        r += s["post"]

    s = r

    # "1 Ziege = 4 Beine" =>  "Ziege"
    p = r'\d+\s*([^\s]*)'
    m = re.match(p, s)
    if m:
        s = m.group(1)

    return s


def rem_brackets(s):
    """
    Entfernt Klammerinhalte sowie kursives Zeug aus s.
    """
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


def normalize_sprache(s):
    """
    Normalisiert die Angabe der Amtssprache.
    """
    s = rem_brackets(s)

    # Anhänge abhacken anhand von Signalstrings
    signals = []
    for el in [
        # Signalstringliste
        r'sowie',
        r'diverse',
        r'+',
    ]:
        signals.append(el+r'.*?$')

    for el in signals:
        s = s.replace(el, "").strip()

    # Einzelsprachen isolieren und normalisieren
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

        # Capitalize
        el = el[0].upper() + el[1:]

        sprachen.append(el)

    s = ""
    for el in sprachen:
        s += " "+el+","

    # Sonderregel für Neuseeland
    s = re.sub(r"\s*mehrheitlich\s*", "", s)

    # Erstes " " und letztes "," abhacken
    return s[1:len(s)-1:1]


def normalize_tld(s):
    """
    Normalisiert die TLD-Angabe s
    """
    s = rem_brackets(s)

    # Trenner vereinheitlichen
    trenner = [
        "/",
        ",",
        "<br>",
    ]
    for el in trenner:
        s = s.replace(el, " ")

    # TLD-Angaben rauspicken und String bauen
    tokens = re.findall(r"(\.[^\s]*)", s)
    s = ""
    for el in tokens:
        s += " " + el.strip().lower()

    return s[1:]


def normalize_kfz(s):
    """
    Normalisiert KFZ-Kennzeichenangaben
    """
    s = rem_brackets(s)

    # Trenner vereinheitlichen
    s = s.replace("/", ", ")

    # Bilder skalieren
    size = 40
    links = wiki.parse_links(s)
    for link in links:
        if link["file"]:
            to_repl = wiki.build_link(link)
            new_link = "[["+link["uri"]
            new_link += "|" + str(size) + "px"
            if "filelink" in link:
                new_link += "|link=" + link["filelink"]
            new_link += "]]"

            # replace
            split = re.split(re.escape(to_repl), s)
            s = split[0]
            for i in range(1, len(split)):
                s += new_link + split[i]

    return s


def normalize_vorwahl(s):
    """
    Normalisiert Vorwahlangaben
    """
    if s == unknown:
        return s

    s = rem_brackets(s)

    split = re.split(",", s)

    # auf +xy-Angabe normalisieren
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


def rem_whitespace(matchobject):
    """
    Hilfsfunktion für normalizeZeitzone()
    """
    return re.sub("\s+", "", matchobject.group())


def normalize_zeitzone(s):
    """
    Normalisiert Zeitzonenangaben
    """
    if s == unknown:
        return s

    s = rem_brackets(s)
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

    # "UTC" => "+0"
    s = re.sub(r"UTC\s*[^+\-\s]?", r"+0,", s)

    s = s.replace("UTC", "")

    # "+ 1" => "+1"
    s = re.sub("[+-]\s+\d*", rem_whitespace, s)

    # Whitespaces normalisieren
    s = re.sub(r"\s{2,}", " ", s)

    # Splitten und wieder zusammensetzen
    split = re.split(r",", s)
    s = ""
    for el in split:
        if el == '' or re.match(r"\s*$", el):
            continue
        s += " " + el.strip() + ","

    return s[1:len(s)-1:1]


def normalize_infobox(infobox, name):
    """
    Prüft auf wichtige Werte
    Füllt Infobox-dicts mit unknown-Werten auf
    """
    mandatory_list = [
        "Einwohnerzahl",
        "Fläche",
    ]
    unknown_list = [
        "TLD",
        "Amtssprache",
        "KFZ",
        "Zeitzone",
        "Telefonvorwahl",
        "Kürzel",
    ]

    for key in mandatory_list:
        if key not in infobox or infobox[key] is None:
            raise InfoboxException(key + " fehlt in Infobox " + name)

    for key in unknown_list:
        if key not in infobox or infobox[key] is None:
            infobox[key] = unknown

    return infobox


def sum_up_waehrung(w, f):
    """
    Erstellt eine Liste der drei meistgenutzten (nach f(w))
    Währungen in aufsteigender Reihenfolge:
    [
      {
        "name":name
        "anz":anzahl
      }, x3
    ]
    :param w Liste aller Währungen
    :param f f(w) wie oben
    """
    erg = []
    for el in w:
        # Währungen in erg hinein zusammenaddieren
        found = False
        for i in range(0, len(erg)):
            if el["name"] == erg[i]["name"]:
                found = True
                break
        if found:
            erg[i]["anz"] += f(el)

        # Ansonsten neues dict für Währung hinzufügen
        else:
            erg.append({"name": el["name"], "anz": f(el)})

    erg = sorted(erg, key=lambda k: k["anz"])
    return erg[-3:]


def update_article(staaten):

    # Infoboxen auf Vollständigkeit prüfen
    for staat in staaten:
        if staat["infobox"] is not None:
            staat["infobox"] = normalize_infobox(staat["infobox"], staat["uri"])

    # Einzeleinträge aufsetzen
    # Jahr ausrechnen
    heute = datetime.now()
    datum = {
        "tag":    int(heute.day),
        "monat":  int(heute.month),
        "jahr":   int(heute.year),
        "stunde": int(heute.hour),
        "minute": int(heute.minute)
    }
    jahr = sydatum.rltosy(datum)["jahr"]

    gesamt = {
        "flaeche": [],
        "ew": [],
        "bip": [],
        "waehrung": [],
    }

    # Infotabellen-dicts auslesen und Vorlageneinträge zusammensetzen
    text_stats = ""
    text_info = ""
    for staat in staaten:
        
        # Fläche
        flaeche = None
        flaeche_int = None
        if "infobox" not in staat:
            print("Warnung - "+staat["uri"]+" hat keine Infobox")
            continue
        elif "Fläche" in staat["infobox"]:
            flaeche = parse_numbertoint(staat["infobox"]["Fläche"])
            flaeche_int = flaeche
            if flaeche is None:
                flaeche = unknown
            gesamt["flaeche"].append(flaeche)
        # Nicht in Infobox oder nicht parsebar
        if flaeche is None or flaeche == 0 or flaeche == unknown:
            flaeche = unknown
        else:
            flaeche = parse_numbertostring(flaeche)

        # BIP, BIP pro Kopf, EW
        ew_int = None
        if "infobox" in staat:
            n = parse_ew_bip(staat)
            if n["bip"] is None:
                bip = unknown
            else:
                bip = parse_numbertostring(n["bip"])

            if n["bip-ew"] is None:
                bip_ew = unknown
            else:
                bip_ew = parse_numbertostring(n["bip-ew"])

            if n["ew"] is None:
                ew = unknown
            else:
                ew = parse_numbertostring(n["ew"])
            ew_int = n["ew"]
            if n["bip"] is not None:
                gesamt["bip"].append(n["bip"])
            if n["ew"] is not None:
                gesamt["ew"].append(n["ew"])
        else:
            bip = unknown
            bip_ew = unknown
            ew = unknown
        if "infobox" not in staat:
            pass

        # EW pro Fläche
        if ew_int is not None and flaeche_int is not None:
            ew_flaeche = float(ew_int) / float(flaeche_int)
            ew_flaeche = parse_numbertostring(ew_flaeche)
        else:
            ew_flaeche = unknown

        # Währung
        if "Währung" in staat["infobox"]:
            waehrung = staat["infobox"]["Währung"]
            if waehrung is None:
                waehrung = unknown
            else:
                waehrung = normalize_waehrung2(waehrung, staat["uri"])
                if waehrung is None:
                    waehrung = unknown
                else:
                    d = {
                        "name": waehrung["name"],
                        "ew": ew_int,
                    }
                    gesamt["waehrung"].append(d)
                    waehrung = waehrung["string"]
        else:
            waehrung = unknown

        # Amtssprache
        sprache = normalize_sprache(staat["infobox"]["Amtssprache"])

        # TLD
        tld = normalize_tld(staat["infobox"]["TLD"])
        if tld is None or tld == "":
            tld = unknown

        # KFZ-Kennzeichen
        kfz = normalize_kfz(staat["infobox"]["KFZ"])

        # Vorwahl
        vorwahl = normalize_vorwahl(staat["infobox"]["Telefonvorwahl"])

        # Zeitzone
        zeitzone = normalize_zeitzone(staat["infobox"]["Zeitzone"])
        
        # Vorlagentext zusammensetzen: Statistik
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

        text_stats += eintrag

        # Vorlagentext zusammensetzen: Allgemeine Informationen
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

        text_info += eintrag

    # Allgemeine Statistiken
    pre = "<onlyinclude>{{IAS Anfang\n"
    pre += "|Jahr="+str(int(jahr))+"\n"

    flaeche_gesamt = 0
    for el in gesamt["flaeche"]:
        if el is not unknown:
            flaeche_gesamt += el
    flaeche_schnitt = flaeche_gesamt / len(gesamt["flaeche"])
    pre += "|Gesamt-Fläche=" + parse_numbertostring(flaeche_gesamt) + "\n"
    pre += "|Schnitt-Fläche=" + parse_numbertostring(flaeche_schnitt) + "\n"

    ew_gesamt = 0
    for el in gesamt["ew"]:
        ew_gesamt += el
    ew_schnitt = float(ew_gesamt) / float(len(gesamt["ew"]))
    pre += "|Gesamt-EW=" + parse_numbertostring(round(ew_gesamt)) + "\n"
    pre += "|Schnitt-EW=" + nice_floatstr(ew_schnitt) + "\n"

    bip_gesamt = 0
    for el in gesamt["bip"]:
        bip_gesamt += el
    bip_schnitt = bip_gesamt / len(gesamt["bip"])
    pre += "|Gesamt-BIP=" + parse_numbertostring(bip_gesamt) + "\n"
    pre += "|Schnitt-BIP=" + parse_numbertostring(bip_schnitt) + "\n"

    ew_fl_gesamt = float(ew_gesamt) / float(flaeche_gesamt)
    bip_ew_gesamt = float(bip_gesamt) / float(ew_gesamt)
    pre += "|EW-Fläche=" + nice_floatstr(ew_fl_gesamt) + "\n"
    pre += "|BIP-EW=" + parse_numbertostring(int(bip_ew_gesamt)) + "\n"

    # Währungen nach Anzahl Staaten
    erg = sum_up_waehrung(gesamt["waehrung"], lambda w: 1)
    pre += "|WährungSt1="+erg[2]["name"]+"\n"
    pre += "|WährungStAnz1=" + parse_numbertostring(erg[2]["anz"]) + "\n"
    pre += "|WährungSt2="+erg[1]["name"]+"\n"
    pre += "|WährungStAnz2=" + parse_numbertostring(erg[1]["anz"]) + "\n"
    pre += "|WährungSt3="+erg[0]["name"]+"\n"
    pre += "|WährungStAnz3=" + parse_numbertostring(erg[0]["anz"]) + "\n"

    # Währung nach EW
    erg = sum_up_waehrung(gesamt["waehrung"], lambda w: w["ew"])
    pre += "|WährungEw1="+erg[2]["name"]+"\n"
    pre += "|WährungEwAnz1=" + parse_numbertostring(erg[2]["anz"]) + "\n"
    pre += "|WährungEw2="+erg[1]["name"]+"\n"
    pre += "|WährungEwAnz2=" + parse_numbertostring(erg[1]["anz"]) + "\n"
    pre += "|WährungEw3="+erg[0]["name"]+"\n"
    pre += "|WährungEwAnz3=" + parse_numbertostring(erg[0]["anz"]) + "\n}}\n"

    # IAS Anfang Statistik und Tabber
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
    wiki.edit_article("Vorlage:IAS", text)

    # Staaten zählen
    bespielt = 0
    spielerlos = 0
    for staat in staaten:
        if staat["spielerlos"]:
            spielerlos += 1
        else:
            bespielt += 1
    
    # Vorlage:Anzahl Staaten
    text = "<onlyinclude><includeonly>" + str(len(staaten))
    text += "</includeonly></onlyinclude>\n"
    text += "Diese Vorlage gibt die aktuelle Anzahl der Staaten in Simocracy "
    text += "zurück. Gezählt werden alle Staaten des Planeten.<br>\nSie wird auf "
    text += "Basis der Staatenliste im [[Wikocracy:Portal|Portal]] berechnet.\n\n"
    text += "[[Kategorie:Fluggbot]]"
    wiki.edit_article("Vorlage:Anzahl_Staaten", text)

    # Vorlage:Anzahl Freie Staaten
    text = "<onlyinclude><includeonly>" + str(spielerlos)
    text += "</includeonly></onlyinclude>\n"
    text += "Diese Vorlage gibt die aktuelle Anzahl der freien Staaten in "
    text += "Simocracy zurück. Gezählt werden alle Staaten des Planeten.<br>\nSie "
    text += "wird auf Basis der Staatenliste im [[Wikocracy:Portal|Portal]] berechnet."
    text += "\n\n[[Kategorie:Fluggbot]]"
    wiki.edit_article("Vorlage:Anzahl_Freie_Staaten", text)

    # Vorlage:Anzahl Bespielte Staaten
    text = "<onlyinclude><includeonly>" + str(bespielt)
    text += "</includeonly></onlyinclude>\n"
    text += "Diese Vorlage gibt die aktuelle Anzahl der bespielten Staaten in "
    text += "Simocracy zurück.<br>\nSie wird auf Basis der Staatenliste im "
    text += "[[Wikocracy:Portal|Portal]] berechnet.\n\n[[Kategorie:Fluggbot]]"
    wiki.edit_article("Vorlage:Anzahl_Bespielte_Staaten", text)

    # Vorlage:Anzahl Spieler
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
            if el not in spielerliste:
                spielerliste.append(el)
        spielerliste = sorted(spielerliste, key=lambda s: s.lower())

    text = "<onlyinclude><includeonly>" + str(len(spielerliste))
    text += "</includeonly></onlyinclude>\n"
    text += "Diese Vorlage gibt die aktuelle Anzahl der aktiven Spieler "
    text += "in Simocracy zurück.<br>\nSie wird auf Basis der Staatenliste im "
    text += "[[Wikocracy:Portal|Portal]] berechnet.<br>\n===Derzeitige Spieler===\n"
    for spieler in spielerliste:
        text += spieler + "<br>\n"
    text += "\n[[Kategorie:Fluggbot]]"
    wiki.edit_article("Vorlage:Anzahl_Spieler", text)

if __name__ == "__main__":
    wiki.login()
    vz = wiki.read_vz()
    staaten = wiki.read_states(vz)
    update_article(staaten)
