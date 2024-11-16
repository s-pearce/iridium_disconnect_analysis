# -*- coding: utf-8 -*-
"""log_regexes.py

This module contains sets of regular expressions to identify specific phrases
that correspond to events within SFMC/Glider Terminal logs.  (e.g. identify
"callback 15" as a moment where the callback command is given and the glider
hangs up the Iridium phone.)

The comments document the regular expressions.

Created: Sep 25, 2024

@author: Stuart Pearce
"""
import re


# =============================================================================
# Intentional Iridium Disconnect Phrases:
#   This section is the set of phrases that signal an intentional (user issued
#   or automated) disconnection of the Iridium phone.  Any log file without
#   one or more of these are considered to have disconnected unintentionally, 
#   i.e. dropped.
#   
#   * For this subsection, several phrases may be included for each 
#       disconnect reason this is because communications can be messy and
#       it can be good to try and match as many as possible in case one is 
#       garbled or not printed entirely.
# =============================================================================

# 1. "callback" command:
#   The command used to hang up the Iridium phone and callback in X minutes. 
#   There are 2 variants, an out-of-mission version and an in-mission version 
#   that uses `H` as a shortcut.
#   Example: 
#   -----------------------------------------
#       GliderDos N -1 >callback 2
#       I am going to hangup the Iridium!
#       I will call you back in 2 minutes
#       at the primary number ( 88160000500 )
#   -----------------------------------------

#   callback result phrase:
#   could only use this phrase, but rarely a callback is taken and hangs up 
#   before printing the result, so I include the others.
callback1 = r'I am going to hangup the Iridium!'

#   out-of-mission version:
#   '[^_]' eliminates the case when "callback" is the end of a variable where
#       an underscore precedes it.  e.g. 'u_max_time_in_callback 900'
#   '\n' (line feed) terminates the line to show that enter was pressed and the
#       command was taken and the call not dropped before.
#   '(?: [01])*' captures if the optional primary or secondary phone number is
#       indicated.
callback2 = r'[^_]callback \d+(?: [01])*\n'

#   in-mission version:  Similar to above, but with 'H'
callback3 = r'H \d+(?: [01])*\n'


# 2. Control R:
#   The in-mission signal to end the call and continue the mission.
#   Example: 
#   -----------------------------------------
#   ^R  7955  0 behavior surface_4: User typed Control-R, resuming
#   
#      I heard a Control-R
#      RESUMING MISSION
#   
#     7956    00750001.mlg LOG FILE CLOSED
#   Doing system wide housekeeping.......
#       ...
#   Housekeeping is done
#   -----------------------------------------
housekeeping = r'Housekeeping is done'
# ctrlr1 = r'\^R'  # removing `ctrlr1` because this created a false positive in
#   one scenario when random characters were dumped to the screen following a 
#   G3 science bay transfer (which is a regular problem).
#   `ctrlr1` is redundant with `ctrlr2` and `ctrlr3` anyway and this false 
#   positive scenario could be a possibility for other users as well, although
#   it would be exceedingly rare.
ctrlr2 = r'I heard a Control-R'
ctrlr3 = r'User typed Control-R, resuming'


# 3. mission starts:
#   Regardless of how a mission starts, either by using "run", "sequence", 
#   the glider autoexecutes the next sequenced mission, or starts lastgasp or
#   initial.mi, the glider will report "Starting Mission:".
#   Example: 
#   -----------------------------------------
#   SEQUENCE: Running lastgasp.mi on try 0
#   SEQUENCE: Forcing use of critical devices
#   Starting Mission: lastgasp.mi
#   timestamp: Fri Sep 15 23:50:12 2023
#   load_mission(): Opening Mission file: lastgasp.mi
#   -----------------------------------------
#   It is necessary to do some special handling of the mistart regexes and so 
#   they won't be grouped together (see the regex compiling below).  Because
#   there are moments after starting a mission where it is possible to cancel
#   the mission starting and is possible a mission will abort on the start, 
#   if these phrases are seen, the remaining text must be checked for phrases
#   indicating the mission was canceled before disconnecting the Iridium call.
#   See below for more details, and the `log_disconnect_info` function in the
#   `iridium_analysis.py` module.
mistart1 = r'Starting Mission: [_a-zA-Z0-9]+\.mi'
mistart2 = r'load_mission\(\): Opening Mission file:'


# 4. "use" command:
#   The command that controls device usage.  Either putting devices in service
#   or taking devices out of service inherently does a reset of all devices, 
#   including the Iridium phone.  So the Iridium is temporarily disconnected
#   when the command is issued.
#   Example: 
#   -----------------------------------------
#    GliderDos N -1 >use + science_super
#   
#      science_super:ok
#    Exiting all devices ...
#    146830 61 disabling Iridium console...
#   -----------------------------------------
#   simliar to the callback command, using '[^_]' to eliminate cases where use
#   is part of a variable. e.g. m_bms_battery_in_use
usecmd = r'[^_]use (?:\+|-) [_A_Za-z0-9]+\n'

