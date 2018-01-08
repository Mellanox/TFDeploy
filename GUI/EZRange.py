#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from random import randint

#############################################################################
# Range interface:
#############################################################################

class EZIRange(object):
    def __init__(self):
        raise NotImplementedError()

    def __iter__(self):
        raise NotImplementedError()

    def __contains__(self, value):    
        raise NotImplementedError()
    
    def rand(self):
        raise NotImplementedError()

#############################################################################
# EZIntRange
#############################################################################

class EZIntRange(EZIRange):
    
    class Iterator(object):
        def __init__(self, range):
            self._current = range._start
            self._end = range._end
            
        def next(self):
            if self._current > self._end:
                raise StopIteration
            
            self._current += 1
            return self._current - 1

    #--------------------------------------------------------------------#
        
    def __init__(self, start, end):
        self._start = start
        self._end = end
    
    #--------------------------------------------------------------------#
    
    def __iter__(self):
        return EZIntRange.Iterator(self)

    #--------------------------------------------------------------------#

    def __contains__(self, value):
        return (value >= self._start) and (value <= self._end)  

    #--------------------------------------------------------------------#
            
    def rand(self):
        return randint(self._start, self._end)

