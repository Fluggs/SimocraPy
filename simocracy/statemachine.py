#!/usr/bin/env python3.4


class StateMachine:
    def __init__(self, endless=False, verbose=False):
        self.msg = "statemachine " + str(id(self)) + ": "
        self.verbose = verbose
        self.states = {}
        self.start = None
        self.ends = []
        self.state = None
        self.endless = endless

    def add_state(self, name, handler, end=False):
        if self.verbose:
            msg = self.msg + "state added: "
            hname = "None"
            if handler is not None:
                hname = handler.__name__
            print(msg + name + "; handler: " + hname)
        self.states[name] = handler
        if end:
            self.ends.append(name)
        
    def set_start(self, name):
        if self.verbose:
            print(self.msg + "start state set: " + name)
        if name in self.states:
            self.start = name
        else:
            raise Exception("unknown state: " + name)
        
    def run(self, verbose=None):
        if verbose is not None:
            self.verbose = verbose
        if self.verbose:
            print(self.msg + "running statemachine")
            
        if self.start is None:
            raise Exception("no start state given")
        if not self.endless and self.ends == []:
            raise Exception("no end state given")
            
        self.state = self.start
        
        while True:
            if self.verbose:
                print(self.msg + "state: "+self.state)
            self.state = self.states[self.state]()
            if self.state not in self.states:
                raise Exception("unknown state: " + self.state)
            elif self.state in self.ends:
                if self.verbose:
                    print(self.msg + "end state reached: "+self.state)
                if self.states[self.state] is not None:
                    self.states[self.state]()
                break
