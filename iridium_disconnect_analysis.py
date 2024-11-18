# -*- coding: utf-8 -*-
"""iridium_disconnect_analysis

A module with functions intended to quantify Iridium call disconnections by 
analyzing the glider terminal logs to see which calls are disconnected 
intentionally or are dropped connections.

The primary function to use is `logsdir_iridium_analysis` and input is a 
directory where the glider terminal logs can be found for a deployment.  
(e.g. "/var/opt/gmc/gliders/<glider name>/logs/"  on an SFMC or Dockserver
 installation)

A dictionary summary of the results and a pandas dataframe with each log file
analyzed is returned.

Created: Sep 24 2024
@author: Stuart Pearce
"""


# %% imports
import glob
import re
import os
import logging

from datetime import datetime as dt

import pandas as pd
import numpy as np

from log_regexes import intentional_regex, gdos_reg, xfer_reg, xfer_type_reg
from log_regexes import mi_start_regex


# %% setup logger
logger = logging.getLogger("iridium_analysis")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s: %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)


# %%
# Regular Expression to read log file open time from a glider terminal log
#sfmclogreg = re.compile(r'[_a-z0-9]+_(\d{8}T\d{6})_network_net_\d+.log')
logreg = re.compile(r'(\d{8}T\d{6})')


def log_open_dtstr(logfile):
    """Parse the file open time from the filename of a glider terminal log

    Parameters
    ----------
    logfile : str
        path to a glider terminal log file with time as part of the filename

    Returns
    -------
    dtstr : str
        The timestamp string from the filename.

    """
    fn = os.path.basename(logfile)
    match = logreg.search(fn)
    if not match:
        logger.error(
            "cannot determine open time from log filename {}".format(logfile))
        return
    dtstr = match.group(1)
    return dtstr


def log_open_datetime(logfile):
    """Parse the file open time from the filename of a glider terminal log

    Parameters
    ----------
    logfile : str
        path to a glider terminal log file with time as part of the filename

    Returns
    -------
    dto : datetime
        The log file open time as a datetime object

    """
    dtstr = log_open_dtstr(logfile)
    dto = dt.strptime(dtstr, '%Y%m%dT%H%M%S')
    return dto



# %% log disconnect intentions

def log_disconnect_info(logfile):
    """Compile information about an Iridium call from a glider terminal log
    

    Parameters
    ----------
    logfile : str
        path to a glider terminal log file

    Returns
    -------
    open_time : datetime.datetime object
        The date and time the log was opened
    intentional_disconnect : bool
        True if a call was disconnected intentionally, False if it was dropped
    in_mission : bool
        True if the glider was in mission for the entirety of the call duration
        False if the glider was out of a mission for any amount of time during
        the call duration
    drop_xfer : bool
        True if the call was dropped (`intentional_disconnect` is False) and 
        the call was dropped during a data transfer (Zmodem transfer).
    flight_xfer : bool
        True if the call was dropped during a flight data transfer
    sci_xfer : bool
        True if the call was dropped during a science data transfer
    other_xfer : bool
        True if the call was dropped during a data transfer, but the type was
        not determined

    """
    open_time = log_open_datetime(logfile)
    with open(logfile, 'r', errors="replace") as fid:
        try:
            filetext = fid.read()
        except UnicodeDecodeError as e:
            logger.error("{} not loading".format(logfile))
            raise e

    # Check if log has any out of mission portions first
    rematch = gdos_reg.search(filetext)
    if rematch:
        in_mission = False
    else:
        in_mission = True

    # If a mission has been started during a log it is a special case. The log
    # has to be checked to make sure that the stared mission isn't canceled or 
    # aborted before the call is disconnected because there is a lot of time
    # ways that it can fail, and users are given the opportunity to stop it.
    # So we take the remaining part of the file and make sure that a control C
    # or an abort don't happen before the end of the file.
    intentional_disconnect = False
    matchlist = list(mi_start_regex.finditer(filetext))
    if matchlist:
        filetext = filetext[matchlist[-1].end():]
        # Note that here filetext is shortened to everything after an attempt
        # to start a mission because everything that comes after is what
        # determines intentional disconnect or not.
        if not re.search(r"\^C|Mission completed ABNORMALLY", filetext):
            intentional_disconnect = True

    if not intentional_disconnect:  # can't be an `else` situation so that 
        # positive `matchlist` can still be checked for other disconnects
        rematch = intentional_regex.search(filetext)
        if rematch:
            intentional_disconnect = True

    drop_xfer, flight_xfer, sci_xfer, other_xfer = _determine_xfer_drops(filetext)
    
    if intentional_disconnect or drop_xfer:
        assert drop_xfer != intentional_disconnect, (
            "Error of dropped call assertion. There appear to be conflicts in "
            "{}".format(logfile))
    
    return open_time, intentional_disconnect, in_mission, drop_xfer, flight_xfer, sci_xfer, other_xfer


