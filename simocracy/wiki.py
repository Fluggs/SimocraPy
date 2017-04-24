#!/usr/bin/env python3.4

import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import xml.etree.ElementTree as ET
import sys
import re
import os

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

############
# Config ###
# username = "USERNAME"
# password = "PASSWORD"

_url = 'https://simocracy.de/'
_vz = "Wikocracy:Portal"
sort_prefixes = [
    'Königreich',
    'Republik',
    'Bundesrepublik',
    'Föderation',
    'Freistaat',
    'Reich',
    'Heiliger',
    'Heilige',
    'Hl.',
]

image_keywords = [
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


# Flow Control für falls kein Template im Artikel gefunden wird
class NoTemplate(Exception):
    pass


class ConfigError(Exception):
    pass


class Template:
    """
    Geparste Vorlage in Artikel
    """

    def __init__(self, article):
        self.article = article
        self.name = None
        self.values = {}
        
        # nested templates; list bestehend aus:
        # {"start":startcursor, "end":endcursor, "template":Template()}
        self.subtemplates = []
        
        # "anonyme" Werte in Vorlagen ({{Vorlage|Wert}})
        self.anonymous = 0
        
        # Setup State Machine
        self.fsm = StateMachine()
        self.fsm.add_state("start", self.start_state)
        self.fsm.set_start("start")
        self.fsm.add_state("name", self.name_state)
        self.fsm.add_state("value", self.value_state)
        self.fsm.add_state("end", None, end=True)
        self.fsm.add_state("link", self.link_state)
        
        self.p_start = re.compile(r"\{\{")
        self.p_end = re.compile(r"\}\}")
        self.p_val = re.compile(r"\s*\|\s*([^=|}]*)\s*=?\s*([^|}]*)")
        self.p_linkstart = re.compile(r"\[\[")
        self.p_link = re.compile(r"\[\[(.*?)\]\]")
        self.p_slicer = re.compile(r"\|")
        # Marker für nächsten Abschnitt; dh Ende der Vorlage oder nächster Wert
        self.slicers = {
            self.p_end:       "end",
            self.p_slicer:    "value",
            self.p_start:     "start",
            self.p_linkstart: "link",
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
            
        cursor = {"line": self.article.cursor["line"]}
        cursor["char"] = start.span()[1] + self.article.cursor["char"]
        self.article.cursor = cursor
        return "name"

    def name_state(self):
        """Name der Vorlage"""
        line = self.article.line
        new_state = None
        
        # Hinteren Vorlagenkram abhacken
        start_cursor = self.article.cursor
        for slicer in self.slicers:
            match = slicer.search(line)
            if not match:
                continue
            
            line = line[:match.span()[0]]
            self.article.cursor = match.span()[1] + start_cursor["char"]
            new_state = self.slicers[slicer]
            
        # TODO
        # if self.slicers[slicer] == "start":
        #     raise Exception("template in template name: " + line.rstrip('\n'))
                
        line = line.strip()
        if line == "":
            return "name"
            
        self.name = line.strip()
        
        if new_state:
            return new_state
            
        # Nächsten Status in nächster Zeile suchen
        new_state = None
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
                new_state = self.slicers[slicer]

                # TODO
                # template name over multiple lines

            if new_state:
                c = self.article.cursor["char"] + span[1]
                self.article.cursor = c
                return new_state

    def value_state(self):
        """Vorlageneintrag /-wert; sucht über mehrere Zeilen hinweg"""
        # hinteren Kram abhacken; mehrere Zeilen zusammensammeln
        new_state = "continue"
        value = ""
        while True:
            line = self.article.line
            span = None
            for slicer in self.slicers:
                match = slicer.search(line)
                if not match:
                    continue
            
                new_state = self.slicers[slicer]
                span = match.span()
                line = line[:span[0]]
                
            value += line
            
            # link parsen [[ ... ]]
            if new_state is "link":
                cursor = self.article.cursor
                self.article.cursor = cursor["char"] + span[0]
                del cursor
                m = self.p_link.match(self.article.line)
                
                # Angetäuschtes [[ ohne Link
                if m is None:
                    end_cursor = self.article.cursor
                    end_cursor["char"] += 2
                    as_string = "[["
                # Echter Link
                else:
                    end_cursor = self.article.cursor
                    end_cursor["char"] += m.span()[1]
                    as_string = self.article.extract(self.article.cursor, end_cursor)
                    
                value += as_string
                self.article.cursor = end_cursor
                
                new_state = "continue"
                continue
            
            # nested template
            elif new_state is "start":
                cursor = self.article.cursor
                cursor["char"] += span[0]
                self.article.cursor = cursor
                
                template = Template(self.article)
                subt = {"startcursor": cursor,
                        "template": template,
                        "endcursor": self.article.cursor}
                self.subtemplates.append(subt)
                
                as_string = self.article.extract(cursor, subt["endcursor"])
                value += as_string
                self.article.cursor = subt["endcursor"]
                
                new_state = "continue"
                continue
            
            # v.a. Cursor setzen
            elif new_state is not "continue":
                self.article.cursor = span[1] + self.article.cursor["char"]
                break
                
            try:
                line = self.article.__next__()
                value += "\n"
            except StopIteration:
                raise NoTemplate()
                
        # value parsen
        split = value.split("=")
        if len(split) > 1:
            value = split[1]
            # mögliche weitere = in value abfangen
            for el in range(2, len(split)):
                value += "=" + split[el]
                
            key = split[0]
            if "{{" in key:
                raise Exception("template in key: "+key)
            self.values[key] = value.strip()
            
        # anonyme values
        else:
            key = 1
            while True:
                if key in self.values:
                    key += 1
                else:
                    break
                    
            self.values[key] = split[0].strip()
            
        return new_state
                

class Article:
    """
    Artikelklasse; iterierbar über Zeilen
    """
    def __init__(self, name, redirect=True):
        """
        Öffnet einen Wikiartikel; löst insb. Redirections auf.
        name: Artikelname
        """
        self.title = None
        self.templates = None
        self.text = []
        self._asString = None
        self._cursor = {"line": -1, "char": 0, "modified": False}
        
        qry = "api.php?format=xml&action=query&titles="
        qry = _url + qry + urllib.parse.quote(name)
        if redirect:
            qry += "&redirects"
        response = opener.open(qry)

        # Leerzeile ueberspringen
        response.readline()

        # XML einlesen
        xml = ET.fromstring(response.readline())

        article = xml.find("query").find("pages")
        # Spezialseiten abfangen (z.B. Hochladen)
        if not article:
            raise Exception("Spezialseite")

        error = article.find("error")
        if error:
            msg = error.attrib["code"] + ": "
            msg += error.attrib["info"]
            raise Exception(msg)

        self.title = article.find("page").attrib["title"]
        print("Öffne " + self.title)
        try:
            qry = _url+urllib.parse.quote(self.title) + "?action=raw"
            site = opener.open(qry)
        except urllib.error.HTTPError:
            raise Exception("404: " + self.title)
            
        for line in site.readlines():
            self.text.append(remove_html_comments(line.decode('utf-8').strip(os.linesep).strip("\n")))

    @property
    def as_string(self):
        """
        Artikeltext als String
        """
        if self._asString is not None:
            return self._asString

        start = {
            "line": 0,
            "char": 0,
        }
        lastline = len(self.text) - 1
        end = {
            "line": lastline,
            "char": len(self.text[lastline]),
        }

        self._asString = self.extract(start, end)
        return self._asString

    @property
    def cursor(self):
        """
        Cursor-Definition
        { "line":line, "char":char, "modified":True|False }
        """
        return self._cursor.copy()
       
    # value kann vollständiger Cursor oder nur char sein
    @cursor.setter
    def cursor(self, value):
        # vollständiger Cursor übergeben
        try:
            self._cursor = { 
                "line": value["line"] + 0,
                "char": value["char"] + 0,
                "modified": True,
            }
        except:
            # nur char übergeben
            try:
                self._cursor = {
                    "line": self._cursor["line"],
                    "char": value + 0,
                    "modified": True,
                }
            except:
                raise Exception("invalid cursor: " + str(value))
        
    def reset_cursor(self):
        self._cursor = {"line": -1, "char": 0, "modified": False}

    def extract(self, start, end, linesep=os.linesep):
        """
        Gibt den Teil zwischen den Cursorn start und end zurück;
        alle Zeilen aneinandergehängt und mit \n getrennt
        """
        # Nur eine Zeile
        if start["line"] == end["line"]:
            return self.text[start["line"]][start["char"]:end["char"]]
        
        r = ""
        for i in range(start["line"], end["line"] + 1):
            # Anfangszeile
            if i == start["line"]:
                r += self.text[i][start["char"]:] + linesep
            # Endzeile
            elif i == end["line"]:
                return r + self.text[i][:end["char"]]
                
            else:
                r += self.text[i] + linesep
                
        # Sollte eigentlich nicht auftreten, da return in Endzeile
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

    def parse_templates(self):
        """
        Parst alle Vorlagen im Artikel text und gibt ein dict zurueck.
        Setzt den Cursor zurück.
        """
        self.templates = []
        self.reset_cursor()
        while True:
            try:
                self.templates.append(Template(self))
            except NoTemplate:
                break
                

def login(user=None, passwd=None):
    """
    Loggt den User ins Wiki ein.
    """
    # Config Check
    global username
    global password

    if user is not None and passwd is not None:
        username = user
        password = passwd

    if username is None or password is None:
        raise ConfigError("username or password not given")

    global opener

    # Ersten Request zusammensetzen, der das Login-Token einsammelt
    query_args = {'lgname': username, 'lgpassword': password}
    qry_args = urllib.parse.urlencode(query_args).encode('utf-8')
    qry = _url + 'api.php?format=xml&action=login'
    c = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(c))
    response = opener.open(qry, qry_args)

    # Token aus xml extrahieren
    response.readline()  # Leerzeile überspringen
    xml_root = ET.fromstring(response.readline())
    lg_token = xml_root.find('login').attrib['token']
    # session = xml_root.find('login').attrib['sessionid']

    # Zweiter Request mit Login-Token
    query_args.update({'lgtoken': lg_token})
    data = urllib.parse.urlencode(query_args).encode('utf-8')
    response = opener.open(_url+'api.php?format=xml&action=login', data)

    # Login-Status; ggf. abbrechen
    response.readline()  # Leerzeile überspringen
    xml_root = ET.fromstring(response.readline())
    result = xml_root.find('login').attrib['result']

    if result != "Success":
        raise Exception("Login: " + result)
    else:
        print(("Login: " + result))


def all_pages(resume=None):
    """
    Generator für Namen aller Wikiseiten
    """
    qry = _url+'api.php?action=query&list=allpages&aplimit=5000&format=xml'
    if resume:
        qry = qry + "&apfrom=" + resume
    response = opener.open(qry)

    # Leerzeile ueberspringen
    response.readline()

    # XML einlesen
    xml = ET.fromstring(response.readline())

    for page in xml.iter('p'):
        yield page.attrib['title']


def read_vz():
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
    while True:
        if re.match('^\s*|\s*Staaten\s*=\s*', text[i]):
            i += 1
            found = True
            break
        i += 1
    if not found:
        raise Exception("|Staaten= nicht gefunden.")
    
    # erstes "{{!}}-" suchen
    while True:
        if text[i].startswith('{{!}}-'):
            found = True
            i += 1
            break
        i += 1
    if not found:
        raise Exception("Staatentabellenheader nicht gefunden.")
    
    # zweites "{{!}}-" suchen
    while True:
        if text[i].startswith('{{!}}-'):
            found = True
            i += 1
            break
        i += 1
    if not found:
        raise Exception("Staatentabelleninhalt nicht gefunden.")
    
    # Tabelle parsen
    entry_ctr = 0
    dict = {}
    staaten = []
    # gegen highlightbug X_x
    ta = "'" + "'" + "'"
    name_p = re.compile(r'\{\{!\}\}\s*'+ta+'\s*(\[\[[^]]*\]\])\s*'+ta+'\s*<br>\s*(.*)')
    flagge_p = re.compile(r'\{\{!\}\}\s*(\[\[[^]]*\]\])\s*')
    zahl_p = re.compile(r'\{\{!\}\}\s*(\(*[\d-]*\)*)\s*')
    while True:
        # Tabellenende
        if text[i].startswith('{{!}}}'):
            i += 1
            break
        # Tabelleneintrag
        if not text[i].startswith('{{!}}'):
            i += 1
            continue
        
        # Datensatz zuende
        if text[i].startswith('{{!}}-'):
            if entry_ctr == 5:
                staaten.append(dict.copy())
                dict.clear()
            i += 1
            entry_ctr = 0
            continue

        value = text[i].strip()
        
        # Ins dict eintragen; evtl value korrigieren
        if entry_ctr == 0:
            value = value.replace('{{!}}', '').strip()
            
        elif entry_ctr == 1:
            tokens = re.split(name_p, value)
            names = get_state_names(tokens[1])
            dict["name"] = names["name"]
            dict["uri"] = names["uri"]
            dict["sortname"] = names["sortname"]

            # Spielername
            dict["spieler"] = tokens[2].replace('[[', '').replace(']]', '')
            
        elif entry_ctr == 2:
            try:
                value = re.split(flagge_p, value)[1]
                dict["buendnis"] = extract_flag(value)
            except:
                dict["buendnis"] = ""
            
        elif entry_ctr == 3:
            ms = re.split(zahl_p, value)[1]
            # Zweitstaat
            if ms.startswith('('):
                ms = ms.replace('(', '').replace(')', '')
                dict["zweitstaat"] = True
            else:
                dict["zweitstaat"] = False
            dict["ms"] = ms
            
        elif entry_ctr == 4:
            bomben = re.split(zahl_p, value)[1]
            if bomben == '-':
                bomben = '0'
            dict["as"] = bomben
            
        entry_ctr += 1
        i += 1
        
        if i == len(text):
            break

    """
    Spielerlose Staaten
    """
    # "|Spielerlose_Staaten=" suchen
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

    # Tabelle parsen
    eintrag_p = re.compile(r'\*(\{\{[^\}]+\}\})\s*(\[\[[^]]+\]\])')
    dict = {}
    spielerlos = []
    while True:
        line = text[i]
        # Tabellenende
        if line.startswith("|") or i >= len(text):
            break
        if eintrag_p.match(line) is not None:
            tokens = re.split(eintrag_p, line)
            # dict["flagge"] = extractFlag(tokens[1])
            names = get_state_names(tokens[2])
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
    # "|Militärbündnisse" suchen
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
    
    # Tabelle parsen
    dict = {}
    bnds = []
    bndeintrag_p = re.compile(r'\*\s*(\[\[[^]]*\]\])\s*\[\[([^]]*)\]\]')
    while True:
        line = text[i]
        # Tabellenende
        if line.startswith('{{!}}'):
            i += 1
            break
        # Tabelleneintrag
        if bndeintrag_p.match(line) is not None:
            tokens = re.split(bndeintrag_p, line)
            dict["flagge"] = extract_flag(tokens[1]).strip()
            dict["name"] = tokens[2].split("|")[0].strip()
            bnds.append(dict.copy())
            dict.clear()
            i += 1
            continue

        i += 1
        
        if i == len(text):
            break
    
    return {
            "staaten":    sorted(staaten, key=lambda k: k['sortname']),
            "buendnisse": bnds,
            "spielerlos": sorted(spielerlos, key=lambda k: k['uri']),
    }


def read_states(vz):
    """
    Liest die Infotabellen aller Staaten aus
    """
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
        article.parse_templates()
        infobox = None
        for t in article.templates:
            if t.name == "Infobox Staat":
                infobox = t.values
                break

        if infobox is None:
            print("Keine Infobox: "+staat["uri"])
            continue

        for key in infobox:
            infobox[key] = globalize_links(infobox[key], staat["uri"])
        if infobox is not None:
            staat["infobox"] = infobox
        # Stellt sicher, dass jeder Staat eine Infobox hat
        else:
            s = "Warnung: "+staat["uri"]+" hat keine Infobox Staat"
            print(s, file=sys.stderr)
            continue

    return staaten
    

def get_state_names(wikilink):
    """
    Nimmt einen Wikilink der Form [[x|y]] oder [[x]] und
    liefert Staatsname, Staats-URI und Sortierkey zurück:
    { "name":name, "uri":uri, "sortname":sortname }
    """
    name_p = re.compile(r'\[\[([^]]*)\]\]')

    r = {}
    # Staatsname
    tokens = re.split(name_p, wikilink)
    values = tokens[1].split("|")
    name = values[len(values) - 1]
    name = name.strip()
    r["name"] = name

    # URI; fuer [[x|y]]
    r["uri"] = values[0].strip()

    # Name für Sortierung
    sortkey = name
    for el in sort_prefixes:
        if sortkey.startswith(el+' '):
            sortkey = sortkey.replace(el, '')
            sortkey = sortkey.strip()
    r["sortname"] = sortkey
    return r
    

def extract_flag(flagcode):
    """
    Extrahiert den Dateinamen der Flagge
    aus der Flaggeneinbindung flagcode.
    """
    # html-Kommentar rauswerfen
    p = re.compile(r'<!--[^>]*-->')
    flagcode = p.sub("", flagcode)

    # Flaggenvorlage
    if re.match(r'\{\{', flagcode) is not None:
        # flagcode.replace(r"{{", "")
        # flagcode.replace(r"|40}}", "")
        mit_px_p = re.compile(r'\{\{(.+?)\|[^}]*\}\}')
        ohne_px_p = re.compile(r'\{\{(.+?)\}\}')

        if mit_px_p.match(flagcode):
            pattern = mit_px_p
        elif ohne_px_p.match(flagcode):
            pattern = ohne_px_p
        else:
            raise Exception(flagcode + " unbekannter Flaggencode")

        flagcode = re.split(pattern, flagcode)[1]
        
        # Vorlage herunterladen
        try:
            response = Article("Vorlage:" + flagcode)
        except:
            raise Exception("konnte nicht öffnen: "+flagcode)

        for line in response:
            if re.search(r'include>', line):
                break
        
        # Regex
        for el in image_keywords:
            line = line.replace(el, '')
        pattern = re.compile(r"\[\[(.+?)\|.+?\]\]")
        flagcode = re.findall(pattern, line)[0]

    # Normale Bildeinbindung
    elif re.match(r'\[\[', flagcode) is not None:
        flagcode = flagcode.replace('[[', '')
        flagcode = flagcode.replace(']]', '')
        for el in image_keywords:
            flagcode = flagcode.replace(el, '')
        values = flagcode.split('|')
        flagcode = values[0]
    # kaputt
    else:
        raise Exception(flagcode + " keine gültige Flagge")
    
    # Bild-URL extrahieren
    flagcode = urllib.parse.quote(flagcode.strip().replace(' ', '_'))
    response = opener.open(_url + 'api.php?titles=Datei:'+flagcode+'&format=xml&action=query&prop=imageinfo&iiprop=url')
    response.readline()  # Leerzeile ueberspringen
    xml_root = ET.fromstring(response.readline())
    
    for element in xml_root.iterfind('query/pages/page/imageinfo/ii'):
        return element.attrib['url']


def globalize_link(link, article):
    """
    Macht den Link link global.
    :param link: Link-dict, wie es aus parse_links() herausfällt.
    :param article: Artikelname für den lokalen Link
    :return: Gibt nichts zurück; das dict selbst wird modifiziert.
    """
    if link["uri"].startswith("#"):
        link["uri"] = article + link["uri"]
    if "filelink" in link and link["filelink"].startswith("#"):
        link["filelink"] = article + link["filelink"]


def globalize_links(s, article):
    """
    Macht alle lokalen Links in s global.
    Nimmt article als Artikelnamen für die lokalen Links an.
    Berücksichtigt auch Dateilinks, z.B.
    [[Datei:file.png|30px|link=#whatever]]
    """
    links = parse_links(s)
    for link in links:
        to_repl = build_link(link)

        globalize_link(link, article)
        new_link = build_link(link)
        s = s.replace(to_repl, new_link)
        """
        split = re.split(re.escape(new_link), s)
        s = split[0]
        for i in range(1, len(split)):
            s = new_link + split[i]
        """

    return s


def parse_links(s):
    """
    :return: Gibt alle Wikilinks ([[ ... ]]) im String s als Liste von dicts zurück.
    Liste ist leer, falls keine Links vorhanden.

    Zwingend vorhanden:
    "uri":<Ziel des Links>
    "file":boolescher Wert; gibt an ob Link eine Datei ist

    Vorhanden, falls im Link vorhanden:
    "filelink":<Link der "belinkten" Datei (|link=<filelink>)>
    "name":<name des Links bzw. Größenangabe der Datei>
    """
    e = re.findall(r"\[\[(.*?)\]\]", s)
    r = []
    for el in e:
        split = re.split("\|", el)
        dict = {"uri": split[0]}
        if len(split) > 1:
            if not split[1].startswith("link="):
                dict["name"] = split[1]

        # File check
        dict["file"] = False
        for el in image_keywords:
            if dict["uri"].startswith(el):
                dict["file"] = True
                break

        # File link
        if dict["file"] and len(split) > 1:
            for i in range(1, len(split)):
                if split[i].startswith("link="):
                    link = split[i].replace("link=", "")
                    dict["filelink"] = link
                    break

        r.append(dict)

    return r


def build_link(link, name=None):
    """
    Baut einen Link-String aus einem dict wie in parse_links() zusammen.
    :param link: Link, der aus parse_links() rausgefallen ist
    :param name: Name des Links, falls abweichend
    :return: Linkstring für Mediawiki (etwa [[Berge|Staat#Geographie]])
    """
    r = "[[" + link["uri"]

    if name is None and "name" in link:
        name = link["name"]
    if name is not None:
        r += "|" + name

    if link["file"] and "filelink" in link:
        r += "|link=" + link["filelink"]

    return r + "]]"


def remove_links(s):
    """
    Ersetzt alle Wikilinks im String s durch den Namen des Links,
    d.h. entfernt alle Wikilinks.
    """
    p = re.compile(r"\[\[.*?\]\]")

    # schrittweise jeden Links entfernen
    while True:
        link = p.search(s)
        if link is None:
            break
        link = link.group()

        parsed_link = parse_links(link)[0]
        parts = s.split(link, maxsplit=1)
        if "name" in parsed_link:
            name = parsed_link["name"]
        else:
            name = parsed_link["uri"].split("#")[0]
            if name == "":
                raise Exception("link "+name+"is not gobal")
        s = parts[0] + name + parts[1]

    return s


def remove_html_comments(s):
    """
    removes html comments from s.
    :param s: the string the comments are removed from
    :return: s without html comments
    """
    if "<!--" not in s:
        return s

    """
    Splits s by <!-- and -->, takes the first and the last part away and does things with the stuff in between.
    """
    while True:
        start_parts = s.split("<!--", maxsplit=1)
        if len(start_parts) < 2:
            break
        end_parts = start_parts[1].split("-->", maxsplit=1)
        if len(end_parts) < 2:
            break
        s = start_parts[0] + end_parts[1]

    return s


def edit_article(article, text, section=None):
    """
    Schreibt den Text text in den Artikel article.
    """
    print("Bearbeite "+article)

    # Edit-Token lesen
    url = _url + 'api.php?action=query&format=xml&titles=' + urllib.parse.quote(article) + '&meta=tokens'
    response = opener.open(url)
    # return response
    response.readline()
    xml_root = ET.fromstring(response.readline())
    edit_token = xml_root.find('query').find('tokens').attrib['csrftoken']
    
    # Seite bearbeiten
    query_args = {'text': text, 'token': edit_token}
    if section is not None:
        query_args['section'] = section
    query_url = _url + 'api.php?action=edit&bot&format=xml&title=' + urllib.parse.quote(article)
    response = opener.open(query_url, urllib.parse.urlencode(query_args).encode('utf8'))

    # Result auslesen
    response.readline()
    xml_root = ET.fromstring(response.readline())
    if xml_root.find('edit').attrib['result'] != 'Success':
        raise Exception('edit not successful')


def build_query(args):
    qry = "?"
    for arg in args:
        if qry == "?":
            qry += arg
        else:
            qry += "&"+arg
    return qry + "&format=xml&action=query"


def send_query(*args):
    """
    Schickt das Query bestehend aus *args ans Wiki.
    format=xml und action=query muss nicht angegeben werden.
    Gibt den xml-elementtree der Antwort zurück.
    Beispiel: sendQuery("titles=Flugghingen","redirects")
    """
    qry = build_query(args)
    print(qry)
    response = opener.open(_url+"api.php"+qry)
    response.readline()
    l = response.readline()
    return ET.fromstring(l)
