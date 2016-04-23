#!/bin/env python3.4
# -*- coding: UTF-8 -*-

import simocracy.wiki as wiki
import re

## config ##
#Möglichkeit zur Simulation des Vorgangs
simulation = False

#Loglevel: schreibe nur geänderte Zeilen ("line") oder
#          ganze geänderte Artikel ("article") auf stdin oder
#          gar nicht ("none")
loglevel = "line"

# Ersatz für LD-Host-Links
replacement = r"{{LD-Host-Replacer}}"
# Kommt vor jeden Artikel, wo was ersetzt wurde
notif = r"{{LD-Host}}"
############


def main():
    opener = wiki.login(wiki.username, wiki.password)

    for p in wiki.allPages(opener, resume="speed"):
        doIt(p, opener)

#Ersetzt alle Vorkommnisse von sub in s durch repl.
def replaceAll(sub, repl, s):
    while True:
        testagainst = s
        s = re.sub(sub, repl, s)
        if s == testagainst:
            return s

def doIt(article, opener):
    ldhost = re.compile(r'(Thumb=)?\[?\[?\s*(?P<link>(http://)?(www\.)?ld-host\.de/[/\w]*?\.[a-z][a-z][a-z])\s*[^\]]*?\]?\]?')
    doubleRepl = re.compile(r'\[?\s*' + re.escape(replacement) + r'\s*' + re.escape(replacement) + r'\s*\]?')
    found = False
    text = ""
    logs = ""

    #Spezialseiten abfangen
    site = None
    try:
        site = wiki.openArticle(article, opener, redirect=False)
    except Exception as e:
        if str(e) == "Spezialseite":
            return

    for line in site:
        newLine = line.decode('utf-8')
        foundList = []
        for el in ldhost.finditer(newLine):
            foundList.append(el)

        #nichts gefunden
        if foundList == []:
            text = text + newLine
            continue
        else:
            found = True

        #ersetzen
        for el in foundList:
            #Bildboxen berücksichtigen
            if 'Thumb=' in el.groups():
                newLine = replaceAll(el.groupdict()['link'], "", newLine)
            else:
                newLine = replaceAll(el.groupdict()['link'], replacement, newLine)

        newLine = replaceAll(doubleRepl, replacement, newLine)

        text = text + newLine

        #logging
        if simulation and loglevel == "line":
            logs = logs + "\n- " + line.decode('utf-8') + "+ " + newLine + "\n"

    if found:
        text = notif + text

        print("[[" + article + "]]")
        if loglevel == "line":
            print(logs)
        elif loglevel == "article":
            print(text)
        else:
            raise Exception("config kaputt")

        #Schreiben
        if not simulation:
            wiki.editArticle(article, text, opener)
            print("Done: "+article)

        print("========================================================\n")

        

if __name__ == "__main__":
    main()
