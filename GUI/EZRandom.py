#!/usr/bin/python
# -*- coding: utf-8 -*-

from EZRange import *
from random import randint

#############################################################################

class EZRandomParseException(Exception):
    pass

#############################################################################

class EZRandomToken(object):
    
    def __init__(self, range, weight, disp):
        self.range = range
        self.weight = weight
        self.disp = disp
        
    def __repr__(self):
        if self.weight == 1:
            return self.disp
        return "%s: %u" % (self.disp, self.weight)
        
#############################################################################

class EZRandom(EZIRange):
    
    class Iterator(object):
        def __init__(self, ezrand):
            self._ezrand = ezrand
            self._moveToToken(0)
            
        def _moveToToken(self, token_num):
            self._token_num = token_num
            if self._token_num >= len(self._ezrand._tokens):
                raise StopIteration
            self._it = self._ezrand._tokens[self._token_num].range.__iter__()
            
        def next(self):
            try:
                return self._it.next()
            except StopIteration:
                self._moveToToken(self._token_num + 1)
                return self._it.next()
        
    #--------------------------------------------------------------------#
    
    def __init__(self, st, enums = None):
        self._enums = enums
        self._tokens = []
        self._total_weight = 0
        
        st = st.replace(" ", "")
        tokens = st.split(',')
        if len(tokens) == 0:
            raise EZRandomParseException("0 tokens parsed.")
        
        for i in range(len(tokens)):
            token = self._tryParseToken(i, tokens[i])
            self._tokens.append(token)
            self._total_weight += token.weight
    
    #--------------------------------------------------------------------#
            
    def _tryParseValue(self, i, type, st):
        
        #************************
        # Try to get enum value:
        #************************
        if self._enums != None:
            for enum in self._enums:
                if st in enum.keys():
                    return enum[st]

        #**********************
        # Try to parse as int:
        #**********************
        try:
            return int(st, 0)
        except ValueError:
            raise EZRandomParseException("Token %u: Invalid %s '%s'." % (i, type, st))        
    
    #--------------------------------------------------------------------#
    
    def _tryParseToken(self, i, token):
        if len(token) == 0:
            raise EZRandomParseException("Token %u: cannot be empty." % i)

        parts = token.split(':')
        if len(parts) == 1:
            expression = parts[0]
            weight = 1
        elif len(parts) == 2:
            expression = parts[0]
            weight = self._tryParseValue(i, "weight", parts[1])
        else:
            raise EZRandomParseException("Token %u: Too many colons (%u)." % (i, len(parts) - 1))

        #*******************
        # Parse expression:
        #*******************
        if len(expression) == 0:
            raise EZRandomParseException("Token %u: expression value is empty." % i)
        
        parts = expression.split('-')
        if len(parts) == 1:
            start = self._tryParseValue(i, "value", parts[0])
            end = start
            disp = parts[0]
        elif len(parts) == 2:
            start = self._tryParseValue(i, "value", parts[0])
            end = self._tryParseValue(i, "end", parts[1])
            disp = "%s-%s" % (parts[0], parts[1])  
        else:
            raise EZRandomParseException("Token %u: invalid number of hyphens (%u)." % (i, len(parts) - 1))
            
        range = EZIntRange(start, end)
                    
        return EZRandomToken(range, weight, disp)

    #--------------------------------------------------------------------#
    
    def __repr__(self):
        return ", ".join([str(token) for token in self._tokens])

    #--------------------------------------------------------------------#
    
    def __iter__(self):
        return EZRandom.Iterator(self)

    #--------------------------------------------------------------------#
    
    def __contains__(self, value):    
        raise NotImplementedError()
                
    #--------------------------------------------------------------------#
        
    def tokens(self):
        return self._tokens
    
    #--------------------------------------------------------------------#
    
    def rand(self):
        desc = randint(0, self._total_weight - 1)
        for token in self._tokens:
            if token.weight > desc:
                return token.range.rand()
            desc -= token.weight 