def _determine_xfer_drops(filetext):
    """determine the type of data transfer when an Iridium call is dropped

    Parameters
    ----------
    filetext : str
        The entire file text of a glider terminal log from the `read` method
        of the open file object.

    Returns
    -------
    drop_xfer : bool
        True if a call was dropped during data transfer
    flight_xfer : TYPE
        True if a call was dropped during flight data transfer
    sci_xfer : TYPE
        True if a call was dropped during science data transfer
    other_xfer : TYPE
        True if a call was dropped during data transfer, but bay source is 
        unknown.
        
    """
    filelines = filetext.split('\n')
    rematch = xfer_reg.search(filelines[-1])
    if rematch:
        drop_xfer = True
    else:
        drop_xfer = False
    
    flight_xfer = False
    sci_xfer = False
    other_xfer = False
    file_xfer_type = None
    if drop_xfer:
        filelines.reverse()
        reverse_filetext = "\n".join(filelines)
        rematch = xfer_type_reg.search(reverse_filetext)
        if rematch:
            file_xfer_type = rematch.group(1)
            if re.match(r's[bc]d', file_xfer_type.lower()):
                flight_xfer = True
            elif re.match(r't[bc]d', file_xfer_type.lower()):
                sci_xfer = True
            else:
                other_xfer = True
    return drop_xfer, flight_xfer, sci_xfer, other_xfer


def determine_xfer_drops(file):
    """determine the type of data transfer when an Iridium call is dropped

    Parameters
    ----------
    file : str
        the path to a glider terminal log file for analyzing if an Iridium 
        dropped during a data transfer.

    Returns
    -------
    drop_xfer : bool
        True if a call was dropped during data transfer
    flight_xfer : TYPE
        True if a call was dropped during flight data transfer
    sci_xfer : TYPE
        True if a call was dropped during science data transfer
    other_xfer : TYPE
        True if a call was dropped during data transfer, but bay source is 
        unknown.

    """
    with open(file) as fid:
        filetext = fid.read()
    return _determine_xfer_drops(filetext)


def _analyze_logfiles(logfiles):
    return np.array(list(map(log_disconnect_info, logfiles)))


def analyze_logfiles(logfiles):
    """Analyze Iridium call connect and disconnect information for a glider 
    deployment from the glider terminal log files

    Parameters
    ----------
    logfiles : list or seq
        a sequence of string paths to log files to analyze

    Returns
    -------
    df : pandas dataframe
        analysis results table, with a line for each log file and a boolean
        table for disconnection (True if intended, False if dropped),
        in-mission, drops during data transfers, and category of data transfer
        drop (flight, science, or other)

    """
    results = _analyze_logfiles(logfiles)
    df = pd.DataFrame(
        results, 
        index=map(os.path.basename, logfiles), 
        columns= [
            'open time', 'disconnect', 'in-mission', 'data transfer drop', 
            'flight xfer drop', 'science xfer drop', 'other data xfer drop'])
    df.index.name = "log file"
    return df


