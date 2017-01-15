#!/usr/bin/env python3.4

import urllib.request, urllib.parse, urllib.error
import http.cookiejar
import xml.etree.ElementTree as ET
import sys
import re
import simocracy.credentials as credentials

from enum import Enum
from simocracy.statemachine import StateMachine

username = None
password = None
try:
    import simocracy.credentials as credentials
    username = credentials.username
    password = credentials.password
except ImportError:
    pass

##############
### Config ###
#username = "USERNAME"
#password = "PASSWORD"

_url = 'https://simocracy.de/'
_vz = "Wikocracy:Portal"
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

#Flow Control für falls kein Template im Artikel gefunden wird
class NoTemplate(Exception):
    pass

class ConfigError(Exception):
    pass

"""
Geparste Vorlage in Artikel
"""
class Template:

    def __init__(self, article):
        self.article = article
        self.name = None
        self.values = {}
        
        #nested templates; list bestehend aus:
        #{"start":startcursor, "end":endcursor, "template":Template()}
        self.subtemplates = []
        
        #"anonyme" Werte in Vorlagen ({{Vorlage|Wert}})
        self.anonymous = 0
        
        #Setup State Machine
        self.fsm = StateMachine()
        self.fsm.addState("start", self.start_state)
        self.fsm.setStart("start")
        self.fsm.addState("name", self.name_state)
        self.fsm.addState("value", self.value_state)
        self.fsm.addState("end", None, end=True)
        self.fsm.addState("link", self.link_state)
        
        self.p_start = re.compile(r"\{\{")
        self.p_end = re.compile(r"\}\}")
        self.p_val = re.compile(r"\s*\|\s*([^=|}]*)\s*=?\s*([^|}]*)")
        self.p_linkstart = re.compile(r"\[\[")
        self.p_link = re.compile(r"\[\[(.*?)\]\]")
        self.p_slicer = re.compile(r"\|")
        #Marker für nächsten Abschnitt; dh Ende der Vorlage oder nächster Wert
        self.slicers = {
            self.p_end    : "end",
            self.p_slicer : "value",
            self.p_start  : "start",
            self.p_linkstart : "link",
        }
        
        self.fsm.run()
        
    def link_state(self):
        print("cursor: "+str(self.article.cursor))
        raise Exception("link state")
        
    """
    State Machine Handlers
    """
    """Start bzw. bisher keine Vorlage gefunden"""
    def start_state(self):
        start = self.p_start.search(self.article.line)
        if not start:
            try:
                self.article.__next__()
            except StopIteration:
                raise NoTemplate()
            return "start"
            
        cursor = { "line" : self.article.cursor["line"] }
        cursor["char"] = start.span()[1] + self.article.cursor["char"]
        self.article.cursor = cursor
        return "name"
        
        
    """Name der Vorlage"""
    def name_state(self):
        line = self.article.line
        newState = None
        
        #Hinteren Vorlagenkram abhacken
        startCursor = self.article.cursor
        for slicer in self.slicers:
            match = slicer.search(line)
            if not match:
                continue
            
            line = line[:match.span()[0]]
            self.article.cursor = match.span()[1] + startCursor["char"]
            newState = self.slicers[slicer]
            
        #TODO
        #if self.slicers[slicer] == "start":
        #    raise Exception("template in template name: " + line.rstrip('\n'))
                
        line = line.strip()
        if line == "":
            return "name"
            
        self.name = line.strip()
        
        if newState:
            return newState
            
        #Nächsten Status in nächster Zeile suchen
        newState = None
        while True:
            try:
                line = self.article.__next__()
            except StopIteration:
                raise NoTemplate()

            span = [len(line)+1, len(line)+1]                
            for slicer in self.slicers:
                match = slicer.search(line)
                if not match:
                    continue
                if not match.span()[0] < span[0]:
                    continue

                span = match.span()
                newState = self.slicers[slicer]

                #TODO
                #template name over multiple lines

            if newState:
                c = self.article.cursor["char"] + span[1]
                self.article.cursor = c
                return newState
                
    
    """Vorlageneintrag /-wert; sucht über mehrere Zeilen hinweg"""
    def value_state(self):
        #hinteren Kram abhacken; mehrere Zeilen zusammensammeln
        newState = "continue"
        value = ""
        while True:
            line = self.article.line
            span = None
            for slicer in self.slicers:
                match = slicer.search(line)
                if not match:
                    continue
            
                newState = self.slicers[slicer]
                span = match.span()
                line = line[:span[0]]
                
            value += line
            
            #link parsen [[ ... ]]
            if newState is "link":
                cursor = self.article.cursor
                self.article.cursor = cursor["char"] + span[0]
                del(cursor)
                m = self.p_link.match(self.article.line)
                endCursor = None
                asString = None
                
                #Angetäuschtes [[ ohne Link
                if m is None:
                    endCursor = self.article.cursor
                    endCursor["char"] += 2
                    asString = "[["
                #Echter Link
                else:
                    endCursor = self.article.cursor
                    endCursor["char"] += m.span()[1]
                    asString = self.article.extract(self.article.cursor,endCursor)
                    
                value += asString
                self.article.cursor = endCursor
                
                newState = "continue"
                continue
            
            #nested template
            elif newState is "start":
                cursor = self.article.cursor
                cursor["char"] += span[0]
                self.article.cursor = cursor
                
                template = Template(self.article)
                subt = {"startcursor" : cursor,
                        "template" : template,
                        "endcursor" : self.article.cursor}
                self.subtemplates.append(subt)
                
                asString = self.article.extract(cursor, subt["endcursor"])
                value += asString
                self.article.cursor = subt["endcursor"]
                
                newState = "continue"
                continue
            
            #v.a. Cursor setzen
            elif newState is not "continue":
                self.article.cursor = span[1] + self.article.cursor["char"]
                break
                
            try:
                line = self.article.__next__()
                value += "\n"
            except StopIteration:
                raise NoTemplate()
                
        #value parsen
        split = value.split("=")
        if len(split) > 1:
            value = split[1]
            #mögliche weitere = in value abfangen
            for el in range(2, len(split)):
                value += "=" + split[el]
                
            key = split[0]
            if "{{" in key:
                raise Exception("template in key: "+key)
            self.values[key] = value.strip()
            
        #anonyme values
        else:
            key = 1
            while True:
                if key in self.values:
                    key += 1
                else:
                    break
                    
            self.values[key] = split[0].strip()
            
        return newState
                
            
            

