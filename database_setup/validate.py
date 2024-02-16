import pandas as pd
import numpy as np
import glob
import os
from pymongo import MongoClient

'''
The Validator class validates the steadiness of magnetron sputter experiments based on their CSV outputs.
Steadiness is judged by a set of parameters settling below a given standard deviation before a given time limit.
Steady and completely unsteady experiments are evaluated to "True" by the validate function and stored in a MongoDB database. 
Experiments which settle after the given time limit are evaluated to "False" by the validate function and are not stored in 
the database. The False signal indicates that the experiment should be rerun.

TODO: 
    - Add metadata (where is it coming from)?
    - Add all other fields that Jonathan mentioned when we have access to them
    - Test that default CSV path works on the lab computer
    - Test that everything else works on the lab computer 
'''

class Validator:

    # TODO: check that default filepath works on lab computer
    def __init__(self, database, collection, path_CSV='Log/RecordingData'): 
        '''
        Initializer for the DatabaseLoader class

        Parameters
        ----------
        database: which mongodb database to use 
        collection: which collection of given database to enter experiment data in
        path_CSV: file path for experiment CSV files (defaults to Log/RecordingData)

        Class variables
        ---------------
        sigma_V: 
        sigma_P: 
        t:
        t_d:
        steady_params: 
        '''

        client = MongoClient()
        self.db = client[database]
        self.collection = self.db[collection]
        self.path_CSV = path_CSV

        self.sigma_V = 1
        self.sigma_P = 0.1
        self.t = 0.5
        self.t_d = 0.3
        self.thresholds = {
            'PC Capman Pressure' : self.sigma_P,
            'Power Supply 1 Voltage' : self.sigma_V, 
            'Power Supply 3 Voltage' : self.sigma_V,
            'Power Supply 5 DC Bias' : self.sigma_V
        }
            
        




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
        '''
        The validate function is the core function of the Validator class. The function (1) retrieves the latest 
        sputtering experiment CSV file from a given filepath, (2) calculates if the experiment has settled
        according to given (time and std) thresholds, (3) stores settled and fully unsettled experiments in 
        the database, and returns a True bool, since these have clear results; alternatively, does not store
        the experiment if the experiment settles too late within given thresholds and returns False, indicating
        that the experiment controller should retry the experiment.
        '''

        # Get date of latest experiment and its CSV as dataframe
        date, df = self.getLastExperiment()

        # Create date dictionary
        date_dict = {'Date' : date}

        # Get size of dataframe (n rows)
        rows = len(df.axes[0])

        # Find steady state and drag threshold as index
        n_t = int(self.t*rows)
        n_td = int(self.t_d*rows)

        for j in range(0, n_t + n_td):

            if all(df[p].tail(rows-j).std() <= self.thresholds[p] for p in self.thresholds.keys()):
                if (j <= n_t):
                    # Get settling time
                    settle_time_dict = {'Settling time' : df["Time Stamp"].iloc[j]}

                    # Create settled status entry (True)
                    status_dict = {"Settled" : True}
                    
                    # Get mean and stds for all columns
                    calc_dict = self.calculate_statistics(df, rows, index=j)

                    # Merge all dictionaries into a doc
                    doc = {**date_dict, **status_dict, **settle_time_dict, **df.to_dict('list'), **calc_dict}
                    
                    # Insert doc into database collection
                    self.collection.insert_one(doc)
                    
                    return True
                else:
                    # Return False if experiment settles between time t and t_d, indicating that the experiment should be rerun
                    return False
        
        
        '''Return True for fully unstable experiments, indicating that we have stored the result to database'''

        # Created settled status entry (False)
        status_dict = {"Settled" : False}

        # Get mean and stds for all columns
        calc_dict = self.calculate_statistics(df, rows)

        # Merge all dictionaries into a doc
        doc = {**date_dict, **status_dict, **df.to_dict('list'), **calc_dict}

        # Insert doc into database collection
        self.collection.insert_one(doc)

        return True



    def calculate_statistics(self, df, rows, index=1):
        '''
        Calculates mean and std for all fields (except time) in the dataframe

        Parameters
        ----------
        df: processed dataframe with experiment data  
        rows: amount of rows in the dataframe (already calculated in validate function)
        index: in settled experiments, index indicates where measurements become stable, so
        we only calculate statistics for where the experiment is steady

        Returns
        -------
        calc_dict: a dictionary of mean and std for all fields (except time) in the dataframe

        '''

        # Prepare calculation dictionary
        calc_keys = []
        calc_vals = []
        
        # Calculate settled mean and std for all columns
        for k in df.columns[1:]:
            mean_key = k + ' Mean'
            std_key = k + ' STD'
            mean = df[k].tail(rows-index).mean()
            std = df[k].tail(rows-index).std()
            
            # Round off values that are not PC Source
            if 'PC Source' not in k:
                mean = np.round(mean, 3)
                std = np.round(std, 3)
                
            calc_keys.extend([mean_key, std_key])
            calc_vals.extend([mean, std])
        
        # Create calculation dictionary
        calc_dict = dict(zip(calc_keys, calc_vals))

        return calc_dict
    

    
    def getLastExperiment(self):
        '''
        Retrieves the latest modified file from the CSV filepath and processes it.    

        Returns
        -------
        date: String of date of the experiment
        df: A dataframe of the experiment CSV (Experiment parameters + time series measurements)
        '''

        # Get CSVs from filepath
        files = glob.glob(self.path_CSV + "*.CSV")

        # Get latest modified file
        latest_file = max(files, key=os.path.getctime)

        # Read csv
        df = pd.read_csv(latest_file, skiprows=[0,1])

        # Retrieve date and processed df
        return self.process_df(df)
        



db_loader = Validator("db-py-test", "experiments", path_CSV='data/')
db_loader.validate()