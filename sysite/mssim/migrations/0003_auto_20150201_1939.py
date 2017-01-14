# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('mssim', '0002_staat_zweitstaat'),
    ]

    operations = [
        migrations.AddField(
            model_name='buendnis',
            name='nummer',
            field=models.IntegerField(default=-1),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='staat',
            name='nummer',
            field=models.IntegerField(default=-1),
            preserve_default=True,
        ),
    ]
