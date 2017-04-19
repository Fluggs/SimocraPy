#!/usr/bin/env python3.4
# -*- coding: UTF-8 -*-

"""
Datumsformat:
{
  "tag":tag,
  "monat":monat,
  "jahr":jahr,
  "stunde":stunde,
  "minute":minute,
}
"""


class SyEpocheException(Exception):
    """
    Wird geworfen, wenn ein Datum nicht in der Simocracy-Epoche liegt.
    """
    pass


def monat_len(monat, jahr):
    """
    Gibt zurück, wie viele Tage monat im Jahr jahr hat.
    """
    if monat == 2:
        if is_schaltjahr(jahr):
            return 29
        else:
            return 28
        
    monate = [
        31,  # jan
        -1,  # feb
        31,  # mae
        30,  # apr
        31,  # mai
        30,  # jun
        31,  # jul
        31,  # aug
        30,  # sep
        31,  # okt
        30,  # nov
        31   # dez
    ]
    
    return monate[monat - 1]


def is_schaltjahr(jahr):
    """
    Gibt zurück, ob jahr ein Schaltjahr n. greg. Kalender ist.
    """
    if jahr % 400 == 0:
        return True
    if jahr % 4 == 0 and jahr % 100 != 0:
        return True
    
    return False


def is_valid_datum(datum):
    """
    Wirft Exception, wenn datum kein valides Datum n. greg. Kalender ist.
    """
    msg = "Angegebenes Datum ist ungültig."

    if not (
      "tag" in datum
      and "monat" in datum
      and "jahr" in datum
      and "stunde" in datum
      and "minute" in datum
    ):
        raise Exception(msg)

    tag = datum["tag"] > monat_len(datum["monat"], datum["jahr"])
    tag = tag or datum["tag"] < 1
    monat = datum["monat"] < 1
    monat = monat or datum["monat"] > 12
    stunde = datum["stunde"] < 0 or datum["stunde"] > 23
    minute = datum["minute"] < 0 or datum["minute"] > 59

    if tag or monat or stunde or minute:
        raise Exception(msg)
    

def rltosy(datum):
    """
    Konvertiert ein RL-Datum zum zugehörigen SY-Datum.
    """
    # Input checken
    is_valid_datum(datum)
    epoch_in_08 = datum["jahr"] == 2008 and datum["monat"] < 10
    if datum["jahr"] < 2008 or epoch_in_08:
        raise SyEpocheException(datum)
    
    # Monate des Quartals (= Sy-Jahr) sammeln
    quartalsanfang = datum["monat"] - (datum["monat"] + 2) % 3
    quartal = []
    for i in range(quartalsanfang, datum["monat"]):
        quartal.append(i)
        
    # SY-Jahr berechnen
    sy_jahr = (datum["jahr"] - 2008) * 4 + 2017
    sy_jahr += quartalsanfang / 3
        
    # Vergangene Tage im Quartal zusammenaddieren
    tage = datum["tag"] - 1
    for i in quartal:
        tage += monat_len(i, datum["jahr"])
        
    # Bisherige Minuten des Quartals
    minuten = tage*24*60 + datum["stunde"]*60 + datum["minute"]
    
    # In SY-Minuten umrechnen
    schalttag = 0
    if is_schaltjahr(sy_jahr):
        schalttag = 1
        
    sy_jahr_mins = (365 + schalttag) * 24 * 60
    
    quartal_mins = 0
    for i in range(quartalsanfang, quartalsanfang + 3):
        quartal_mins += monat_len(i, datum["jahr"]) * 24 * 60
        
    sy_datum_mins = int(float(minuten) * (float(sy_jahr_mins) / float(quartal_mins)))
    
    # Stunde und Minute berechnen
    sy_datum_tag = sy_datum_mins / (60 * 24) + 1
    sy_minute = sy_datum_mins % 60
    sy_stunde = sy_datum_mins / 60 - sy_datum_tag * 24 + 24
    
    # von Tagen Monate abziehen
    volle_monate = 0  # Tage im SY-Datum, die in vergangenen Monaten liegen
    sy_monat = 1
    while True:
        if volle_monate + monat_len(sy_monat, sy_jahr) >= sy_datum_tag:
            break
        volle_monate += monat_len(sy_monat, sy_jahr)
        sy_monat += 1
    
    sy_tag = sy_datum_tag - volle_monate
    
    return {
        "tag":    sy_tag,
        "monat":  sy_monat,
        "jahr":   sy_jahr,
        "stunde": sy_stunde,
        "minute": sy_minute,
    }


def sytorl(datum):
    """
    Konvertiert ein SY-Datum zum RL-Datum.
    Erwartet 5-elementige Liste als Argument.
    """
    # Input checken
    is_valid_datum(datum)
    if datum["jahr"] < 2020:
        raise SyEpocheException()
    
    # Jahr und Quartal berechnen
    quartal_nr = (datum["jahr"] - 1) % 4  # Zaehlung beginnt bei 0
    rl_jahr = (datum["jahr"] - 2017) / 4 + 2008
    
    # Minuten zusammenaddieren
    minuten = (datum["tag"] - 1) * 24 * 60 + datum["stunde"] * 60 + datum["minute"]
    for i in range(1, datum["monat"]):
        minuten += monat_len(i, datum["jahr"]) * 24 * 60
    
    # Minuten des gesamten Jahres berechnen
    schalttag = 0
    if is_schaltjahr(datum["jahr"]):
        schalttag = 1
    sy_jahr_mins = (365 + schalttag) * 24 * 60
    
    # Quartallaenge in Minuten berechnen
    quartal = []
    quartal_mins = 0
    for i in range(quartal_nr * 3 + 1, quartal_nr * 3 + 4):
        quartal.append(i)
        quartal_mins += monat_len(i, rl_jahr) * 24 * 60
    
    # in RL-Quartal-Minuten umrechnen
    rl_datum_mins = int(float(minuten) / (float(sy_jahr_mins) / float(quartal_mins)))
    
    # Stunde und Minute berechnen
    rl_minute = rl_datum_mins % 60
    rl_datum_tag = rl_datum_mins / (60 * 24) + 1
    rl_stunde = rl_datum_mins / 60 - (rl_datum_tag - 1) * 24
    
    # von Tagen Monate abziehen
    volle_monate = 0  # Tage im RL-Datum, die in vergangenen Monaten liegen
    rl_monat = quartal[0]
    while True:
        if volle_monate + monat_len(rl_monat, rl_jahr) > rl_datum_tag - 1:
            break
        volle_monate += monat_len(rl_monat, rl_jahr)
        rl_monat += 1
    
    rl_tag = rl_datum_tag - volle_monate
    
    # 24-Stunde umklappen"
    if rl_stunde == 24:
        rl_stunde = 0
        rl_tag += 1
        if rl_tag > monat_len(rl_monat, rl_jahr):
            rl_monat += 1
            rl_tag = 1
    
    return {
        "tag":    rl_tag,
        "monat":  rl_monat,
        "jahr":   rl_jahr,
        "stunde": rl_stunde,
        "minute": rl_minute,
    }
