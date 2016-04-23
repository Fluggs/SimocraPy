#!/usr/bin/python
# -*- coding: UTF-8 -*-

import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import http.cookiejar
import xml.etree.ElementTree as ET
import re
import simocracy.credentials as credentials

##############
### Config ###
username = credentials.username
password = credentials.password

url = 'https://simocracy.de/'
vz = "Wikocracy:Portal"
sortprefixes = [
    'Königreich',
    'Republik',
    'Bundesrepublik',
    'Föderation',
    'Reich',
    'Heiliger',
    'Heilige',
    'Hl.',
]

imageKeywords = [
    'File:',
    'file:',
    'Image:',
    'image:',
    'Datei:',
    'datei:',
    'Bild:',
    'bild:',
]
##############

opener = None

"""
Artikelklasse; iterierbar über Zeilen
"""
class Article:
    def __init__(self, name):
        pass

"""
Wird von parseTemplate geworfen, wenn die Vorlage
nicht im Artikel ist
"""
class NoSuchTemplate(Exception):
    pass

"""
Loggt den User ins Wiki ein.
"""
def login():
    global opener

    #Ersten Request zusammensetzen, der das Login-Token einsammelt
    query_args = { 'lgname':username, 'lgpassword':password }
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    response = opener.open(url + 'api.php?format=xml&action=login', urllib.parse.urlencode(query_args).encode('utf8'))

    #Token aus xml extrahieren
    response.readline() #Leerzeile überspringen
    xmlRoot = ET.fromstring(response.readline())
    lgToken = xmlRoot.find('login').attrib['token']
    session = xmlRoot.find('login').attrib['sessionid']

    #Zweiter Request mit Login-Token
    query_args.update({'lgtoken':lgToken})
    data = urllib.parse.urlencode(query_args)
    response = opener.open(url+'api.php?format=xml&action=login', data.encode('utf8'))

    #Login-Status; ggf. abbrechen
    response.readline() #Leerzeile überspringen
    xmlRoot = ET.fromstring(response.readline())
    result = xmlRoot.find('login').attrib['result']

    if result != "Success":
        raise Exception("Login: " + result)
    else:
        print(("Login: " + result))


"""
Generator für alle Wikiseiten
"""
def allPages(resume=None):
    qry = url+'api.php?action=query&list=allpages&aplimit=5000&format=xml'
    if resume:
        qry = qry + "&apfrom=" + resume
    response = opener.open(qry)

    #Leerzeile ueberspringen
    response.readline()

    #XML einlesen
    xml = ET.fromstring(response.readline())

    for page in xml.iter('p'):
        yield page.attrib['title']

