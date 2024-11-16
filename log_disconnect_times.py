# -*- coding: utf-8 -*-
"""Functions to estimate the length of time a glider iridium call was connected
from various sources. E.g. the SFMC dockserver logs, the glider terminal log
itself, or from glider data

Created: Sep 2024
@author: Stuart Pearce
"""
import os
import re
from datetime import datetime as dt
from datetime import timedelta as td


def first_of_next_month(dto):
    yr = dto.year
    mnth = dto.month
    nextmnth = mnth + 1
    if nextmnth == 13:
        nextmnth = 1
        yr += 1
    return dt(yr, nextmnth, 1)
    

def sfmclog_disconnect_time(dto, glidername):
    # While this code works, it turns out the sfmc-dockserver logs in 8.5 are 
    # unreliable because it looks like another logging function accidentally 
    # overwrites the logs and creates the weirdly named log files *see the 
    # `logfilename` variable creation below, at least for SFMC version 8.5.
    # So it only gets a valid disconnection time about 40% of the time.
    sfmc_log_dir = "/var/log/sfmc-dockserver/"
    # get date from datetime
    dtdate = dto.strftime("%Y%m%d")
    dtstr = dto.strftime("%Y%m%dT%H%M%S")
    # get first day date of the next month for sfmc log name
    nextmonth = first_of_next_month(dto)
    nextmnthstr = nextmonth.strftime('%Y%m%d')
    logfilename = "dockServer_{}.log-{}".format(dtdate, nextmnthstr)
    sfmclogpath = os.path.join(sfmc_log_dir, logfilename)
    # open "/var/log/sfmc-dockserver/dockServer_<yyyymmdd>.log-<yyyymmdd_of_nextmonth>"
    #  *and yes that is filename format.  On SFMC 8.5 the sfmc-dockserver log 
    #  creation is screwed up in some way.
    with open(sfmclogpath) as fid:
        filetext = fid.read()
        if dtstr in filetext:
            dtstr_byte = filetext.find(dtstr)
            fid.seek(dtstr_byte)
            line = fid.readline()
            disconnect_str = "Glider {}: Disconnect Event".format(glidername)
            disconnect_line = ""
            for line in fid.readlines():
                if disconnect_str in line:
                    disconnect_line = line
                    break
            if disconnect_line:
                disconnect_time = re.search(r'^(\d{8}T\d{6}) - ', line).group(1)
                return dt.strptime(disconnect_time, "%Y%m%dT%H%M%S")
            else:
                return None


# example time line in a glider terminal log
# Curr Time: Sat May 12 04:25:39 2018 MT:  116230
time_regex = re.compile(
    r'^Curr Time: [A-Z][a-z]{2} ([A-Z][a-z]{2} +\d+ \d{2}:\d{2}:\d{2} \d{4}) '
    r'MT: +(\d+)$', re.MULTILINE)

mt_regex = re.compile(r'^ *(\d+) +.+$', re.MULTILINE)

def parse_gliderlog_timelines(text):
    matches = time_regex.findall(text)
    if matches:
        lasttstr, lastmtime = matches[-1]
        ts = dt.strptime(lasttstr, '%b %d %H:%M:%S %Y')
        mt = int(lastmtime)
        return ts, mt
    else:
        return None, None
    

def logfile_disconnect_time(logfile):
    with open(logfile) as fid:
        filetext = fid.read()
    refts, refmt = parse_gliderlog_timelines(filetext)
    if refts and refmt:
        lastmt = find_last_mt(filetext)
        if lastmt and lastmt > refmt:
            lastfts = refts + td(seconds=(lastmt - refmt))
        else:
            lastfts = refts
        return lastfts
    else:
        return None


def find_last_mt(filetext):
    mtmatches = mt_regex.findall(filetext)
    if mtmatches:
        return int(mtmatches[-1])
    else:
        return None


def analyze_logtimes(logfile):
    lots = log_open_datetime(logfile)
    lcts = logfile_disconnect_time(logfile)
    if lots and lcts:
        tdiff = (lcts - lots).total_seconds()
    else:
        tdiff = None
    print("open: {}, close: {}, elapsed: {}".format(lots, lcts, tdiff))