"""
Artikelklasse; iterierbar über Zeilen
"""
class Article:
    """
    Öffnet einen Wikiartikel; löst insb. Redirections auf.
    name: Artikelname
    """
    def __init__(self, name, redirect=True):
        self.title = None
        self.templates = None
        self.text = []
        self._cursor = { "line":-1, "char":0, "modified":False }
        
        qry = "api.php?format=xml&action=query&titles="
        qry = _url + qry + urllib.parse.quote(name)
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

        error = article.find("error")
        if error:
            msg = error.attrib["code"] + ": "
            msg += error.attrib["info"]
            raise Exception(msg)

        self.title = article.find("page").attrib["title"]
        print("Öffne " + self.title)
        site = None
        try:
            qry = _url+urllib.parse.quote(self.title) + "?action=raw"
            site = opener.open(qry)
        except urllib.error.HTTPError:
            raise Exception("404: " + self.title)
            
        for line in site.readlines():
            self.text.append(line.decode('utf-8'))
            
    """
    Cursor-Definition
    { "line":line, "char":char, "modified":True|False }
    """
    @property
    def cursor(self):
        return self._cursor.copy()
       
    #value kann vollständiger Cursor oder nur char sein
    @cursor.setter
    def cursor(self, value):
        #vollständiger Cursor übergeben
        try:
            self._cursor = { 
                "line" : value["line"] + 0,
                "char" : value["char"] + 0,
                "modified" : True,
            }
        except:
            #nur char übergeben
            try:
                self._cursor = {
                    "line" : self._cursor["line"],
                    "char" : value + 0,
                    "modified" : True,
                }
            except:
                raise Exception("invalid cursor: " + str(value))
        
    def resetCursor(self):
        self._cursor = { "line":-1, "char":0, "modified":False }
        
    """
    Gibt den Teil zwischen den Cursorn start und end zurück;
    alle Zeilen aneinandergehängt und mit \n getrennt
    """
    def extract(self, start, end):
        #Nur eine Zeile
        if start["line"] == end["line"]:
            return self.text[start["line"]][start["char"]:end["char"]]
        
        r = ""
        for i in range(start["line"], end["line"] + 1):
            #Anfangszeile
            if i == start["line"]:
                r += self.text[i][start["char"]:] + "\n"
            #Endzeile
            elif i == end["line"]:
                return r + self.text[i][:end["char"]]
                
            else:
                r += self.text[i] + "\n"
                
        #Sollte eigentlich nicht auftreten, da return in Endzeile
        raise RuntimeError()
            
    """
    Iterator-Stuff
    """
    def __iter__(self):
        return self
        
    """
    Berücksichtigt manuell geänderte Cursor.
    """
    def __next__(self):
        if self._cursor["modified"]:
            self._cursor["modified"] = False
        #else:
        self._cursor["line"] += 1
        self._cursor["char"] = 0
            
        try:
            line = self.text[self._cursor["line"]]
        except IndexError:
            raise StopIteration
            
        line = line[self._cursor["char"]:]
            
        return line
        
    @property
    def line(self):
        return self.text[self._cursor["line"]][self._cursor["char"]:]
        
    class TState(Enum):
        nothing = 1
        name = 2
        value = 3
                
            
    """
    Parst alle Vorlagen im Artikel text und gibt ein dict zurueck.
    Setzt den Cursor zurück.
    """
    def parseTemplates(self):
        self.templates = []
        self.resetCursor()
        while True:
            try:
                self.templates.append(Template(self))
            except NoTemplate:
                break
                

