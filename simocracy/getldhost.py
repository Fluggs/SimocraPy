#!/bin/env python3.4

import simocracy.wiki as wiki
import re
import urllib
import sys


def main():
    opener = wiki.login()

    #Datei öffnen
    if len(sys.argv) < 2:
        print("missing argument: "+sys.argv[0]+" FILENAME")
        exit()
    if sys.argv[0] == sys.argv[1]:
        print("nope")
    file = open(sys.argv[1], "w")

    #Revisions sammeln
    revs = {}
    for page in wiki.allPages():
        ##zerbricht an ß
        #title = urllib.parse.quote(page)
        title = page
        xml = wiki.sendQuery(
            "redirects",
            "prop=revisions",
            "titles="+urllib.parse.quote(page),
            "rvdir=older",
            "rvlimit=max")

        #redirects ausschließen
        #xml = xml.find("query").find("pages")
        #if not xml:
        #    continue
        #title = xml.find("page").attrib["title"]
        #if title in revs:
        #    continue

        #letzte Fluggbot-revision finden
        fluggbotid = 0
        found = False
        for el in xml.iter():
            if el.tag != "rev":
                continue
            if el.attrib["user"] != "Fluggbot":
                continue

            found = True
            id = int(el.attrib["revid"])
            if id > fluggbotid:
                fluggbotid = id

        if not found:
            continue

        #letzte revision vor Fluggbot finden
        lastrevid = 0
        for el in xml.iter():
            if el.tag != "rev":
                continue
            if el.attrib["user"] == "Fluggbot":
                continue

            id = int(el.attrib["revid"])
            if id > lastrevid and id < fluggbotid:
                lastrevid = id

        revs[title] = str(lastrevid)


    #Revisioncontents parsen und LD-Host-Links extrahieren
    links = []
    for title in revs:
        qry = wiki.buildQuery((
            "titles="+title,
            "prop=revisions",
            "rvstartid="+revs[title],
            "rvprop=content",
            "rvlimit=1",
            "redirects"))
        print(qry)
        try:
            r = wiki.opener.open(wiki._url+"api.php"+qry)
        except:
            print("Überspringe "+title)
            continue

        text = []
        for line in r.readlines():
            text.append(line.decode('utf-8'))
        found = extractLDHostLinks(text)
        for el in found:
            if not el in links:
                links.append(el)

    print(str(len(links))+" Links gefunden, schreibe in "+sys.argv[1])
    for el in links:
        file.write(el + "\n")


def extractLDHostLinks(text):
    ldhost = re.compile(r'((http://)?(www\.)?(?P<link>ld-host\.de/[^.]*?\.[a-z][a-z][a-z]))')
    links = []
    for line in text:
        found = ldhost.findall(line)
        if not found:
            continue

        for el in found:
            link = el[0]
            #Link normalisieren
            link = ldhost.search(link).group('link')
            if not link in links:
                links.append(link)

    return links

main()
