import pandas as pd
from scipy.io import arff
import os

# --- Configuration ---
# The name of the ARFF file you downloaded
arff_file_name = 'eeg.arff'
# The desired name for the output CSV file
csv_file_name = 'eeg_eye_state.csv'
# -------------------

# Check if the input file exists
if not os.path.exists(arff_file_name):
    print(f"Error: Input file '{arff_file_name}' not found.")
    print("Please make sure the .arff file is in the same directory as this script.")
else:
        # Load the ARFF file
        print(f"Loading '{arff_file_name}'...")
        data, meta = arff.loadarff(arff_file_name)
        
        # Convert the data to a pandas DataFrame
        df = pd.DataFrame(data)
        
        
        # Save the DataFrame to a CSV file
        df.to_csv(csv_file_name, index=False)
        
        print(f"\nSuccess! ✨")
        print(f"File converted and saved as '{csv_file_name}'.")