"""
Liest Staaten und Bündnisse aus dem
Verzeichnis-Seitentext site aus und packt sie in ein dict.
Keys: staaten, buendnisse

staaten: Liste aus dicts; keys:
nummer
flagge (bild-URL)
name
uri (Artikelname)
buendnis (flaggen-URL)
ms
as
spieler
zweitstaat

buendnisse: array aus dicts; keys:
    flagge
    name
    
zB Zugriff auf Staatenname: r["staaten"][0]["name"]
"""
def readVZ(site):

    if not site:
        raise Exception("übergebene Seite leer")
    text = []
    for line in site:
        text.append(line)
    del site
        
    """
    Staaten
    """
    # "|Staaten=" suchen
    i = 0
    found = False
    while True:
        if re.match(b'^\s*|\s*Staaten\s*=\s*', text[i]):
            i += 1
            found = True
            break
        i += 1
    if not found:
        raise Exception("|Staaten= nicht gefunden.")
    found = False
    
    # erstes "{{!}}-" suchen
    while True:
        if text[i].startswith(b'{{!}}-'):
            found = True
            i += 1
            break
        i += 1
    if not found:
        raise Exception("Staatentabellenheader nicht gefunden.")
    found = False
    
    # zweites "{{!}}-" suchen
    while True:
        if text[i].startswith(b'{{!}}-'):
            found = True
            i += 1
            break
        i += 1
    if not found:
        raise Exception("Staatentabelleninhalt nicht gefunden.")
    found = False
    
    #Tabelle parsen
    entryCtr = 0
    dict = {}
    staaten = []
    #gegen highlightbug X_x
    ta = "'" + "'" + "'"
    name_p = re.compile(r'\{\{!\}\}\s*'+ta+'\s*(\[\[[^]]*\]\])\s*'+ta+'\s*<br>\s*(.*)')
    flagge_p = re.compile(r'\{\{!\}\}\s*(\[\[[^]]*\]\])\s*')
    zahl_p = re.compile(r'\{\{!\}\}\s*(\(*[\d-]*\)*)\s*')
    while True:
        #Tabellenende
        if text[i].startswith(b'{{!}}}'):
            i += 1
            break
        #Tabelleneintrag
        if not text[i].startswith(b'{{!}}'):
            i += 1
            continue
        
        #Datensatz zuende
        if text[i].startswith(b'{{!}}-'):
            if entryCtr == 5:
                staaten.append(dict.copy())
                dict.clear()
            i += 1
            entryCtr = 0
            continue
            
        key = ""
        value = text[i].strip().decode('utf-8')
        
        #Ins dict eintragen; evtl value korrigieren
        if entryCtr == 0:
            value = value.replace('{{!}}', '').strip()
            try:
                dict["flagge"] = extractFlag(value)
            except:
                raise Exception("fehler bei Flaggencode "+value)
            
        elif entryCtr == 1:
            tokens = re.split(name_p, value)
            names = getStateNames(tokens[1])
            dict["name"] = names["name"]
            dict["uri"] = names["uri"]
            dict["sortname"] = names["sortname"]


            #Spielername
            dict["spieler"] = tokens[2].replace('[[', '').replace(']]', '')
            
        elif entryCtr == 2:
            try:
                value = re.split(flagge_p, value)[1]
                dict["buendnis"] = extractFlag(value)
            except:
                dict["buendnis"] = ""
            
        elif entryCtr == 3:
            ms = re.split(zahl_p, value)[1]
            #Zweitstaat
            if ms.startswith('('):
                ms = ms.replace('(', '').replace(')', '')
                dict["zweitstaat"] = True
            else:
                dict["zweitstaat"] = False
            dict["ms"] = ms
            
        elif entryCtr == 4:
            bomben = re.split(zahl_p, value)[1]
            if bomben == '-':
                bomben = '0'
            dict["as"] = bomben
            
        entryCtr += 1
        i += 1
        
        if i == len(text):
            break

    """
    Spielerlose Staaten
    """
    #"|Spielerlose_Staaten=" suchen
    found = False
    while True:
        line = text[i].decode('utf-8')
        if i >= len(text):
            break
        if re.match(r'\s*\|\s*Spielerlose_Staaten\s*=', line) is not None:
            i += 1
            found = True
            break
        i += 1
    if not found:
        raise Exception("|Spielerlose_Staaten= nicht gefunden.")

    #Tabelle parsen
    eintrag_p = re.compile(r'\*(\{\{[^\}]+\}\})\s*(\[\[[^]]+\]\])')
    dict = {}
    spielerlos = []
    while True:
        line = text[i].decode('utf-8')
        #Tabellenende
        if line.startswith("|") or i >= len(text):
            break
        if eintrag_p.match(line) is not None:
            tokens = re.split(eintrag_p, line)
            dict["flagge"] = extractFlag(tokens[1])
            names = getStateNames(tokens[2])
            dict["uri"] = names["uri"]
            dict["name"] = names["name"]
            dict["sortname"] = names["sortname"]
            spielerlos.append(dict.copy())
            dict.clear()
            i += 1
            continue
        i += 1
    
    """
    Bündnisse
    """
    #"|Militärbündnisse" suchen
    found = False
    while True:
        line = text[i].decode('utf-8')
        if i >= len(text):
            break
        if re.match(r'^\s*|\s*Milit', line) is not None and re.search(r'ndnisse\s*=\s*$', line) is not None:
            i += 1
            found = True
            break
        i += 1
    if not found:
        raise Exception("|Militärbündnisse= nicht gefunden.")
    found = False
    
    #Tabelle parsen
    entryCtr = 0
    dict = {}
    bnds = []
    bndeintrag_p = re.compile(r'\*\s*(\[\[[^]]*\]\])\s*\[\[([^]]*)\]\]')
    while True:
        line = text[i].decode('utf-8')
        #Tabellenende
        if line.startswith('{{!}}'):
            i += 1
            break
        #Tabelleneintrag
        if bndeintrag_p.match(line) is not None:
            tokens = re.split(bndeintrag_p, line)
            dict["flagge"] = extractFlag(tokens[1]).strip()
            dict["name"] = tokens[2].split("|")[0].strip()
            bnds.append(dict.copy())
            dict.clear()
            i += 1
            continue

        i += 1
        
        if i == len(text):
            break
    
    return {
            "staaten": sorted(staaten, key=lambda k: k['sortname']),
            "buendnisse":bnds,
            "spielerlos": sorted(spielerlos, key=lambda k: k['uri']),
    }

