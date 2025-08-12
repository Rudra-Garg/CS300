import pandas as pd

# Make sure this path is correct inside your container
DATA_FILE = 'data_producer/eeg_eye_state.csv' 

# Load the dataframe into a variable first
df = pd.read_csv(DATA_FILE)

# Print the available columns to the console
print("Available columns in the CSV file are:")
print(df.columns)

# Once you see the correct name, use it below. 
# For example, if the real name is 'EEG AF3', you would use:
# eeg_dataset = df['EEG AF3'].values