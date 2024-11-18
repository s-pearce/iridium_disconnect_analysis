# Iridium Disconnect Analysis
Python module to analyze Slocum Glider Iridium call logs

This module is intended to quantify Slocum Glider Iridium call disconnections 
by analyzing the glider terminal logs from a Dockserver or SFMC server 
(e.g. "/var/opt/gmc/gliders/<glider name>/logs/") to see which calls are 
disconnected intentionally by either a user or by glider functions or are 
unintentional dropped connections.

The primary function to use is `logsdir_iridium_analysis` from the 
`iridium_disconnect_analysis` module. Input is a directory where the glider 
terminal logs can be found for a single deployment.  The function analyzes each
log file within the directory and using phrases from the `log_regexes` module
determines whether the Iridium call was disconnected intentionally or not.
Any calls not disconnected intentionally are considered dropped calls.  After
all files are analyzed, a pandas dataframe with results from each log file is
returned along with a dictionary that summarizes the results of all the logs
within the directory.  Other information about the log file is cataloged and
kept to investigate different circumstances of the disconnection rates such as
whether the glider was in-mission for the entire call, or if the call was
dropped during data transfer.  

Because every group stores metadata about glider deployments differently, it is
up to the user of this function to catalog any additional information to
co-analyze the call disconnection results (e.g. glider model, fin type,
firmware version, deployment start and stop, etc.). The module 
`ooice_iridium_analysis.py` is what I run for our OOICE group (Ocean 
Observatories Initiative Coastal Endurance Array operated at Oregon State 
University), I have included it as an example file to which any group may use 
as a guiding example to compile the iridium analysis results across multiple 
deployments and include metadata for the final analysis. My end result is that 
I made histograms of in-mission dropped call rates for G2 gliders with digifin 
model tails, G2 gliders with Radome model tails, and G3 gliders (that also 
feature the same Radome model tail). 

If you end up using this code to see the difference between G2 gliders and G3
gliders, please let me know the general results, I would be interested to hear
them.

Stuart