#!/bin/env python3.4
# -*- coding: UTF-8 -*-

import simocracy.wiki as wiki
import re

## config ##
#Möglichkeit zur Simulation des Vorgangs
simulation = True

#Loglevel: schreibe nur geänderte Zeilen ("line") oder
#          ganze geänderte Artikel ("article") auf stdin
loglevel = "line"

# Ersatz für LD-Host-Links
replacement = r"{{LD-Host-Replacer}}"
# Kommt vor jeden Artikel, wo was ersetzt wurde
notif = r"{{LD-Host}}"
############


def main():
    opener = wiki.login(wiki.username, wiki.password)

    for p in wiki.allPages(opener):
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
    found = False
    text = ""
    logs = ""

    for line in wiki.openArticle(article, opener):
        newLine = line.decode('utf-8')
        foundList = []
        for el in ldhost.finditer(newLine):
            foundList.append(el)

        #nichts gefunden
        if foundList == []:
            text = text + newLine + "\n"
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

        text = text + newLine + "\n"

        #logging
        if simulation and loglevel == "line":
            logs = logs + "\n- " + line.decode('utf-8') + "+ " + newLine + "\n"

    if found:
        text = notif + "\n" + text

        if not simulation:
            wiki.editArticle(article, text, opener)
            print("Done: "+article)

        #Simulation
        else:
            print("[[" + article + "]]")
            if loglevel == "line":
                print(logs)
            elif loglevel == "article":
                print(text)
            else:
                raise Exception("config kaputt")

            print("========================================================\n\n")

        

if __name__ == "__main__":
    main()
