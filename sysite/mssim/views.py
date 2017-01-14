#!/usr/bin/env python3.4
# -*- coding: UTF-8 -*-

from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader

from mssim.models import Staat, Buendnis

import random
import simocracy.datum as sydatum
import xml.etree.ElementTree as ET
from datetime import datetime

def slwahl(request):
    bewerber = ['Schleicher', 'Costa', 'Furanty']

    vardict = { "calculation" : False }
    if "calc" in request.POST:
        vardict["ergebnis"] = random.choice(bewerber)
        vardict["calculation"] = True

    template = loader.get_template('slwahl/index.html')
    context = RequestContext(request, vardict)
    return HttpResponse(template.render(context))

def toInfinity():
    i = 0
    while True:
        yield i
        i += 1

def wahlsim(request):
    
    vardict = { "error" : False }
    
    # Select-Listen bestuecken
    vardict["parteien"] = []
    for i in range(2, 10):
        vardict["parteien"].append(str(i))
        
    vardict["prozentmax"] = []
    for i in range(10, 101, 5):
        vardict["prozentmax"].append(str(i) + "%")
        
    vardict["prozentmin"] = []
    for i in range(0, 10):
        vardict["prozentmin"].append(str(i) + "%")
        
    
    # Maximalergebnis nicht anwendbar
    if ("calc" in request.POST
            and int(request.POST["anzahl"]) * int(request.POST["max"].replace("%", "")) < 100):
        vardict["error"] = True
        vardict["calculation"] = False
        
        vardict["input"] = {}
        vardict["input"]["anzahl"] = request.POST["anzahl"]
        vardict["input"]["max"] = request.POST["max"]
        vardict["input"]["min"] = request.POST["min"]
        
    # POST-Input liegt for
    elif "calc" in request.POST:
        
        vardict["calculation"] = True
        vardict["input"] = {}
        vardict["input"]["anzahl"] = request.POST["anzahl"]
        vardict["input"]["max"] = request.POST["max"]
        vardict["input"]["min"] = request.POST["min"]
        
        anzahl = int(request.POST["anzahl"])
        sup = int(request.POST["max"].replace("%", "")) # Supremum bzw. Maximum
        inf = int(request.POST["min"].replace("%", "")) # Infimum bzw. Minimum
        if inf < 0.1:
            inf = 0.3
        
            
        ergebnis = []
        
        # Zufallszahlen
        """
        Bestimmt Zufallszahl zwischen noch freiem Raum bzw. Maximum
        und Minimum.
        Dadurch sieht die Verteilung mehr wie ein Wahlergebnis
        aus (im Vgl. zu Array aus Zufallszahlen und nach
        Verhaeltnis die Stimmen verteilen).
        """
        for i in range(0, anzahl - 1):
            maximum = float(min(sup, 100.0 - sum(ergebnis)))
            rndnumber = random.uniform(inf, maximum)
            ergebnis.append(random.uniform(inf, maximum))
            
            # sum verkleinern, falls zu gross fuer weiteres Ergebnis
            for i in toInfinity():
                if sum(ergebnis) < 100.0 - inf:
                    break
                
                j = i % len(ergebnis)
                ergebnis[j] = random.uniform(inf, ergebnis[j])
                if ergebnis[j] == 0.0:
                    ergebnis[j] =.1
        del maximum
            
        # Letztes Ergebnis unter max bzw. inf bringen
        for i in toInfinity():
            if 100.0 - sum(ergebnis) <= float(sup):
                break
            
            j = i % len(ergebnis)
            ergebnis[j] = random.uniform(ergebnis[j], float(sup))
            
        for i in range(0, len(ergebnis)):
            ergebnis[i] = round(ergebnis[i], 1)
            
        ergebnis.append(100.0 - sum(ergebnis))
        ergebnis[0] = ergebnis[0] - (sum(ergebnis) - 100.0)
        # irgendwo wird die Sort. umgedreht, keinen Schimmer wo
        ergebnis.sort(reverse = True)
        
        # Wahlergebnis in vardict stecken
        vardict["ergebnis"] = []
        for i in range(0, len(ergebnis)):
            dict = { "nummer" : i + 1,
                    "ergebnis" : ergebnis[i] }
            vardict["ergebnis"].append(dict)
            
    # Kein Input
    else:
        vardict["calculation"] = False
        

    template = loader.get_template('wahlsim/index.html')
    context = RequestContext(request, vardict)
    return HttpResponse(template.render(context))
        

