# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Buendnis',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('flagge', models.CharField(max_length=200)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Staat',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, verbose_name='ID', primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('flagge', models.CharField(max_length=200)),
                ('spieler', models.CharField(max_length=200)),
                ('ms', models.IntegerField(default=20)),
                ('bomben', models.IntegerField(default=0)),
                ('buendnis', models.ForeignKey(to='mssim.Buendnis')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