"""
Loggt den User ins Wiki ein.
"""
def login():
    #Config Check
    if username is None or password is None:
        raise ConfigError("username or password not given")

    global opener

    #Ersten Request zusammensetzen, der das Login-Token einsammelt
    query_args = { 'lgname':username, 'lgpassword':password }
    qry_args = urllib.parse.urlencode(query_args).encode('utf-8')
    qry = _url + 'api.php?format=xml&action=login'
    c = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(c))
    response = opener.open(qry, qry_args)

    #Token aus xml extrahieren
    response.readline() #Leerzeile überspringen
    xmlRoot = ET.fromstring(response.readline())
    lgToken = xmlRoot.find('login').attrib['token']
    session = xmlRoot.find('login').attrib['sessionid']

    #Zweiter Request mit Login-Token
    query_args.update({'lgtoken':lgToken})
    data = urllib.parse.urlencode(query_args).encode('utf-8')
    response = opener.open(_url+'api.php?format=xml&action=login', data)

    #Login-Status; ggf. abbrechen
    response.readline() #Leerzeile überspringen
    xmlRoot = ET.fromstring(response.readline())
    result = xmlRoot.find('login').attrib['result']

    if result != "Success":
        raise Exception("Login: " + result)
    else:
        print(("Login: " + result))


