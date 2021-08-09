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
from tda import auth, client

from . import trade, analyze

# Create typer app
app = typer.Typer()

@app.command()
class AlgoTrade:
    """ The controller for the trade strategies framework.
    
    Calling a command from here will pass through to the necessary modules
    to get and store quotes, analyze, and excute (and/or simulate) trades.
    
    'persistent' is assumed in this state (whereas it's a parameter in Trade)
    
    """
    
    @coftc_logging.exceptions()
    def __init__(
            self,
            tda_profile: str = typer.Argument(
                ...,
                help="The TDA credentials profile to be used",
                ),
            db_profile: str = typer.Argument(
                ...,
                help="The database credentials profile to be used",
                ),
            redirect_uri: str = typer.Option(
                'https://localhost', '--redirect', '-r',
                help="The redirect URI to be used with TD Ameritrade authentication",
                ),
            period_minutes: int = typer.Option(
                15, '--period',
                help="The time period (in minutes) with which to store quotes (and calculations)",
                ),
            analysis_types: Optional[str] = typer.Option(
                None, '--analysis',
                help="List of analysis types to use when determining buy/sell signals"),
            interactive: bool = typer.Option(
                False, '--interactive', '-i', show_default=False,
                help="Run the script interactively (rather than automated)"),
            dev: bool = typer.Option(
                False, '--dev', show_default=False,
                help="Specify that the package is in 'development mode'"),
            ):

        # If this is run in an interpreter, set the optional Options to their
        # defaults so the user doesn't have to
        self.period_minutes = period_minutes.default if isinstance(period_minutes, typer.models.OptionInfo) else period_minutes    
        self.analysis_types = analysis_types.default if isinstance(analysis_types, typer.models.OptionInfo) else analysis_types    
        self.interactive = interactive.default if isinstance(interactive, typer.models.OptionInfo) else interactive    
        self.dev = dev.default if isinstance(dev, typer.models.OptionInfo) else dev
        
        # Set paths based on 'dev mode'
        if not self.dev:
            self.package_path = importlib.resources.files('trade_framework')
        else:
            self.package_path = os.getcwd()

        # Set credential manager
        self.cred = coftc_cred_man.Cred(tda_profile)
        self.db_profile = db_profile
        
        self.connect(redirect_uri)
        
        if self.interactive:
            self.run()
        
    @coftc_logging.exceptions()
    def connect(self, redirect_uri):
        
        # Connect to TD Ameritrade
        token_path = os.path.expanduser('~/.tdatoken.pickle')

        try:
            self._client = auth.client_from_token_file(token_path, self.cred.password())
        except FileNotFoundError:
            from selenium import webdriver
            # TODO: Test this try-catch block; may or may not work when using on a non-GUI OS
            try:
                with webdriver.Chrome(
                        executable_path=os.path.join(
                            self.package_path,
                            'resources',
                            'chromedriver.exe',
                            )
                        ) as driver:
                    self._client = auth.client_from_login_flow(
                        driver,
                        self.cred.password(),
                        redirect_uri,
                        token_path
                        )
            except:
                self._client = auth.client_from_manual_flow(
                    self.cred.password(),
                    redirect_uri,
                    token_path,
                    asyncio=False,
                    token_write_func=None
                    )

        # Connect to `algo_trading` database
        self._conn = coftc_db_utils.Conn(self.db_profile)
        
    @coftc_logging.exceptions()
    def run(self):
        """
        Autorun the sections of the trade strategies framework

        Returns
        -------
        None.

        """
        
        # TODO: Set up stock screener to automatically feed Trade. For now,
        # use a manual TOML file to feed tickers. Like the eventual screener
        # feed, the script should check for a new file periodically, and be
        # able to filter out invalid tickers (and post to exceptions log).
        
        # TODO: Set up market open/close reading (something like scraping
        # https://www.tradinghours.com/open). For now, use a weekday 0900-1630
        # (New York time) 
        

def run_cli():
    app()



