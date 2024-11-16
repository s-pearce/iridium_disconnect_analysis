# -*- coding: utf-8 -*-
"""ooice_iridium_analysis

An example module that runs an Iridium call drop rate analysis on 
OOI Coastal Endurance gliders.

These functions are unique to the OOI-CE system, but could easily be adapted
for anyone's system by changing directories, creating a JSON metadata file for
any information you want to pair with the analysis (e.g. G2 vs G3 glider) and 
how that information is accessed in the scripts, changing the regular 
expressions, and editing how deployment identification is done for your glider 
operations.

So if you want to use this analysis, make a copy of this module and edit to
use with your system.

Created: Oct 7 2024
@author: Stuart Pearce
"""
import re
import os
import json
import logging
import glob

from datetime import datetime as dt

import pandas as pd
import matplotlib.pyplot as plt

from iridium_analysis import logsdir_iridium_analysis

# grab and use the logger created from the iridium analysis module
logger = logging.getLogger("iridium_analysis")


#%% OOI-CE unique setup
# This section, the directories, the regex, and metadata file load are unique 
# to OOI-CE's system.


# glider_utils is a module unique to OOI-CE and reads from a google doc to 
# get deployment start and end times.  Adjust as needed for your group.
from glider_utils import google

# Directory variables unique to OOI-CE
# My root level location for writing results.  
# function will create the actual directory in this root level directory.
proj_root = "/home/stuart/projects/iridium_issue"

# create a directory name specific to this run (different directories were only
# useful in running multiple times with each code update, edit as needed).
# `full_run_ooice_log_call_analysis` uses these and actually creates the
# directory below. `run_time_str` is also used in the full results filename.

write_dirname = os.path.join(proj_root, "deployments")

# Data root is OOI-CE's root directory for stored data, including the glider
# terminal logs saved from each deployment
dataroot = "/home/doris/gliders/nasrawdata/"

# A regular expression phrase to get glider serial number and deployment number
# from the glider terminal logs directory input specific to OOI directory
# naming conventions
fileregex = re.compile(r'ce05moas-gl*(\d{3,4})(?:\\|/)(D\d{5})')

# load a json metadata file specific to OOI-CE glider deployments (created
# externally to this script) into a dictionary
ooice_f_and_gtypes_file = os.path.join(
    proj_root,
    "deploy_iridium_metadata.json")

with open(ooice_f_and_gtypes_file) as fid:
    fin_and_gtypes = json.load(fid)


#%%% Deployment level results write helper functions

# These are unique to OOI-CE in that the information is stored based on glider
# serial number and deployment number, which I have chosen to use as the
# deployment identifier.  Edit as needed.

def write_analysis_csv(analysis_df, write_dir):
    """Write results from iridium_analysis for a deployment to a csv file

    Writes a short header of deployment information and then writes a results
    line for each log file analyzed from the glider deployment with boolean 
    information for disconnect intention (True for intended, False if call was 
    dropped), whether it was in-mission, and if dropped, whether or not it was
    during a data transfer, and if so, the estimated type of data transfer
    (flight, science, or other).

    Parameters
    ----------
    analysis_df : pandas dataframe
        dataframe of results from `iridium_analysis.logsdir_iridium_analysis`
    write_dir : str
        the path to the write directory for deployment analysis run

    """
    glider = analysis_df.attrs["glider_sn"]
    deploynum = analysis_df.attrs["deployment_number"]
    deploy_csv = os.path.join(write_dir, '{}-{}.csv'.format(glider, deploynum))
    
    # I found I needed to call the end of line character explicitly to work
    # when combining python filewriting operations and pandas file writing.
    with open(deploy_csv, 'w', newline="\n") as fid:
        for key, value in analysis_df.attrs.items():
            fid.write("{}, {}\n".format(key, value))
            
        # Pandas changed the line terminator keyword in version 1.5.0
        if float(pd.__version__[0:3]) >= 1.5:
            analysis_df.to_csv(
                fid, lineterminator="\n", date_format="%Y-%m-%dT%H:%M:%S")
        else:
            analysis_df.to_csv(
                fid, line_terminator="\n", date_format="%Y-%m-%dT%H:%M:%S")