"""
Nimmt einen Wikilink der Form [[x|y]] oder [[x]] und
liefert Staatsname, Staats-URI und Sortierkey zurück:
{ "name":name, "uri":uri, "sortname":sortname }
"""
def getStateNames(wikilink):
    name_p = re.compile(r'\[\[([^]]*)\]\]')

    r = {}
    #Staatsname
    tokens = re.split(name_p, wikilink)
    values = tokens[1].split("|")
    name = values[len(values) - 1]
    name = name.strip()
    r["name"] = name

    #URI; fuer [[x|y]]
    r["uri"] = values[0].strip()

    #Name für Sortierung
    sortkey = name
    for el in sortprefixes:
        if sortkey.startswith(el+' '):
            sortkey = sortkey.replace(el, '')
            sortkey = sortkey.strip()
    r["sortname"] = sortkey
    return r
    
"""
Extrahiert den Dateinamen der Flagge
aus der Flaggeneinbindung flagcode.
"""
def extractFlag(flagcode):
    #Flaggenvorlage
    if re.match(r'\{\{', flagcode) is not None:
        #flagcode.replace(r"{{", "")
        #flagcode.replace(r"|40}}", "")
        mitPx_p = re.compile(r'\{\{(.+?)\|\d*\}\}')
        ohnePx_p = re.compile(r'\{\{(.+?)\}\}')
        pattern = None
        if mitPx_p.match(flagcode):
            pattern = mitPx_p
        elif ohnePx_p.match(flagcode):
            pattern = ohnePx_p
        else:
            raise Exception(flagcode + " unbekannter Flaggencode")

        flagcode = re.split(pattern, flagcode)[1]
        
        #Vorlage herunterladen
        try:
            response = openArticle("Vorlage:" + flagcode)
        except:
            raise Exception("konnte nicht öffnen: "+flagcode)
        text = []

        for line in response:
            line = line.decode('utf-8')
            if re.search(r'include>', line):
                break
        
        #Regex
        for el in imageKeywords:
            line = line.replace(el, '')
        pattern = re.compile(r"\[\[(.+?)\|.+?\]\]")
        flagcode = re.findall(pattern, line)[0]

    #Normale Bildeinbindung
    elif re.match(r'\[\[', flagcode) is not None:
        flagcode = flagcode.replace('[[', '')
        flagcode = flagcode.replace(']]', '')
        for el in imageKeywords:
            flagcode = flagcode.replace(el, '')
        values = flagcode.split('|')
        flagcode = values[0]
    #kaputt
    else:
        raise Exception(value + " keine gültige Flagge")
    
    #Bild-URL extrahieren
    flagcode = urllib.parse.quote(flagcode.strip().replace(' ', '_'))
    response = opener.open(url + 'api.php?titles=Datei:'+flagcode+'&format=xml&action=query&prop=imageinfo&iiprop=url')
    response.readline() #Leerzeile ueberspringen
    xmlRoot = ET.fromstring(response.readline())
    
    for element in xmlRoot.iterfind('query/pages/page/imageinfo/ii'):
        return element.attrib['url']


"""
Oeffnet einen Wikiartikel; loest insb. Redirections auf.
Gibt ein "file-like object" (doc)  zurueck.
article: Artikelname
"""
def openArticle(article, redirect=True):
    qry = url + "api.php?format=xml&action=query&titles=" + urllib.parse.quote(article)
    if redirect:
        qry = qry + "&redirects"
    response = opener.open(qry)
    
    #Leerzeile ueberspringen
    response.readline()

    #XML einlesen
    xml = ET.fromstring(response.readline())

    article = xml.find("query").find("pages")
    #Spezialseiten abfangen (z.B. Hochladen)
    if not article:
        raise Exception("Spezialseite")

    article = article.find("page").attrib["title"]
    print("Öffne " + article)
    try:
        return opener.open(url + urllib.parse.quote(article) + "?action=raw")
    except urllib.error.HTTPError:
        raise Exception("404: " + article)


