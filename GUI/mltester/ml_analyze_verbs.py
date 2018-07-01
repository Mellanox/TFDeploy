#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import sys
from mltester.actions.analyze_verbs import analyzeVerbs

#--------------------------------------------------------------------#

def main():
    if len(sys.argv) < 3:
        print "Usage: %s <request_starts_file> <requests_done_file> [output_dir]" % os.path.basename(sys.argv[0])
        sys.exit(1)
    output_dir = sys.argv[3] if len(sys.argv) >= 4 else None
    analyzeVerbs(sys.argv[1], sys.argv[2], output_dir)

#--------------------------------------------------------------------#

if __name__ == '__main__':
    main()