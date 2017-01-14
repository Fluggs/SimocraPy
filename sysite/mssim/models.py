#!/usr/bin/env python3.4
# -*- coding: UTF-8 -*-

from django.db import models

    
class Buendnis(models.Model):
    nummer = models.IntegerField(default=-1)
    name = models.CharField(max_length=200)
    flagge = models.CharField(max_length=200)
    
    def __unicode__(self):
        return self.name

class Staat(models.Model):
    nummer = models.IntegerField(default=-1)
    name = models.CharField(max_length=200)
    flagge = models.CharField(max_length=200)
    spieler = models.CharField(max_length=200)
    ms = models.IntegerField(default=20)
    bomben = models.IntegerField(default=0)
    buendnis = models.ForeignKey(Buendnis)
    zweitstaat = models.BooleanField(default=False)
    
    # Fuer Parteizuordnung im View
    partei = None

    def __unicode__(self):
        return self.name