def write_analysis_json(summary, write_dir):
    """Write summary from iridium_analysis for a deployment to a JSON file

    Writes the results of the summarization of an iridium analysis to a JSON
    file for a glider deployment with compiled summarization numbers (e.g. 
    number of calls dropped, percentage of calls dropped in-mission, etc.)

    Parameters
    ----------
    summary : dict
        summary dictionary from `iridium_analysis.logsdir_iridium_analysis`
    write_dir : str
        the path to the write directory for deployment analysis run

    """
    glider = summary["glider_sn"]
    deploynum = summary["deployment_number"]
    deploy_json = os.path.join(write_dir, '{}-{}.json'.format(glider, deploynum))
    with open(deploy_json, 'w', newline="\n") as fid:
        json.dump(summary, fid, indent=2)


#%% Main block 
def ooice_deployment_results(logsdir, glider, deploynum, write_dir):
    """Run an iridium disconnection analysis on an OOI-CE glider deployment's 
    glider terminal logs
    

    Parameters
    ----------
    logsdir : str
        the path to a deployment's logs directory (assuming the directory has
        the logs from a single deployment)
    glider : str
        glider serial number (format specific to keywords used in reference 
        metadata from OOI-CE specific `fin_and_gtypes` dictionary)
    deploynum : str
        deployment number (format specific to keywords used in reference 
        metadata from OOI-CE specific `fin_and_gtypes` dictionary)

    Returns
    -------
    deploy_info : dict
        A summarization dictionary from 
        `iridium_analysis.logsdir_iridium_analysis` with compiled deployment
        specific metadata fin type (digifin or radome), glider type (G2 or G3),
        deployment start and end time, and deployment length.

    """
    ftype = fin_and_gtypes[glider][deploynum]['fin_type']
    gtype = fin_and_gtypes[glider][deploynum]['glider_type']
    
    start, end = google.deployment_dates_pdts(glider, deploynum.replace("D", ""))
    if end is pd.NaT:
        end = dt.utcnow()
        endstr = "still deployed"
    else:
        endstr = end.strftime("%Y-%m-%dT%H:%M:%S")
    len_days = (end - start).total_seconds() / 86400
    
    deploy_info = {
        "glider_sn": glider, 
        "deployment_number": str(int(deploynum.replace('D', ''))),
        "fin_type": ftype, 
        "glider_type": gtype,
        "length_days": len_days,
        "launch_datetime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "end_datetime": endstr
        }
    
    summary_results, analysis_df = logsdir_iridium_analysis(logsdir)
    if not summary_results:
        return
    
    analysis_df.attrs.update(deploy_info)
    write_analysis_csv(analysis_df, write_dir)
    
    deploy_info.update(summary_results)
    write_analysis_json(deploy_info, write_dir)
    
    return deploy_info