def logcall_summary(logcall_dataframe):
    """Summarize Iridium analysis from `analyze_logfiles` output

    Parameters
    ----------
    logcall_dataframe : pandas dataframe
        A dataframe of the results from `analyze_logfiles`

    Returns
    -------
    outdict : dict
        Dictionary of results summary from glider deployment.

    """
    intentional_disc = logcall_dataframe["disconnect"]
    in_mission = logcall_dataframe["in-mission"]
    data_xfer_drops = logcall_dataframe["data transfer drop"]
    flight_xfer_drops = logcall_dataframe["flight xfer drop"]
    science_xfer_drops = logcall_dataframe["science xfer drop"]
    other_xfer_drops = logcall_dataframe["other data xfer drop"]
    
    
    # logical opposite determinations
    drops = np.logical_not(intentional_disc)
    gliderdos = np.logical_not(in_mission)
    
    # initial counts
    n_calls = len(logcall_dataframe.index)
    n_drops = sum(drops)
    n_int_disc = sum(intentional_disc)
    n_inmis = sum(in_mission)
    n_gdos = sum(gliderdos)
    n_fli_xfer_drops = sum(flight_xfer_drops)
    n_sci_xfer_drops = sum(science_xfer_drops)
    n_other_xfer_drops = sum(other_xfer_drops)
    
    # Total dropped call rate and intentional disconnects rate
    drop_call_rate = n_drops / n_calls
    int_disc_rate = n_int_disc / n_calls

    # determine in mission drop call rate
    inmis_drops = np.logical_and(in_mission, drops)
    inmis_discs = np.logical_and(in_mission, intentional_disc)
    n_inmis_drops = sum(inmis_drops)
    n_inmis_discs = sum(inmis_discs)

    assert n_inmis_drops + n_inmis_discs == n_inmis, (
        "In mission drops and disconnects don't add up")
    inmis_drop_rate = n_inmis_drops / n_inmis if n_inmis > 0 else 0
    inmis_disc_rate = n_inmis_discs / n_inmis if n_inmis > 0 else 0
    
    # determine out of mission drop call rate
    gdos_drops = np.logical_and(gliderdos, drops)
    gdos_discs = np.logical_and(gliderdos, intentional_disc)
    n_gdos_drops = sum(gdos_drops)
    n_gdos_discs = sum(gdos_discs)
    assert n_gdos_drops + n_gdos_discs == n_gdos, (
        "gliderdos drops and disconnects don't add up")
    gdos_drop_rate = n_gdos_drops / n_gdos if n_gdos > 0 else 0
    gdos_disc_rate = n_gdos_discs / n_gdos if n_gdos > 0 else 0
    
    # determine data transfer drop rates
    n_data_xfer_drops = sum(data_xfer_drops)
    data_xfer_drop_rate = n_data_xfer_drops / n_drops if n_drops > 0 else 0
    
    # in and out of mission (out = gliderdos) data transfer drop rates
    mis_xfer_drops = np.logical_and(data_xfer_drops, inmis_drops)
    n_mis_xfer_drops = sum(mis_xfer_drops)
    gdos_xfer_drops = np.logical_and(data_xfer_drops, gdos_drops)
    n_gdos_xfer_drops = sum(gdos_xfer_drops)
    
    # flight, science, or other data tranfsfer drop rates
    tmpn = n_data_xfer_drops
    fli_xfer_drop_rate = n_fli_xfer_drops / tmpn if tmpn > 0 else 0
    sci_xfer_drop_rate = n_sci_xfer_drops / tmpn if tmpn > 0 else 0
    other_xfer_drop_rate = n_other_xfer_drops / tmpn if tmpn > 0 else 0
    
    # flight, and science data transfer drop rates in mission
    tmpn = n_mis_xfer_drops
    n_fli_xfer_drops_inmis = sum(np.logical_and(
        mis_xfer_drops, flight_xfer_drops))
    inmis_fli_xfer_drop_rate = n_fli_xfer_drops_inmis / tmpn if tmpn > 0 else 0
    n_sci_xfer_drops_inmis = sum(np.logical_and(
        mis_xfer_drops, science_xfer_drops))
    inmis_sci_xfer_drop_rate = n_sci_xfer_drops_inmis / tmpn if tmpn > 0 else 0
    n_oth_xfer_drops_inmis = sum(np.logical_and(
        mis_xfer_drops, other_xfer_drops))
    inmis_oth_xfer_drop_rate = n_oth_xfer_drops_inmis / tmpn if tmpn > 0 else 0
    
    # flight, and science data transfer drop rates out of mission (gliderdos)
    tmpn = n_gdos_xfer_drops
    n_fli_xfer_drops_gdos = sum(np.logical_and(
        gdos_xfer_drops, flight_xfer_drops))
    gdos_fli_xfer_drop_rate = n_fli_xfer_drops_gdos / tmpn if tmpn > 0 else 0
    n_sci_xfer_drops_gdos = sum(np.logical_and(
        gdos_xfer_drops, science_xfer_drops))
    gdos_sci_xfer_drop_rate = n_sci_xfer_drops_gdos / tmpn if tmpn > 0 else 0
    n_oth_xfer_drops_gdos = sum(np.logical_and(
        gdos_xfer_drops, other_xfer_drops))
    gdos_oth_xfer_drop_rate = n_oth_xfer_drops_gdos / tmpn if tmpn > 0 else 0
    
    # compile the dictionary of results
    outdict = {
        "N total calls": n_calls,
        # counts
        "N drops": n_drops,
        "N disconnects": n_int_disc,
        "N mission calls": n_inmis,
        "N gliderdos calls": n_gdos,
        "N mission drops": n_inmis_drops,
        "N mission disconnects": n_inmis_discs,
        "N gliderdos drops": n_gdos_drops,
        "N gliderdos disconnects": n_gdos_discs,
        "N data transfer drops": n_data_xfer_drops,
        "N mission data transfer drops": n_mis_xfer_drops,
        "N gliderdos data transfer drops": n_gdos_xfer_drops,
        "N flight data transfer drops": n_fli_xfer_drops,
        "N science data transfer drops": n_sci_xfer_drops,
        "N other data transfer drops": n_other_xfer_drops,
        "N mission flight data transfer drops": n_fli_xfer_drops_inmis,
        "N mission science data tranfer drops": n_sci_xfer_drops_inmis,
        "N mission other data transfer drops": n_oth_xfer_drops_inmis,
        "N gliderdos flight data trasfer drops": n_fli_xfer_drops_gdos,
        "N gliderdos science data transfer drops": n_sci_xfer_drops_gdos,
        "N gliderdos other data transfer drops": n_oth_xfer_drops_gdos,
        # rates
        "disconnects (%)": int_disc_rate * 100,
        "dropped calls (%)": drop_call_rate * 100,
        "mission drops (%)": inmis_drop_rate * 100,
        "mission disconnects (%)": inmis_disc_rate * 100,
        "gliderdos drops (%)": gdos_drop_rate * 100,
        "gliderdos disconnects (%)": gdos_disc_rate * 100,
        "data transfer drops (%)": data_xfer_drop_rate * 100,
        "flight transfer drops (%)": fli_xfer_drop_rate * 100,
        "science transfer drop (%)": sci_xfer_drop_rate * 100,
        "other transfer drops (%)": other_xfer_drop_rate * 100,
        "mission flight transfer drops (%)": inmis_fli_xfer_drop_rate * 100,
        "mission science transfer drops (%)": inmis_sci_xfer_drop_rate * 100,
        "mission other transfer drops (%)": inmis_oth_xfer_drop_rate * 100,
        "gliderdos flight transfer drops (%)": gdos_fli_xfer_drop_rate * 100,
        "gliderdos science transfer drops (%)": gdos_sci_xfer_drop_rate * 100,
        "gliderdos other transfer drops (%)": gdos_oth_xfer_drop_rate * 100
    }
    return outdict