"""
Generator für Namen aller Wikiseiten
"""
def allPages(resume=None):
    qry = _url+'api.php?action=query&list=allpages&aplimit=5000&format=xml'
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
def readVZ():
    article = Article(_vz)

    if not article:
        raise Exception("übergebene Seite leer")
    text = []
    for line in article:
        text.append(line)
    del article
        
    """
    Staaten
    """
    # "|Staaten=" suchen
    i = 0
    found = False
    while True:
        if re.match('^\s*|\s*Staaten\s*=\s*', text[i]):
            i += 1
            found = True
            break
        i += 1
    if not found:
        raise Exception("|Staaten= nicht gefunden.")
    found = False
    
    # erstes "{{!}}-" suchen
    while True:
        if text[i].startswith('{{!}}-'):
            found = True
            i += 1
            break
        i += 1
    if not found:
        raise Exception("Staatentabellenheader nicht gefunden.")
    found = False
    
    # zweites "{{!}}-" suchen
    while True:
        if text[i].startswith('{{!}}-'):
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
        if text[i].startswith('{{!}}}'):
            i += 1
            break
        #Tabelleneintrag
        if not text[i].startswith('{{!}}'):
            i += 1
            continue
        
        #Datensatz zuende
        if text[i].startswith('{{!}}-'):
            if entryCtr == 5:
                staaten.append(dict.copy())
                dict.clear()
            i += 1
            entryCtr = 0
            continue
            
        key = ""
        value = text[i].strip()
        
        #Ins dict eintragen; evtl value korrigieren
        if entryCtr == 0:
            value = value.replace('{{!}}', '').strip()
            #try:
            #    dict["flagge"] = extractFlag(value)
            #except:
            #    raise Exception("fehler bei Flaggencode "+value)
            
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
        line = text[i]
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
        line = text[i]
        #Tabellenende
        if line.startswith("|") or i >= len(text):
            break
        if eintrag_p.match(line) is not None:
            tokens = re.split(eintrag_p, line)
            #dict["flagge"] = extractFlag(tokens[1])
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
        line = text[i]
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
        line = text[i]
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
Liest die Infotabellen aller Staaten aus
"""
def readStates(vz):
    print("Lese Portal ein")

    staaten = []
    for staat in vz["staaten"]:
        staat['spielerlos'] = False
        staaten.append(staat)
    for staat in vz["spielerlos"]:
        staat["spielerlos"] = True
        staaten.append(staat)

    staaten = sorted(staaten, key=lambda k: k["sortname"])

    print("Lese Infoboxen ein")
    for staat in staaten:
        article = Article(staat["uri"])
        article.parseTemplates()
        infobox = None
        for t in article.templates:
            if t.name == "Infobox Staat":
                infobox = t.values
                continue

        if infobox is None:
            print("Keine Infobox: "+staat["uri"])
            continue

        for key in infobox:
            infobox[key] = globalizeLinks(infobox[key], staat["uri"])
        if not infobox == None:
            staat["infobox"] = infobox
        #Stellt sicher, dass jeder Staat eine Infobox hat
        else:
            s = "Warnung: "+staat["uri"]+" hat keine Infobox Staat"
            print(s, file=sys.stderr)
            continue

    return staaten
    

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
    #html-Kommentar rauswerfen
    p = re.compile(r'<!--[^>]*-->')
    flagcode = p.sub("",flagcode)

    #Flaggenvorlage
    if re.match(r'\{\{', flagcode) is not None:
        #flagcode.replace(r"{{", "")
        #flagcode.replace(r"|40}}", "")
        mitPx_p = re.compile(r'\{\{(.+?)\|[^}]*\}\}')
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
            response = Article("Vorlage:" + flagcode)
        except:
            raise Exception("konnte nicht öffnen: "+flagcode)
        text = []

        for line in response:
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
        raise Exception(flagcode + " keine gültige Flagge")
    
    #Bild-URL extrahieren
    flagcode = urllib.parse.quote(flagcode.strip().replace(' ', '_'))
    response = opener.open(_url + 'api.php?titles=Datei:'+flagcode+'&format=xml&action=query&prop=imageinfo&iiprop=url')
    response.readline() #Leerzeile ueberspringen
    xmlRoot = ET.fromstring(response.readline())
    
    for element in xmlRoot.iterfind('query/pages/page/imageinfo/ii'):
        return element.attrib['url']


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
    response = opener.open(_url + 'api.php?action=query&format=xml&titles=' + urllib.parse.quote(article) + '&meta=tokens')
    #return response
    response.readline()
    xmlRoot = ET.fromstring(response.readline())
    editToken = xmlRoot.find('query').find('tokens').attrib['csrftoken']
    
    #Seite bearbeiten
    query_args = { 'text':text, 'token':editToken }
    query_url = _url + 'api.php?action=edit&bot&format=xml&title=' + urllib.parse.quote(article)
    response = opener.open(query_url, urllib.parse.urlencode(query_args).encode('utf8'))

    #Result auslesen
    return response
    response.readline()
    xmlRoot = ET.fromstring(response.readline())
    if xml.find('edit').attrib['result'] != 'Success':
        raise Exception('edit not successful')


def buildQuery(args):
    qry = "?"
    for arg in args:
        if qry == "?":
            qry += arg
        else:
            qry += "&"+arg
    return qry + "&format=xml&action=query"


"""
Schickt das Query bestehend aus *args ans Wiki.
format=xml und action=query muss nicht angegeben werden.
Gibt den xml-elementtree der Antwort zurück.
Beispiel: sendQuery("titles=Flugghingen","redirects")
"""
def sendQuery(*args):
    qry = buildQuery(args)
    print(qry)
    response = opener.open(_url+"api.php"+qry)
    l = response.readline()
    l = response.readline()
    return ET.fromstring(l)
    
