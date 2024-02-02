import pandas as pd
import numpy as np
import glob
import os
from pymongo import MongoClient

'''
The Validator class validates the steadiness of magnetron sputter experiments based on their CSV outputs.
Steadiness is judged by a set of parameters settling below a given standard deviation before a given time limit.
Steady and completely unsteady experiments are evaluated to "True" by the evaluate function and stored in a MongoDB database. 
Experiments which settle after the given time limit are evaluated to "False" by the validate function and are not stored in 
the database. The False signal indicates that the experiment should be rerun.
'''

class Validator:

    # TODO: check that default filepath works in lab computer
    def __init__(self, database, collection, path_CSV='Log/RecordingData'): 
        '''
        Initializer for the DatabaseLoader class

        Parameters
        ----------
        database: which mongodb database to use 
        collection: which collection of given database to enter experiment data in
        path_CSV: file path for experiment CSV files (defaults to Log/RecordingData)

        '''

        # Connect to database server
        client = MongoClient()

        # Get/create database
        self.db = client[database]

        # Get/create collection
        self.collection = self.db[collection]

        # Store CSV filepath
        self.path_CSV = path_CSV

        # Standard deviation threshold for voltages
        self.sigma_V = 1

        # Standard deviation threshold for pressure
        self.sigma_P = 0.1

        # Time threshold
        self.t = 0.5

        # Time drag threshold
        self.t_d = 0.3

        # Parameters which define the steady state
        self.steady_params = [
            'PC Capman Pressure', 
            'Power Supply 1 Voltage', 
            'Power Supply 3 Voltage', 
            'Power Supply 5 DC Bias'
        ]




    def process_df(self, df):
        '''
        Converts time stamp column from String datetime to seconds starting from 0 
        and rounds values of selected columns (all but PC Source columns) to 3 decimals
        
        Parameters
        ----------
        df: pandas df of experiment CSV
        
        
        Returns
        ---------
        date: string of experiment date (mm/dd/yy)
        df: pandas df with converted time column and 3 decimal values for all columns
        '''
        
        # Convert to datetime
        df['Time Stamp'] = pd.to_datetime(df['Time Stamp'])
        
        # Save date
        date = df['Time Stamp'].iloc[0].date().strftime('%m/%d/%Y')

        # Convert datetime to seconds starting from zero
        df['Time Stamp'] = (df['Time Stamp'] - df['Time Stamp'].iloc[0]).dt.total_seconds()
        
        # Round selected columns to three decimals
        rounded_columns = []

        for i in df.columns.values:
            if 'PC Source' not in i:
                rounded_columns.append(i)

        df[rounded_columns] = df[rounded_columns].round(3)

        
        return date, df
    


    def validate(self):

        # Get date of latest experiment and its CSV as dataframe
        date, df = self.getLastExperiment()

        # Create date dictionary
        date_dict = {'Date' : date}

        # Get size
        rows = len(df.axes[0])
        cols = len(df.axes[1])

        # Find steady state threshold as index
        n_threshold = int(self.t * rows)
        
    
    def getLastExperiment(self):
        '''
        Retrieves the latest modified file from the CSV filepath and processes it.    

        Returns
        -------
        date: String of date of the experiment
        df: A dataframe of the experiment CSV (Experiment parameters + time series measurements)
        '''

        # Get CSVs from filepath
        files = glob.glob(self.path_CSV + "*.CSV") # * means all if need specific format then *.csv

        # Get latest modified file
        latest_file = max(files, key=os.path.getctime)

            # Read csv
        df = pd.read_csv(latest_file, skiprows=[0,1])

        # Retrieve date and processed df
        return self.process_df(df)
        



db_loader = Validator("db-py-test", "experiments", path_CSV='data/')
db_loader.validate()