def logsdir_iridium_analysis(logsdir):
    """Iridium call disconnect info about a glider deployment from log files
    
    Provide the path to a directory of glider terminal logs and 
    `logsdir_iridium_analysis` will analyze and summarize information about 
    Iridium call disconnections for a deployment from glider terminal logs, 
    assuming `logsdir` points to a directory of glider terminal logs for 1 
    Slocum glider deployment.
    Specifically determines if each call (based on its corresponding log file)
    was disconnected with intention, or unintentionally dropped.  If a call is
    dropped, it attempts to provide if a call was dropped during data file 
    transfers.
    
    Summarizes percentages and totals of call connection information.

    Parameters
    ----------
    logsdir : str
        the path to a glider deployment logs directory

    Returns
    -------
    summary_results : dict
        the summary numbers for Iridium calls
    analysis_df : pandas dataframe
        analysis results table, with a line for each log file and a boolean
        table for disconnection type (True if intended, False if dropped),
        in-mission or not, drops during data transfers, and category of data 
        transfer drop (flight, science, or other)

    """
    logfile_pat = os.path.join(logsdir, '*.log')
    logfiles = glob.glob(logfile_pat)
    if len(logfiles) == 0:
        logger.error(f"No glider terminal logs found at {logsdir}")
        return

    analysis_df = analyze_logfiles(logfiles)
    summary_results = logcall_summary(analysis_df)
    logopentimes = analysis_df["open time"]
    len_days_fromlogs = (logopentimes[-1] - logopentimes[0]).total_seconds() / 86400
    summary_results['length_days_from_logs'] = len_days_fromlogs
   
    return summary_results, analysis_df