def datum(request):

    if "api" in request.GET:
        return botdatum(request)
    
    vardict = { "error" : False }
    
    # Select-Listen bestücken
    vardict["tage"] = []
    for i in range(1, 32):
        vardict["tage"].append("%02d" % (i))
        
    vardict["monate"] = []
    for i in range(1, 13):
        vardict["monate"].append("%02d" % (i))
        
    vardict["jahre"] = []
    for i in range(2008, 2060):
        vardict["jahre"].append("%04d" % (i))
        
    vardict["stunden"] = []
    for i in range(0, 24):
        vardict["stunden"].append("%02d" % (i))
        
    vardict["minuten"] = []
    for i in range(0, 60):
        vardict["minuten"].append("%02d" % (i))
    
    # POST-Input liegt vor
    datum = []
    
    if "calc" in request.POST:
        
        inputdatum = []
        
        # Heutiges Datum
        if request.POST["calc"] == "heute":
            vardict["calculation"] = True
            heute = datetime.now()
            vardict["modus"] = "sy"
            inputdatum = {
                "tag"    : int(heute.day),
                "monat"  : int(heute.month),
                "jahr"   : int(heute.year),
                "stunde" : int(heute.hour),
                "minute" : int(heute.minute)
            }
            calculate = sydatum.rltosy
        
        # Irgendein Datum
        else:
            vardict["calculation"] = True
            vardict["modus"] = request.POST["modus"]
            inputdatum = {
                "tag"    : int(request.POST["tag"]),
                "monat"  : int(request.POST["monat"]),
                "jahr"   : int(request.POST["jahr"]),
                "stunde" : int(request.POST["stunde"]),
                "minute" : int(request.POST["minute"]),
            }
            
            # Modus SY -> RL
            if request.POST["modus"] == "rl":
                calculate = sydatum.sytorl
            
            # Modus RL -> SY
            else:
                calculate = sydatum.rltosy
                
                
            
        vardict["input"] = {
            "tag":"%02d" % (inputdatum["tag"]),
            "monat":"%02d" % (inputdatum["monat"]),
            "jahr":"%04d" % (inputdatum["jahr"]),
            "stunde":"%02d" % (inputdatum["stunde"]),
            "minute":"%02d" % (inputdatum["minute"])
        }
                
        try:
            datum = calculate(inputdatum)
            vardict["tag"] = "%02d" % (datum["tag"])
            vardict["monat"] = "%02d" % (datum["monat"])
            vardict["jahr"] = "%04d" % (datum["jahr"])
            vardict["stunde"] = "%02d" % (datum["stunde"])
            vardict["minute"] = "%02d" % (datum["minute"])
        except sydatum.SyEpocheException:
            vardict["error"] = True
            vardict["calculation"] = False
            pass
        
    # Kein Input   
    else:
        vardict["calculation"] = False
        
    template = loader.get_template('datum/index.html')
    context = RequestContext(request, vardict)
    return HttpResponse(template.render(context))

