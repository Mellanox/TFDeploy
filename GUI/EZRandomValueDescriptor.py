#!/usr/bin/python
# -*- coding: utf-8 -*-

from EZRange import *
from EZRandom import *

'''

ValueDescriptor -
    Description: Value-generation abstraction.

'''

#############################################################################

class ValueDescriptorParseException(Exception):
    pass

#############################################################################

class FixedValueDescriptor(object):
    
    def __init__(self, value):
        self._value = value
    
    #--------------------------------------------------------------------#
    
    def next(self):
        return self._value

#############################################################################

class EZRandomValueDescriptor(object):
    
    OL = 0
    INC = 1
    RAND = 2
    
    OP_NAMES = ["OL", "INC", "RAND"]
     
    #--------------------------------------------------------------------#
    
    def __init__(self, op, ezrand):
        self._range = ezrand
        self._op = op
        if self._op in [EZRandomValueDescriptor.OL, EZRandomValueDescriptor.INC]: 
            self._iterBegin()
    
    #--------------------------------------------------------------------#
    
    def _iterBegin(self):
        self._it = self._range.__iter__()
        
    #--------------------------------------------------------------------#
    
    def _iterNext(self):
        try:
            return self._it.next()
        except StopIteration:
            self._iterBegin()
            return self._it.next()
        
    #--------------------------------------------------------------------#
    
    def __repr__(self):
        if self._op == EZRandomValueDescriptor.RAND:
            return "%s" % str(self._range)
        return "%s: %s" % (EZRandomValueDescriptor.OP_NAMES[self._op], str(self._range))
        
    #--------------------------------------------------------------------#
    
    def ezrand(self):
        return self._range
    
    #--------------------------------------------------------------------#
    
    def next(self):
        if self._op == EZRandomValueDescriptor.OL:
            return self._iterNext()
        elif self._op == EZRandomValueDescriptor.INC:
            return self._iterNext()
        elif self._op == EZRandomValueDescriptor.RAND:
            return self._range.rand()
    
    #--------------------------------------------------------------------#
    
    @classmethod
    def parse(cls, s, enums = None):

        s = s.replace(" ", "")
        op = EZRandomValueDescriptor.RAND
        for i in range(len(EZRandomValueDescriptor.OP_NAMES)):
            op_name = EZRandomValueDescriptor.OP_NAMES[i]
            prefix = op_name + ":"
            if s.startswith(prefix):
                op = i
                s = s[len(prefix):]
                break
        
        try:
            ezrand = EZRandom(s, enums)
        except EZRandomParseException as ex:
            raise ValueDescriptorParseException(*ex.args)
        
        return cls(op, ezrand)
            