"""
Parst das erste Vorkommnis der Vorlage template im Artikel text
und gibt ein dict zurueck.
"""
def parseTemplate(template, site):
    dict = {}
    #Anfang der Vorlage suchen
    pattern = re.compile(r"\s*\{\{\s*"+re.escape(template)+"\s*$", re.IGNORECASE)
    found = False
    for line in site:
        line = line.decode('utf8')
        if pattern.search(line) is not None:
            found = True
            break

    if not found:
        raise NoSuchTemplate(template + " in " + site)

    pattern = re.compile(r"^\s*\|\s*([^=]*)\s*=\s*(.+)\s*$")
    pattern_end = re.compile(r"\}\}")
    pattern_start = re.compile(r"\{\{")
    templateCounter = 0

    for line in site:
        line = line.decode('utf-8')
        if pattern_end.search(line):
            templateCounter += 1
        if pattern_end.search(line):
            #Vorlage template zuende
            if templateCounter == 0:
                if dict == {}:
                    return None #?!
                return dict
            #Irgendeine andere Vorlage geht zuende
            else:
                templateCounter -= 1
        if pattern.match(line) is not None:
            kvPair = re.findall(pattern, line)
            value = kvPair[0][1]
            if re.match(r'<!--(.*?)-->$', value):
                continue
            else:
                dict[kvPair[0][0]] = value
                print(kvPair[0][0] + " = " + value)


"""
Macht alle lokalen Links in s global.
Nimmt article als Artikelnamen für die lokalen Links an.
Berücksichtigt auch Dateilinks, z.B.
[[Datei:file.png|30px|link=#whatever]]
"""
def globalizeLinks(s, article):
    links = parseLinks(s)
    for link in links:
        toRepl = buildLink(link)

        if link["uri"].startswith("#"):
            link["uri"] = article + link["uri"]
        #Datei
        if "filelink" in link and link["filelink"].startswith("#"):
            link["filelink"] = article + link["filelink"]

        newLink = buildLink(link)
        s = s.replace(toRepl, newLink)
        """
        split = re.split(re.escape(newLink), s)
        s = split[0]
        for i in range(1, len(split)):
            s = newLink + split[i]
        """

    return s

"""
Gibt alle Wikilinks ([[ ... ]] im String s als Liste von dicts zurück:

Zwingend vorhanden:
"uri":<Ziel des Links>
"file":boolescher Wert; gibt an ob Link eine Datei ist

Vorhanden, falls im Link vorhanden:
"filelink":<Link der "belinkten" Datei (|link=<filelink>)>
"name":<name des Links bzw. Größenangabe der Datei>
"""
def parseLinks(s):
    e = re.findall(r"\[\[(.*?)\]\]", s)
    r = []
    for el in e:
        split = re.split("\|", el)
        dict = {}
        dict["uri"] = split[0]
        if len(split) > 1:
            if not split[1].startswith("link="):
                dict["name"] = split[1]

        #File check
        dict["file"] = False
        for el in imageKeywords:
            if dict["uri"].startswith(el):
                dict["file"] = True
                break

        #File link
        if dict["file"] and len(split) > 1:
            for i in range(1, len(split)):
                if split[i].startswith("link="):
                    link = split[i].replace("link=", "")
                    dict["filelink"] = link
                    break

        r.append(dict)

    return r

"""
Baut einen Link-String aus einem dict wie in parseLinks() zusammen.
"""
def buildLink(link):
    r = "[[" + link["uri"]
    if "name" in link:
        r += "|" + link["name"]

    if link["file"] and "filelink" in link:
        r += "|link=" + link["filelink"]

    return r + "]]"

"""
Ersetzt alle Wikilinks im String s durch den Namen des Links,
d.h. entfernt alle Wikilinks.
"""
def removeLinks(s):
    p = re.compile(r"\[\[.*?\]\]")

    #schrittweise jeden Links entfernen
    while True:
        link = p.search(s)
        if link is None:
            break
        link = link.group()

        parsedLink = parseLinks(link)[0]
        toDel = re.split(parsedLink["name"], link)
        for el in toDel:
            s = re.sub(re.escape(el), "", s, count=1)

    return s

"""
Schreibt den Text text in den Artikel article.
"""
def editArticle(article, text):
    print("Bearbeite "+article)

    #Edit-Token lesen
    response = opener.open(url + 'api.php?action=query&format=xml&titles=' + urllib.parse.quote(article) + '&meta=tokens')
    #return response
    response.readline()
    xmlRoot = ET.fromstring(response.readline())
    editToken = xmlRoot.find('query').find('tokens').attrib['csrftoken']
    
    #Seite bearbeiten
    query_args = { 'text':text, 'token':editToken }
    query_url = url + 'api.php?action=edit&bot&format=xml&title=' + urllib.parse.quote(article)
    response = opener.open(query_url, urllib.parse.urlencode(query_args).encode('utf8'))

    #Result auslesen
    return response
    response.readline()
    xmlRoot = ET.fromstring(response.readline())
    if xml.find('edit').attrib['result'] != 'Success':
        raise Exception('edit not successful')