def mssim(request):
        
    staaten = []
    for staat in Staat.objects.all():
        staaten.append(staat)
    vardict = {}

    # Letztes Update auslesen
    try:
        f = open("/home/fluggs/sysite/mssim/lastupdate", "r")
        ts = int(f.readline().strip())
        t = datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
        vardict["lastupdate"] = t
    except:
        #Absolut kein Beinbruch, wenn lastupdate fehlt
        pass
    
    # POST-Input liegt vor
    if "check" in request.POST:
        vardict["calculation"] = True
        
        # Radioboxen einsammeln
        submits = {}
        for key in request.POST:
            if key.isdigit():
                submits[int(key)] = request.POST[key]
                
        ms_A = 0
        ms_B = 0
        as_A = 0
        as_B = 0
        for key in submits:
            
            staat = staaten[key - 1]
            
            if submits[key] == "a":
                staat.partei = "a"
                ms_A += staat.ms
                as_A += staat.bomben
            elif submits[key] == "b":
                staat.partei = "b"
                ms_B += staat.ms
                as_B += staat.bomben
            
            #Neutralfall sowie Zweifelsfall
            else:
                staat.partei = "neutral"
            
        # Sieger errechnen
        winner = "Partei A"
        unentschieden = False
        if ms_A == ms_B:
            unentschieden = True #Template ignoriert winner
        elif ms_B > ms_A:
            winner = "Partei B"
            
        # Variablen eintragen
        vardict["winner"] = winner
        vardict["ms_A"] = ms_A
        vardict["ms_B"] = ms_B
        vardict["as_A"] = as_A
        vardict["as_B"] = as_B
        vardict["unentschieden"] = unentschieden
            
    # Kein Input
    else:
        vardict["calculation"] = False
        for staat in staaten:
            staat.partei = "neutral"
            
    vardict["staatenliste"] = staaten
    
    
    template = loader.get_template('mssim/index.html')
    context = RequestContext(request, vardict)
    return HttpResponse(template.render(context))

def isInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def parseDatumGETRequest(request):
    modus = None
    if not request.GET["modus"] in ("sy", "rl", "heute"):
        raise Exception()
    if not request.GET["format"] in ("xml", "raw"):
        raise Exception()
    if request.GET["modus"] == "heute":
        return {"modus":"heute", "format":request.GET["format"]}

    return {
        "modus":request.GET["modus"],
        "format":request.GET["format"],
        "jahr":int(request.GET["jahr"]),
        "monat":int(request.GET["monat"]),
        "tag":int(request.GET["tag"]),
        "stunde":int(request.GET["stunde"]),
        "minute":int(request.GET["minute"]),
    }

def botdatum(request):
    get = None
    try:
        get = parseDatumGETRequest(request)
    except:
        return(HttpResponse("ungültiger request"))

    vardict = { "error":"none" }
    # Heutiges Datum
    if get["modus"] == "heute":
        heute = datetime.now()
        vardict["modus"] = "sy"
        inputdatum = {
            "tag"    : int(heute.day),
            "monat"  : int(heute.month),
            "jahr"   : int(heute.year),
            "stunde" : int(heute.hour),
            "minute" : int(heute.minute)
        }
        calculate = sydatum.rltosy

    # Irgendein Datum
    else:
        vardict["modus"] = get["modus"]
        inputdatum = {
            "tag"    : get["tag"],
            "monat"  : get["monat"],
            "jahr"   : get["jahr"],
            "stunde" : get["stunde"],
            "minute" : get["minute"],
        }

        # Modus SY -> RL
        if get["modus"] == "rl":
            calculate = sydatum.sytorl

        # Modus RL -> SY
        elif get["modus"] == "sy":
            calculate = sydatum.rltosy

    try:
        datum = calculate(inputdatum)
        vardict["tag"] = "%02d" % (datum["tag"])
        vardict["monat"] = "%02d" % (datum["monat"])
        vardict["jahr"] = "%04d" % (datum["jahr"])
        vardict["stunde"] = "%02d" % (datum["stunde"])
        vardict["minute"] = "%02d" % (datum["minute"])
    except sydatum.SyEpocheException:
        vardict["error"] = "epoche"
        vardict["calculation"] = False
        pass
    
    response = None
    if get["format"] == "raw":
        text = None
        if vardict["error"] != "none":
            text = "error:"+vardict["error"]
        else:
            text = vardict["tag"]+"."+vardict["monat"]+"."+vardict["jahr"]
            text = text+" "+vardict["stunde"]+":"+vardict["minute"]
        response = HttpResponse(text)
        response["Content-Type"] = "text/plain"

    elif get["format"] == "xml":
        xml = ET.Element("query")
        if vardict["error"] == "none":
            datedict = {
                "jahr":vardict["jahr"],
                "monat":vardict["monat"],
                "tag":vardict["tag"],
                "stunde":vardict["stunde"],
                "minute":vardict["minute"],
            }
            xmldatum = ET.SubElement(xml, "datum", datedict)

        error = ET.SubElement(xml, "error")
        error.text = vardict["error"]
        response = HttpResponse(ET.tostring(xml))
        response["Content-Type"] = "application/xml"

    return(response)
