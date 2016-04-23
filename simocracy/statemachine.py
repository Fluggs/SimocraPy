#!/usr/bin/env python3.4

class StateMachine():
    def __init__(self, endless=False):
        self.states = {}
        self.start = None
        self.ends = []
        self.state = None
        self.endless = endless

    def addState(self, name, handler, end=False):
        self.states[name] = handler
        if end:
            self.ends.append(name)
        
    def setStart(self, name):
        if name in self.states:
            self.start = name
        else:
            raise Exception("unknown state: " + name)
        
    def run(self):
        if self.start == None:
            raise Exception("no start state given")
        
        if not self.endless and self.ends == []:
            raise Exception("no end state given")
            
        self.state = self.start
        
        while True:
            self.state = self.states[self.state]()
            if self.state not in self.states:
                raise Exception("unknown state: " + self.state)
            elif self.state in self.ends:
                break
