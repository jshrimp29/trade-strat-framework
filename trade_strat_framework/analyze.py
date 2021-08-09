#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path
import os
import pendulum
import importlib
import requests
import math
import time
from typing import Optional
import typer

import coftc_cred_man
import coftc_db_utils
import coftc_logging

# Create typer app
app = typer.Typer()

@app.command()
class Analyze:
    
    @coftc_logging.exceptions()
    def __init__(
            self,
            tda_client: str = typer.Argument(
                ...,
                help="The TDA client connection to be used (tda.client.....Client)",
                ),
            db_conn: str = typer.Argument(
                ...,
                help="The database connection to be used (coftc_db_utils.Conn)",
                ),
            analysis_types: Optional[str] = typer.Option(
                None, '--analysis',
                help="List of analysis types to use when determining buy/sell signals"),
            dev: bool = typer.Option(
                False, '--dev', show_default=False,
                help="Specify that the package is in 'development mode'"),
            ):
        
        # TODO: add this to tests:
        # Note that any non-analysis functions must be preceded by at least
        # one underscore
        
        if not dev:
            self.package_path = importlib.resources.files('trade_strat_framework')
        else:
            self.package_path = os.getcwd()

        # Set connects (matches the attribute names in __init__)
        self._conn = db_conn
        self._client = tda_client

        self._parse_analysis_types(analysis_types)
        
    
    @coftc_logging.exceptions()
    def _parse_analysis_types(self, analysis_types):
        """
        Parse the analysis types input and ensure the proper fields are in the
        database.

        Returns
        -------
        None.

        """
        
        # Split the analysis types, convert to lowercase, and ensure the
        # corresponding function exist in this class
        self.analysis_list = analysis_types.lower().replace(',','').split(' ')
        
        checkList = []
        for itm in self.analysis_list:
            checkList.append(hasattr(self,itm))
        if not all(checkList):
            if len(checkList)==1:
                pluralStr = "analysis hasn't"
            else:
                pluralStr = "analyses haven't"
                
            raise NameError(
                "The following input {plur} yet been set up: '{lst}'".format(
                    plur=pluralStr,
                    lst="', '".join(self.analysis_list[idx] for idx,x in enumerate(checkList) if not x)),
                "The available analyses are '{}'".format(
                    "', '".join(
                        x for x in dir(self) if not x.startswith('_')
                        )
                    ),
                )

        # Ensure the proper fields are in the `analysis` table
        for itm in self.analysis_list:
            
        

    @coftc_logging.exceptions()
    def json_quotes(self, ticker):
        
        r = self.client.get_quotes(ticker)
        assert r.status_code == requests.codes.okay, r.raise_for_status()
        
        return(r.json())
    
    @coftc_logging.exceptions()
    def store_quotes(self, ticker):
        
        # This is tightly coupled with the database - hardcode the conversions
        # as (API name, Database field name)
        dbFieldTransmute = [
            ('symbol', 'ticker'),
            ('lastPrice', 'price'),
            ('askPrice', 'ask'),
            ('bidPrice', 'bid'),
            ('totalVolume', 'volume'),
            ('delayed', 'delayed'),
            ('quoteTimeInLong', 'datetime_newyork'),
            ]
        
        # Set a loop, but break it immediately if not persistent
        firstLoop = True
        while True:
            loopTimeStart = pendulum.now('America/New_York')
            
            quoteDict = self.json_quotes(ticker)
            readDt = pendulum.now('America/New_York')
            
            # If first time through, use the returned dict keys as the master
            # ticker list (these are sanitized via tda-api) to store datetimes
            # and nextRun to store the next runtimes (for persistent)
            if firstLoop:
                # tickerList has the same keys as quoteDict, but each key
                # contains the 'last read' and 'quote' datetimes (in New York
                # time zone)
                tickerList = {
                    key: {
                        'read_dt_ny': None,
                        'quote_dt_ny': None,
                        'prev_quote_dt': None,
                        'delayed': None,
                        } for key in quoteDict.keys()
                    }
                
                nextRun = {key: None for key in quoteDict.keys()}
                
            # Iterate through each currently-run symbol and store the matching
            # values in `algo_trading`.`quotes`. Datetimes are stored in UTC.
            insertList = []
            for key in quoteDict.keys():
                
                # Update tickerList with new data
                tickerList[key]['read_dt_ny'] = readDt
                tickerList[key]['quote_dt_ny'] = pendulum.from_timestamp(
                    int(
                        str(
                            quoteDict[key]['quoteTimeInLong']
                            )[:-3]
                        )
                    ).in_tz('America/New_York')
                tickerList[key]['delayed'] = quoteDict[key]['delayed']
                
                # If this isn't the first time through, compare the quote with
                # (previous + expected period). Ensure the proper time period is maintained
                if not firstLoop:               
                    tickerList[key]['time_correction_period'] = tickerList[key]['quote_dt_ny'] - tickerList[key]['prev_quote_dt'].add(minutes=self.period_minutes)
                    
                    # raise Exception('breakpoint')
                    
                    # Correct the actual period based on history with the 
                    # calculated period
                    time_correction_sec = tickerList[key]['time_correction_period'].in_seconds()

                    
                # If firstLoop, cannot have an error. Initialize
                # tickerList[key]['time_correction_period']
                else:
                    tickerList[key]['time_correction_period'] = tickerList[key]['quote_dt_ny'] - tickerList[key]['quote_dt_ny']
                    time_correction_sec = 0
                  
                # Rewrite (or initialize) 'prev_quote_dt' for next loop
                tickerList[key]['prev_quote_dt'] = tickerList[key]['quote_dt_ny']
                
                # Add to list for database insert
                # Include time_correction_sec calculation, and use firstLoop
                # as for the value in the `initial` field (the `initial` field
                # will be used for candle calculations - if `initial`==True,
                # calcs will not be made)
                insertList.append(
                    [
                        pendulum.from_timestamp(
                            int(
                                str(
                                    quoteDict[key][iterKey]
                                    )[:-3]
                                )
                            ).in_tz('America/New_York') \
                            if iterKey == 'quoteTimeInLong' else \
                            quoteDict[key][iterKey] for iterKey in [
                                x[0] for x in dbFieldTransmute
                                ]
                            ] + [time_correction_sec, firstLoop]
                        )
                
            # Insert all into `quotes` table
            self.conn.insert(table_name='quotes', fields=[x[1] for x in dbFieldTransmute]+['time_correction_sec', 'initial'], values=insertList, on_duplicate='ignore')
            
            print('Wrote {} at {} Mountain'.format(", ".join([quoteDict[key]['symbol'] for key in quoteDict.keys()]), pendulum.now().format('HH:mm:SS')))

            if not self.persistent:
                break
            
            else:   # if persistent
            
                # Finalizing
                if firstLoop:
                    loopTimeEnd = pendulum.now('America/New_York')
                    loopSecPerSymbol = (loopTimeEnd-loopTimeStart).in_seconds()/len(ticker)
                    
                    firstLoop = False
            
                # Determine when next to run the loop for each ticker
                for key in quoteDict.keys():
                    
                    # Use the difference between the read
                    # time and the quote time to calculate the next run time
                    timeDiff = tickerList[key]['read_dt_ny'] - tickerList[key]['quote_dt_ny']
                                
                    # Add the specified period to the last quote time plus the
                    # difference in quote and read (to get 'read_dt_ny'
                    # without milliseconds)
                    # Then add the 'time_correction_period' offset to correct
                    # for any mismatch between expected and actual 'quote' time
                    
                    # The 'time_correction_period' seconds value is signed,
                    # which works well with the subtract() function
                    nextRun[key] = tickerList[key]['quote_dt_ny'].add(
                        seconds=timeDiff.in_seconds()
                        ).add(
                            minutes=self.period_minutes
                            ).subtract(
                                seconds=math.floor(tickerList[key]['time_correction_period'].in_seconds()/2)
                                )                                
                    
                print(nextRun)
                
                # Set the necessary next ticker and pause until next run
                minNextRun = min([nextRun[key] for key in nextRun.keys()])
                # Iterate twice to gain a better estimate for the amount of
                # time the loop will take
                for _ in range(2):
                    newLoopSec = loopSecPerSymbol*len(ticker)
                    ticker = [
                        key for key in nextRun.keys() if nextRun[key] >= minNextRun.subtract(seconds=newLoopSec) and nextRun[key] <= minNextRun.add(seconds=newLoopSec)
                        ]
                
                print('Next ticker is {}'.format(', '.join(ticker)))
                
                pauseSeconds = max(
                    [
                        0,
                        (minNextRun-pendulum.now('America/New_York')).in_seconds(),
                        ]
                    )   # ensure negative numbers are not allowed
                    
                if pauseSeconds == 0:
                    coftc_logging.notifications('store_quotes loop is not pausing - possibly overloaded by the number of quotes')
                    
                print('Pausing for {:.2f} min\n'.format(pauseSeconds/60))
                
                if self.dev:     # in dev mode, pause in 10-second increments to
                                 # allow KeyboardInterrupt
                    pauseInt = math.floor(pauseSeconds/10)
                    for idx in range(pauseInt):
                        time.sleep(10)
                    time.sleep(pauseSeconds - pauseInt*10)  # pause the remaining time, if applicable
                    
                else:
                    time.sleep(pauseSeconds)

def run_cli():
    app()