def full_run_ooice_log_call_analysis(overwrite=False):
    """Iridium Disconnection Analysis run for ALL OOI-CE glider deployments
    
    keeps track of which gliders have been run with a status list saved as
    completed.json in the write directory.
    
    writes a results csv table for each deployment to the write directory
    """
    run_time_str = dt.now().strftime("%Y-%m-%dT%H%M")
    
    if not os.path.exists(write_dirname):
        os.mkdir(write_dirname)
    
    completed_file = os.path.join(write_dirname, 'completed.json')
    if os.path.exists(completed_file) and not overwrite:
        with open(completed_file) as fid:
            completed = json.load(fid)
    else:
        completed = {
            "last_run_time": run_time_str,
            "deployments": []}

    
    # dictionary to keep all deployment results into and saved into a json file
    # for persistence between runs
    json_results_path = os.path.join(
        proj_root, "iridium_call_analysis_summary.json")
    if os.path.exists(json_results_path) and not overwrite:
        with open(json_results_path) as fid:
            all_deployment_results = json.load(fid)
    else:
        all_deployment_results = {
            "last_run_time": run_time_str
            }

    
    # looks at the OOI-CE dataroot directory and provides a list of all available
    # deployments with a logs directory (glider terminal logs from SFMC or 
    # dockserver)
    deployment_dirs = glob.glob(os.path.join(dataroot, "ce05moas-g*/D000*/logs"))
    
    for logsdir in deployment_dirs:
        # the body of this for loop is unique to OOI naming conventions, but
        # the concept should be the same for any glider group. Edit as needed.
        rematch = fileregex.search(logsdir)
        if rematch:
            glider, deploynum = rematch.groups()
            if glider.startswith('0'):  # OOI convention for G3 gliders
                glider = glider[1:]
            deploykey = glider + "-" + deploynum.replace("D", "")
            if deploykey in completed["deployments"]:
                logger.info(f"skipping {deploykey}")
                continue
            logger.info(f"Running {deploykey}")  # just for announcing progress
            # primary anaylysis done via this call to `ooice_deployment_results`
            results = ooice_deployment_results(logsdir, glider, deploynum, write_dirname)
            
            # only considered complete if not still deployed.
            if results["end_datetime"] != "still deployed":
                completed["deployments"].append(deploykey)
            all_deployment_results[deploykey] = results  # store compiled results
            
            # write each run to the JSON files so results are saved if there is
            # an error and the execution breaks. This could be more efficient
            # but works for now.
            with open(completed_file, 'w') as fid:
                json.dump(completed, fid, indent=2)
            
            with open(json_results_path, 'w', newline="\n") as fid:
                json.dump(all_deployment_results, fid, indent=2)
            
        else:
            logger.error(f"cannot determine glider and deployment from {logsdir}")
    
    make_histograms(all_deployment_results)
    
    

# %% plot histograms

def make_histograms(results):
    run_time_datestr = dt.now().strftime('%Y-%m-%d')
    
    g2_dig_total = []
    g2_rad_total = []
    g3_rad_total = []
    
    g2_dig_inmis = []
    g2_rad_inmis = []
    g3_rad_inmis = []
    
    #in-mission
    for deployment in results:
        if deployment == 'last_run_time':
            continue
        gtype = results[deployment]['glider_type']
        ftype = results[deployment]['fin_type']
        total_dropped_calls = results[deployment]['dropped calls (%)']
        inmis_dropped_calls = results[deployment]['mission drops (%)']
        
        if gtype == 'G3':
            g3_rad_total.append(total_dropped_calls)
            g3_rad_inmis.append(inmis_dropped_calls)
        elif gtype == 'G2' and ftype == 'digifin':
            g2_dig_total.append(total_dropped_calls)
            g2_dig_inmis.append(inmis_dropped_calls)
        elif gtype == 'G2' and ftype == 'radome':
            g2_rad_total.append(total_dropped_calls)
            g2_rad_inmis.append(inmis_dropped_calls)

    bins = list(range(0,105,5))    
    
    # Total dropped calls histogram
    fig, ax = plt.subplots()
    ax.hist(g2_dig_total, bins, label="G2 with digifin");
    ax.hist(g2_rad_total, bins, label="G2 with radome");
    ax.hist(g3_rad_total, bins, label="G3 with radome");
    ax.legend()
    ax.set_title('Total dropped calls percent')
    ax.set_ylabel("Counts")
    ax.set_xlabel("Percent %")
    fig.suptitle('OOI-CE Dropped call analysis, {}'.format(run_time_datestr))
    figname = os.path.join(
        proj_root, 'total_dropped_calls_hist_{}.png'.format(run_time_datestr))
    fig.savefig(figname)
    
    # in-mission dropped calls histogram
    fig, ax = plt.subplots()
    ax.hist(g2_dig_inmis, bins, label="G2 with digifin");
    ax.hist(g2_rad_inmis, bins, label="G2 with radome");
    ax.hist(g3_rad_inmis, bins, label="G3 with radome");
    ax.legend()
    ax.set_title('In-mission dropped calls percent')
    ax.set_ylabel("Counts")
    ax.set_xlabel("Percent %")
    
    fig.suptitle('OOI-CE Dropped call analysis, {}'.format(run_time_datestr))

    figname = os.path.join(
        proj_root, 'in-mission_dropped_calls_hist_{}.png'.format(run_time_datestr))
    fig.savefig(figname)
    plt.close('all')