# 5. Freewave chosen to transmit files instead of Iridium
#   This is the rare case that someone is on a boat near a glider and when
#   transferring data, the glider chooses the faster Freewave over Iridium and
#   if an active Iridium call is in progress, the connection is dropped.  I 
#   don't necessarily consider that an intentional disconnect, but it shouldn't
#   count as a dropped Iridium call either
#   Example:
#   -----------------------------------------
#   GliderDos N -1 >send 0077*.ebd 0077*.dbd
#   SCIENCE DATA LOGGING: science IS running
#   CONSCI REQUESTED (using FREEWAVE as console)
#   -----------------------------------------
freewave_xfer = r'using FREEWAVE as console'


# 6. "exit" command:
#   exits for any reason also counts as a disconnect.  Should only be exit reset
#   during a deployment, but also captures exits or exit pico's at the end
#   to also count as an intentional disconnect.
#   Example: 
#   -----------------------------------------
#   GliderDos A 6 >exit reset
#   
#   Preparing to exit GliderDos
#   WAITING for all motors to be idle --and--
#               science power to be stable
#   ...
#   Exiting all devices ...
#   -----------------------------------------
exitreset = r'exit(?: reset| pico)*\n'


# 7. 'Exiting devices':
#   The phrase 'Exiting all devices' occurs both for the use command and any
#   variation of the exit command and so is the final catch all.
exitdevices = r'Exiting all devices'

# keeping a list of all the phrases if I want to select one at a time for
# future uses
intentional_rstrs = [
    callback1, callback2, callback3,
    housekeeping, ctrlr2, ctrlr3, freewave_xfer,
    usecmd, exitreset, exitdevices
    ]

# This compiles a long regular expression where each phrase is separated by "|"
# indicating "or".  So if 1 or more of the above phrases are present in the log 
# file, it will match for at least one of the individual regexs and the log 
# file be considered intentionally disconnected.
intentional_regex = re.compile(r"|".join(intentional_rstrs))

# The mission start regexes require separate logic than the rest because if
# found, they also must be checked that an initialized mission doesn't abort
# or isn't stopped by the user with a control C.  So these are grouped 
# separately than the others.  See how they are handled in the function 
# `log_disconnect_info` in the `iridium_analysis.py` module.
mi_start_regex = re.compile(mistart1 + r"|" + mistart2)

# =============================================================================
# Additional Phrases:

# =============================================================================

# GliderDos prompt:
#   Any time the GliderDos prompt is shown, it signals that a glider is out of
#   mission.  All other log files that are not out-of-mission are considered 
#   in-mission, which is more difficult to determine since a log can start
#   in-mission and exit or abort the mission during the call.
#   Examples: 
#   -----------------------------------------
#   GliderDos N -1 >
# or 
#   GliderDos I -3 >
# or 
#   GliderDos A 6 >
#   -----------------------------------------
gdos_reg = re.compile(r'GliderDos (?:A|N|I) -*\d+ >')


# Data transfer phrases:
#   During data transfer, these phrases occur.  They aren't used for Iridium
#   disconnections, but only to catalog which files dropped during a data
#   transfer when the last line looks like a transfer.
#   Example of last line: 
#   -----------------------------------------
#   Total Bytes sent/received: 19127
#   -----------------------------------------
xfer_reg = re.compile(r'Total Bytes sent/received:')

#   The file type could also be cataloged based on several lines back from
#   lines that indicate data transfer.
#   Example: 
#   -----------------------------------------
#   Starting zModem transfer of 00770005.tbd to/from ce_1012 size is 48551
#   -----------------------------------------
#   only sbd, tbd, scd, and tcd file extensions will be used to determine in 
#   mission science or flight data transfers, see `_determine_xfer_drops` in 
#   `iridium_analysis.py`.
#   This isn't necessarily true, but will likely be true >95% of the time.
#   If the file type is not determined, it will be considered "other".
xfer_type_reg = re.compile(r'Starting zModem transfer of \d+.([a-z]{3})')


# GPS Position line:
#   Each log file *should* have at least 1 GPS position line.  If not, it can
#   be considered a dropped call because it didn't even get far enough to 
#   print out the inital information.
#   However, since the Iridium and GPS share an antenna via a switch board,
#   the position becomes useful to indicate all log files that happen during
#   a single surfacing event. This is because the GPS position remains constant
#   until the Iridium phone releases control of the switch board, which only 
#   happens once it has intentionally disconnected or a timer runs out in which
#   case it gets a new position and dives. 
#   If GPS were otherwise actively being refreshed, the positions would differ
#   by small amounts each time.
#   Example GPS line: 
#   -----------------------------------------
#   GPS Location:  4430.530 N -12503.956 E measured    835.845 secs ago
#   -----------------------------------------
gps_reg = re.compile(r'GPS Location:  (\d{4}\.\d+ N -\d{5}\.\d+ E).+')