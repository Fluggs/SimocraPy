#!/usr/bin/python
# -*- coding: UTF-8 -*-

import urllib.request, urllib.parse, urllib.error, urllib.request, urllib.error, urllib.parse, http.cookiejar
import xml.etree.ElementTree as ET
import re
import time
import simocracy.wiki as wiki
import simocracy.IAS as IAS

from django.core.management.base import BaseCommand, CommandError
from mssim.models import Staat, Buendnis

class Command(BaseCommand):
    args = 'None'
    help = 'Aktualisiert die Staatendatenbank und das IAS'
    
    neutralflagge = ""
    #neutralflagge = "http://simocracy.de/images/1/1c/Xxwhiteflag.png"
    platzhalter = "http://simocracy.de/images/6/65/Platzhalter.png"
            
        
    """
    Fuehrt das Kommando aus.
    """
    def handle(self, *args, **options):
        wiki.login()
        vz = wiki.readVZ()

        staaten = wiki.readStates(vz)
        bnds = vz["buendnisse"]
        
        """
        DB-Modelle aufbauen
        """
        
        #Alte Daten löschen
        Staat.objects.all().delete()
        Buendnis.objects.all().delete()
        
        #"Kein Bündnis"-Bündnis
        neutralbnd = Buendnis()
        neutralbnd.name = "Kein Bündnis"
        neutralbnd.flagge = self.platzhalter
        neutralbnd.save()
        
        i = 1
        for buendnis in bnds:
            bnd = Buendnis()
            bnd.nummer = i
            bnd.flagge = buendnis["flagge"]
            bnd.name = buendnis["name"]
            bnd.save()
            i += 1
            
        # Staaten sortieren
        #staaten = sorted(staaten, key=lambda k: k['name']) 

        i = 1
        for state in staaten:
            #nur bespielte Staaten eintragen
            if state["spielerlos"]:
                continue

            staat = Staat()
            staat.nummer = i
            staat.name = state["name"]
            flag = "[["+state["infobox"]["Flagge"]+"]]"
            staat.flagge = wiki.extractFlag(flag)
            staat.spieler = state["spieler"]
            staat.ms = state["ms"]
            staat.bomben = state["as"]
            staat.zweitstaat = state["zweitstaat"]
            i += 1
            
            #Bündnis suchen
            found = False
            for bnd in Buendnis.objects.all():
                if bnd.flagge == state["buendnis"]:
                    staat.buendnis = bnd
                    found = True
            
            if not found:
                if state["buendnis"] != self.neutralflagge:
                    self.stdout.write("Konnte "+state["buendnis"]+" keinem bestehenden Bündnis zuordnen. "
                                    +state["name"]+" wird daher als neutral eingetragen.")
                staat.buendnis = neutralbnd
            
            staat.save()
        
        # Timestamp schreiben
        f = open("/home/fluggs/sysite/mssim/lastupdate", "w")
        f.write(str(int(time.time())))
        f.close()

        print("mssim-db aktualisiert")


        #IAS
        IAS.updateArticle(staaten)
        print("IAS aktualisiert")
