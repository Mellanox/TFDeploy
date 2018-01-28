#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import time

# -------------------------------------------------------------------- #

class UniBorder():
    
    BAR = []
    
    ##################
    # Border styles: #
    ##################
    BORDER_STYLE_SINGLE  = 0
    BORDER_STYLE_STRONG  = 1
    BORDER_STYLE_DOUBLE  = 2
    BORDER_STYLE_ASCII   = 3
    
    #################
    # Border parts: #
    #################
    BORDER_PART_VERTICAL_LINE                   = 0
    BORDER_PART_HORIZONAL_LINE                  = 1
    BORDER_PART_TOP_LEFT_CORNER                 = 2
    BORDER_PART_TOP_RIGHT_CORNER                = 3
    BORDER_PART_BOTTOM_LEFT_CORNER              = 4
    BORDER_PART_BOTTOM_RIGHT_CORNER             = 5
    BORDER_PART_TOP_LEFT_CORNER_ROUND           = 6
    BORDER_PART_TOP_RIGHT_CORNER_ROUND          = 7
    BORDER_PART_BOTTOM_LEFT_CORNER_ROUND        = 8
    BORDER_PART_BOTTOM_RIGHT_CORNER_ROUND       = 9
    BORDER_PART_TOP_T                           = 10
    BORDER_PART_BOTTOM_T                        = 11
    BORDER_PART_RIGHT_T                         = 12
    BORDER_PART_LEFT_T                          = 13
    BORDER_PART_CROSS                           = 14
    BORDER_PART_NONE                            = 15
    
    VERTICAL_POSITION_HAS_TOP       = 1
    VERTICAL_POSITION_HAS_BOTTOM    = 2
    
    HORIZONAL_POSITION_HAS_LEFT     = 1
    HORIZONAL_POSITION_HAS_RIGHT    = 2
 
    _border_chars = [[ "│", "┃", "║", "|" ],
                     [ "─", "━", "═", "-" ],
                     [ "┌", "┏", "╔", "+" ],
                     [ "┐", "┓", "╗", "+" ],
                     [ "└", "┗", "╚", "+" ],
                     [ "┘", "┛", "╝", "+" ],
                     [ "╭", "┏", "╔", "+" ],
                     [ "╮", "┓", "╗", "+" ],
                     [ "╰", "┗", "╚", "+" ],
                     [ "╯", "┛", "╝", "+" ],
                     [ "┬", "┳", "╦", "+" ],
                     [ "┴", "┻", "╩", "+" ],
                     [ "┤", "┫", "╢", "+" ],
                     [ "├", "┣", "╟", "+" ],
                     [ "┼", "╋", "╬", "+" ],
                     [ " ", " ", " ", " " ]]
          
                                #  Nothing                      HAS LEFT                          HAS RIGHT                        HAS LEFT + RIGHT                     
    _junction_part_by_position = [[BORDER_PART_NONE,            BORDER_PART_HORIZONAL_LINE,        BORDER_PART_HORIZONAL_LINE,     BORDER_PART_HORIZONAL_LINE   ],  # Nothing
                                  [BORDER_PART_VERTICAL_LINE,   BORDER_PART_BOTTOM_RIGHT_CORNER,   BORDER_PART_BOTTOM_LEFT_CORNER, BORDER_PART_BOTTOM_T         ],  # HAS TOP
                                  [BORDER_PART_VERTICAL_LINE,   BORDER_PART_TOP_RIGHT_CORNER,      BORDER_PART_TOP_LEFT_CORNER,    BORDER_PART_TOP_T            ],  # HAS BOTTOM
                                  [BORDER_PART_VERTICAL_LINE,   BORDER_PART_RIGHT_T,               BORDER_PART_LEFT_T,             BORDER_PART_CROSS            ]]  # TOP + BOTTOM

    default_style = BORDER_STYLE_STRONG
        
    # -------------------------------------------------------------------- #
    
    @staticmethod
    def _get_vertical_position(has_top, has_bottom):
        return has_top * UniBorder.VERTICAL_POSITION_HAS_TOP + has_bottom * UniBorder.VERTICAL_POSITION_HAS_BOTTOM

    # -------------------------------------------------------------------- #
    
    @staticmethod
    def _get_horizonal_position(has_left, has_right):
        return has_left * UniBorder.HORIZONAL_POSITION_HAS_LEFT + has_right * UniBorder.HORIZONAL_POSITION_HAS_RIGHT
                                             
    # -------------------------------------------------------------------- #
    
    @staticmethod
    def _get_border_char_by_part(border_part, style = None):
        if style is None:
            style = UniBorder.default_style        
        return UniBorder._border_chars[border_part][style]
    
    # -------------------------------------------------------------------- #

    @staticmethod    
    def _get_border_part_by_direction(vertical_position, horizonal_position):
        return UniBorder._junction_part_by_position[vertical_position][horizonal_position]
    
    # -------------------------------------------------------------------- #
    
    @staticmethod    
    def _get_border_char(has_top, has_bottom, has_left, has_right, style = None):
        if style is None:
            style = UniBorder.default_style
        vertical_position   = UniBorder._get_vertical_position(has_top, has_bottom)
        horizonal_position  = UniBorder._get_horizonal_position(has_left, has_right)
        border_part         = UniBorder._get_border_part_by_direction(vertical_position, horizonal_position, style)
        return UniBorder._get_border_char_by_part(border_part)    

