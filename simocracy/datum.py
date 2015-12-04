#!/usr/bin/env python3.4
# -*- coding: UTF-8 -*-

"""
Wird geworfen, wenn ein Datum nicht in der Simocracy-Epoche liegt.
"""
class SyEpocheException(Exception):
    pass

"""
Gibt zurück, wie viele Tage monat im Jahr jahr hat.
"""
def monatLen(monat, jahr):
    if monat == 2:
        if isSchaltjahr(jahr):
            return 29
        else:
            return 28
        
    monate = [
        31, #jan
        -1, #feb
        31, #mae
        30, #apr
        31, #mai
        30, #jun
        31, #jul
        31, #aug
        30, #sep
        31, #okt
        30, #nov
        31  #dez
    ]
    
    return monate[monat - 1]

"""
Gibt zurück, ob jahr ein Schaltjahr n. greg. Kalender ist.
"""
def isSchaltjahr(jahr):
    if jahr % 400 == 0:
        return True
    if jahr % 4 == 0 and jahr % 100 != 0:
        return True
    
    return False

"""
Konvertiert ein RL-Datum zum zugehörigen SY-Datum.
return [ syTag, syMonat, syJahr, syStunde, syMinute ]
"""
def rltosy(datum):
    
    if len(datum) < 5:
        raise Exception("Zu wenige Elemente in datum")
    
    tag = datum[0]
    monat = datum[1]
    jahr = datum[2]
    stunde = datum[3]
    minute = datum[4]
    
    # Input checken
    if jahr < 2008 or ( jahr == 2008 and monat < 10 ):
        raise SyEpocheException("jahr: " + str(jahr) + "; monat: " + str(monat))
    
    elif (monat > 12 or monat < 1
      or tag > monatLen(monat, jahr) or tag < 1
      or stunde < 0 or stunde > 23
      or minute < 0 or minute > 59):
        raise Exception("Angegebenes Datum ist ungültig")
    
    # Monate des Quartals (= Sy-Jahr) sammeln
    quartalsanfang = monat - ( monat + 2 ) % 3
    quartal = []
    for i in range(quartalsanfang, monat):
        quartal.append(i)
        
    # SY-Jahr berechnen
    syJahr = ( jahr - 2008 ) * 4 + 2017
    syJahr += quartalsanfang / 3
        
    # Vergangene Tage im Quartal zusammenaddieren
    tage = tag - 1
    for i in quartal:
        tage += monatLen(i, jahr)
        
    # Bisherige Minuten des Quartals
    minuten = tage*24*60 + stunde*60 + minute
    
    # In SY-Minuten umrechnen
    schalttag = 0
    if isSchaltjahr(syJahr):
        schalttag = 1
        
    syjahrMins = ( 365 + schalttag ) * 24 * 60
    
    quartalMins = 0
    for i in range(quartalsanfang, quartalsanfang + 3):
        quartalMins += monatLen(i, jahr) * 24 * 60
        
    sydatumMins = int(float(minuten) * (float(syjahrMins) / float(quartalMins)))
    
    # Stunde und Minute berechnen
    sydatumTag = sydatumMins / ( 60 * 24 ) + 1
    syMinute = sydatumMins % 60
    syStunde = sydatumMins / 60 - sydatumTag * 24 + 24
    
    # von Tagen Monate abziehen
    volleMonate = 0 # Tage im SY-Datum, die in vergangenen Monaten liegen
    syMonat = 1
    while True:
        if volleMonate + monatLen(syMonat, syJahr) >= sydatumTag:
            break
        volleMonate += monatLen(syMonat, syJahr)
        syMonat += 1
    
    syTag = sydatumTag - volleMonate
    
    return [ syTag, syMonat, syJahr, syStunde, syMinute ]

"""
Konvertiert ein SY-Datum zum RL-Datum.
Erwartet 5-elementige Liste als Argument.
return [ rlTag, rlMonat, rlJahr, rlStunde, rlMinute ]
"""
def sytorl(datum):
    
    if len(datum) < 5:
        raise Exception("Zu wenige Elemente in datum")
    
    tag = datum[0]
    monat = datum[1]
    jahr = datum[2]
    stunde = datum[3]
    minute = datum[4]
    
    # Input checken
    if jahr < 2020:
        raise SyEpocheException()
    
    elif (monat > 12 or monat < 1
      or tag > monatLen(monat, jahr) or tag < 1
      or stunde < 0 or stunde > 23
      or minute < 0 or minute > 59):
        raise Exception("Angegebenes Datum ist ungültig")
    
    # Jahr und Quartal berechnen
    quartalNr = ( jahr - 1 ) % 4 # Zaehlung beginnt bei 0
    rlJahr = ( jahr - 2017 ) / 4 + 2008
    
    # Minuten zusammenaddieren
    minuten = (tag - 1) * 24 * 60 + stunde * 60 + minute
    for i in range(1, monat):
        minuten += monatLen(i, jahr) * 24 * 60
    
    # Minuten des gesamten Jahres berechnen
    schalttag = 0
    if isSchaltjahr(jahr):
        schalttag = 1
    syjahrMins = ( 365 + schalttag ) * 24 * 60
    
    # Quartallaenge in Minuten berechnen
    quartal = []
    quartalMins = 0
    for i in range(quartalNr * 3 + 1, quartalNr * 3 + 4):
        quartal.append(i)
        quartalMins += monatLen(i, rlJahr) * 24 * 60
    
    # in RL-Quartal-Minuten umrechnen
    rldatumMins = int(float(minuten) / (float(syjahrMins) / float(quartalMins)))
    
    # Stunde und Minute berechnen
    rlMinute = rldatumMins % 60
    rldatumTag = rldatumMins / ( 60 * 24 ) + 1
    rlStunde = rldatumMins / 60 - (rldatumTag - 1) * 24
    
    # von Tagen Monate abziehen
    volleMonate = 0 # Tage im RL-Datum, die in vergangenen Monaten liegen
    rlMonat = quartal[0]
    while True:
        if volleMonate + monatLen(rlMonat, rlJahr) > rldatumTag - 1:
            break
        volleMonate += monatLen(rlMonat, rlJahr)
        rlMonat += 1
    
    rlTag = rldatumTag - volleMonate
    
    # 24-Stunde umklappen"
    if rlStunde == 24:
        rlStunde = 0
        rlTag += 1
        if rlTag > monatLen(rlMonat, rlJahr):
            rlMonat += 1
            rlTag = 1
    
    return [ rlTag, rlMonat, rlJahr, rlStunde, rlMinute ]

