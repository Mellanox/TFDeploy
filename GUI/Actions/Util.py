#!/usr/bin/python
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import threading

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

def log_write(msg, process, stream):
    pid = "" if process is None else " %u" % process.pid
    stream.write("[%s%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), pid, msg))
    stream.flush()
    
# -------------------------------------------------------------------- #

def log(msg, process = None):
    log_write(msg, process, sys.stdout)

# -------------------------------------------------------------------- #

def error(msg, process = None):
    log_write(msg, process, sys.stderr)

# -------------------------------------------------------------------- #

def title(msg, style = UniBorder.BORDER_STYLE_STRONG, process = None):
    UniBorder.default_style = style
    bar = UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_HORIZONAL_LINE) * len(msg)
    log(UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_TOP_LEFT_CORNER) + bar + UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_TOP_RIGHT_CORNER), process)
    log(UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_VERTICAL_LINE) + msg + UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_VERTICAL_LINE), process)
    log(UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_BOTTOM_LEFT_CORNER) + bar + UniBorder._get_border_char_by_part(UniBorder.BORDER_PART_BOTTOM_RIGHT_CORNER), process)
    
# -------------------------------------------------------------------- #

def processCommunicateTarget(process):
    _, err = process.communicate()
    if process.returncode != 0:
        error(err[:-1])            
        error("Command failed. Sorry")

# -------------------------------------------------------------------- #

def processCommunicateLive(process, on_output = None, on_error = None):
    while True:
        out = process.stdout.readline()
        err = process.stderr.readline()
        if (out == "") and (err == "") and (process.poll() is not None):
            break
        if (out != "") and (on_output is not None):
            on_output(out[:-1], process)
        if (err != "") and (on_error is not None):
            on_error(err[:-1], process)

# -------------------------------------------------------------------- #

def waitForProcesses(processes, wait_timeout = None, on_output = None, on_error = None):
    '''
    Wait for a group of processes to finish, but run them in parallel.
    '''
    log("Waiting for processes: %s" % [process.pid for process in processes])    
    threads = []
    start_times = []
    for process in processes:
        thread = threading.Thread(target=processCommunicateLive, args=(process,on_output,on_error))
        threads.append(thread)
        thread.start()

    all_ok = True
    elapsed = 0
    while elapsed < wait_timeout:
        num_remaining_processes = len(processes)
        i = 0
        while i < num_remaining_processes:
            process = processes[i]
            thread = threads[i]
            if not thread.is_alive():
                if process.returncode != 0:
                    error("Process %u exited with error code %u (elapsed: %.2lf)" % (process.pid, process.returncode, elapsed))
                    all_ok = False
                else:
                    log("Process %u finished successfully (elapsed: %.2lf)" % (process.pid, elapsed))
                processes.pop(i)
                threads.pop(i)
                num_remaining_processes -= 1
            else:
                i += 1
        if len(processes) == 0:
            break
        elapsed += 0.1
        time.sleep(0.1)
            
    # All remaining threads got timeout:            
    for thread in threads:
        error("Process %u got timeout (%.2lf)." % (process.pid, wait_timeout))
        all_ok = False
    return all_ok

# -------------------------------------------------------------------- #

def executeCommand(command):
    log("Running command: %s" % command)
    process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process

# -------------------------------------------------------------------- #

def executeRemoteCommand(servers, command, user = None):
    processes = []
    for server in servers:
        remote = server if user is None else "%s@%s" % (user, server)
        process = executeCommand("ssh %s -C \"%s\"" % (remote, command))
        processes.append(process)
    return processes

# -------------------------------------------------------------------- #

def copyToRemote(servers, sources, remote_dir, user = None):
    processes = []    
    for server in servers:
        remote = server if user is None else "%s@%s" % (user, server)
        remote_copy_cmd = "scp -r " + " ".join(sources) + " %s:%s" % (remote, remote_dir)
        process = executeCommand(remote_copy_cmd)
        processes.append(process)
    return processes


###############################################################################################################################################################
#
#                                                                         DEMO
#
###############################################################################################################################################################

if __name__ == '__main__':
    title("Running some processes:")
    processes = []
    processes.append(executeCommand("echo A"))
    processes.append(executeCommand("echo B"))
    processes.append(executeCommand("echo C"))
    processes.append(executeCommand("a_bad_command"))
    processes.append(executeCommand("ls /x/x/x/x/x/"))
    processes.append(executeCommand("echo D"))    
    processes.append(executeCommand("sleep 2"))
    processes.append(executeCommand("echo E"))    
    processes.append(executeCommand("sleep 999"))
    processes.append(executeCommand("echo F"))    

    title("Waiting for processes:", style=UniBorder.BORDER_STYLE_DOUBLE)
    waitForProcesses(processes, 5, log, error)    