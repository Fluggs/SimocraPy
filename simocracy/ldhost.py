#!/usr/bin/python
# -*- coding: UTF-8 -*-

import simocracy.wiki as wiki

opener = wiki.login(wiki.username, wiki.password)

for p in wiki.allPages(opener):
    print(p)
