#!/usr/bin/python
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
replacement = "hier war ein LD-Host-Link"
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
    notif = re.escape("{{LD-Host|--~~~~}}")
    ldhost = re.compile(r'((http://)?(www.)?ld-host.de/[/\w]*?\.[a-z][a-z][a-z])')
    found = False
    text = ""
    logs = ""

    for line in wiki.openArticle(article, opener):
        newLine = line.decode('utf-8')
        m = ldhost.findall(newLine)
        foundList = []
        for el in m:
            foundList.append(el[0])

        #nichts gefunden
        if foundList == []:
            text = text + newLine + "\n"
            continue
        else:
            found = True

        #ersetzen
        for el in foundList:
            newLine = replaceAll(el, replacement, newLine)

        text = text + newLine + "\n"

        #logging
        if simulation and loglevel == "line":
            logs = logs + "\n- " + line.decode('utf-8') + "+ " + newLine

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
