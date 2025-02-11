# Iridium Disconnect Analysis
## example_output directory

This example_output directory holds the example output from a run of the 
`ooice_iridium_analysis.py` module for 1 G3 glider deployment (glider ce_1012 
deployment 3) and demonstrates how additional metadata 
was included to aid in the analysis. The extra fields included for the OOICE 
analysis are, glider serial number, deployment number, launch datetime, 
recovery datetime, fin type used, glider model/type, and deployment length in 
days.

The output are:
 1. 1012-3.csv, created from the pandas dataframe.to_csv method on the results 
    dataframe created from `logsdir_iridium_analysis`. It is a boolean table of 
    results for each glider terminal log file.  See the docstring for 
    `logsdir_iridium_analysis` or `log_disconnect_info` for more details.
 2. 1012-3.json, a JSON file created from the summarization results dictionary 
    returned by `logsdir_iridium_analysis`.  This has summarizations such as 
    number of dropped calls, number of dropped calls while in-mission, number of
    calls dropped during a data transfer, etc. as well as percentages of the
    numbers. See the code for `logcall_summary` for more details.
 3. in-mission_dropped_calls_hist_2024-11-06.png, the histogram output 
    from `ooice_iridium_analysis.py` over all 176 (at the time of run 
    2024-11-06) OOICE Slocum glider deployments that shows the difference 
    between G2 gliders with Digifins tails, G2 gliders with Radome fin tails, 
    and G3 gliders (which have the same Radome fin tails).