# -------------------------------------------------------------------- #

LOG_LEVEL_FATAL = 0
LOG_LEVEL_ERROR = 1
LOG_LEVEL_WARNING = 2
LOG_LEVEL_INFO = 3
LOG_LEVEL_DEBUG = 10
LOG_LEVEL_ALL = sys.maxint

LogLevelNames = ["FATAL", "ERROR", "WARNING", "INFO", "DEBUG", "NONE"]

# -------------------------------------------------------------------- #

def _streamWrite(stream, data):
    stream.write(data + "\n")
    stream.flush()

# -------------------------------------------------------------------- #

def _logWrite(data, process):
    _streamWrite(sys.stdout, data)

# -------------------------------------------------------------------- #

def _errorWrite(data, process):
    _streamWrite(sys.stderr, data)

# -------------------------------------------------------------------- #
    
g_log_level = LOG_LEVEL_INFO
g_file_level = LOG_LEVEL_ALL 
g_log_op = _logWrite
g_error_op = _errorWrite

# -------------------------------------------------------------------- #

def setLogLevel(log_level = None, file_level = None):
    global g_log_level
    global g_file_level 

    if log_level is not None:
        g_log_level = log_level 
    if file_level is not None:
        g_file_level = file_level
        
# -------------------------------------------------------------------- #

def setLogOps(log_op = None, error_op = None):
    global g_log_op
    global g_error_op 

    if log_op is not None:
        g_log_op = log_op 
    if error_op is not None:
        g_error_op = error_op        

# -------------------------------------------------------------------- #

def _doLog(msg, process, op):
    if process is None:
        pid = ""
    else:
        pid = " %u" % process.instance.pid
        
    msg = "[%s%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), pid, msg)
    if op is not None:
        op(msg, process)
    
# -------------------------------------------------------------------- #

def log(msg, process = None):
    _doLog(msg, process, g_log_op)

# -------------------------------------------------------------------- #

def error(msg, process = None):
    _doLog(msg, process, g_error_op)

# -------------------------------------------------------------------- #

def title(msg, style = UniBorder.BORDER_STYLE_STRONG, process = None):
    UniBorder.default_style = style
    bar = UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_HORIZONAL_LINE) * len(msg)
    log(UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_TOP_LEFT_CORNER) + bar + UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_TOP_RIGHT_CORNER), process)
    log(UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_VERTICAL_LINE) + msg + UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_VERTICAL_LINE), process)
    log(UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_BOTTOM_LEFT_CORNER) + bar + UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_BOTTOM_RIGHT_CORNER), process)


###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

class DummyProcess(object):
    def __init__(self, pid):
        self.pid = pid
        
def _testLogWrite(data, process):
    _logWrite("### TEST ### " + data, process)
    
def _testErrorWrite(data, process):
    _errorWrite("### TEST ### " + data, process)
    
if __name__ == '__main__':
    title("A title 1", UniBorder.BORDER_STYLE_ASCII)
    title("A title 2", UniBorder.BORDER_STYLE_SINGLE)
    title("A title 3", UniBorder.BORDER_STYLE_DOUBLE)
    title("A title 4", UniBorder.BORDER_STYLE_STRONG, DummyProcess(1111))
    
    log("A message")
    log("A message 2", DummyProcess(2222))
    log("A message 3", DummyProcess(3333))
    time.sleep(0.2)
    error("An error message")
    error("An error message 2", DummyProcess(9999))

    time.sleep(0.2)
    title("Let's try to override")
        
    setLogOps(_testLogWrite, _testErrorWrite)
    
    log("")
    log("A new message")
    log("A new message 2", DummyProcess(20000))
    time.sleep(0.2)    
    error("A new error")
    error("A new error 2", DummyProcess(40000))
    time.sleep(0.2)
    title("Override!")
