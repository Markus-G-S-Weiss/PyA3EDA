#!/home/dal063121/.conda/envs/extrplt/bin/python3
#%%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# Get current working directory (where script is executed from)
work_dir = os.getcwd()

# Load data from current directory
df = pd.read_csv(os.path.join(work_dir, 'extracted_data.csv'))

species_map = {
    'reactants': 'Reactants',
    'ts': 'Transition State',
    'product': 'Product'
}
df['Species'] = df['Folder_Level_1'].map(species_map)
df = df[df['Species'].notna()].copy()

# Constants
hartree_to_kcalmol = 627.5096080305927 # Ha to kcal/mol
R = 8.31446261815324e-3 * 0.2390057361376673 # kcal/mol.K
ln_24_5 = np.log(24.5) 

# Verify temperature column exists
if 'Temperature (K)' not in df.columns:
    raise ValueError("Temperature column is missing")

# Energy calculations using row-specific temperatures
df['E (kcal/mol)'] = df['Final Energy Fallback (Ha)'] * hartree_to_kcalmol
df['H (kcal/mol)'] = df['E (kcal/mol)'] + df['QRRHO-Total Enthalpy (kcal/mol)']
df['QRRHO-Total Entropy (kcal/mol·K)'] = df['QRRHO-Total Entropy (cal/mol.K)'] * 1e-3
df['G (kcal/mol)'] = df.apply(
    lambda row: row['H (kcal/mol)'] - row['Temperature (K)'] * row['QRRHO-Total Entropy (kcal/mol·K)'],
    axis=1
)

#%%
# Define paths and reference energies
paths = ['no_cat', 'frz', 'pol', 'full']
path_map = {
    'no_cat': 'no_cat',
    'frz': 'frz_cat',
    'pol': 'pol_cat',
    'full': 'full_cat'
}

# Get reference energies (no_cat reactants: butadiene + prop2enal + lip)
butadiene = df[
    (df['Species'] == 'Reactants') &
    (df['Folder_Level_2'] == 'butadiene') &
    (df['Folder_Level_3'] == 'strans_butadiene')
].iloc[0]

prop2enal_nocat = df[
    (df['Species'] == 'Reactants') &
    (df['Folder_Level_2'] == 'prop2enal') &
    (df['Folder_Level_3'] == 'no_cat')
].iloc[0]

lip_reactant = df[
    (df['Species'] == 'Reactants') &
    (df['Folder_Level_2'] == 'lip')
].iloc[0]

# Sum all three components for reference energies
ref_energy = butadiene['E (kcal/mol)'] + prop2enal_nocat['E (kcal/mol)'] + lip_reactant['E (kcal/mol)']
ref_G = butadiene['G (kcal/mol)'] + prop2enal_nocat['G (kcal/mol)'] + lip_reactant['G (kcal/mol)']

#%%
# Plot Final Energy Profile
plt.figure(figsize=(12, 6))

# Species order for x-axis
species_order = ['Reactants\nno cat', 'Reactants\nwith cat', 'Transition\nState', 'Product\nwith cat', 'Product\nno cat']
energies = {path: [] for path in paths}

# Extract energies for each path
for path in paths:
    path_key = path_map[path]
    
    # Reactants (no_cat is reference)
    if path == 'no_cat':
        energies[path].append(0)  # Reference point
    else:
        cat_reactants = df[
            (df['Species'] == 'Reactants') &
            (df['Folder_Level_2'] == 'prop2enal') &
            (df['Folder_Level_3'] == path_key)
        ]['E (kcal/mol)'].values[0] + butadiene['E (kcal/mol)']
        energies[path].append(cat_reactants - ref_energy)
    
    # Transition State
    ts_energy = df[
        (df['Species'] == 'Transition State') &
        (df['Folder_Level_2'] == f'{path_key}_ts')
    ]['E (kcal/mol)'].values[0]
    energies[path].append(ts_energy - ref_energy)
    
    # Product
    product_energy = df[
        (df['Species'] == 'Product') &
        (df['Folder_Level_2'] == f'{path_key}_product')
    ]['E (kcal/mol)'].values[0]
    energies[path].append(product_energy - ref_energy)

# Plot each path
for path in paths:
    if path == 'no_cat':
        plt.plot([0, 2, 4], [energies[path][0], energies[path][1], energies[path][2]], 
                 marker='o', label=path)
    else:
        plt.plot([1, 2, 3], [energies[path][0], energies[path][1], energies[path][2]], 
                 marker='o', label=path)

# plt.xticks(range(5), species_order)
plt.ylabel('Relative Energy (kcal/mol)')
plt.title('Reaction Energy Profile')
plt.legend(title='Paths')
plt.grid(True)
plt.tight_layout()
# plt.savefig(os.path.join(work_dir, 'energy_profile.png'))
df.head()
#%%
# Plot Free Energy Profile (G)
plt.figure(figsize=(12, 6))

g_energies = {path: [] for path in paths}

# Extract G energies for each path
for path in paths:
    path_key = path_map[path]
    
    # Reactants (no_cat is reference)
    if path == 'no_cat':
        g_energies[path].append(0)  # Reference point
    else:
        cat_reactants = df[
            (df['Species'] == 'Reactants') &
            (df['Folder_Level_2'] == 'prop2enal') &
            (df['Folder_Level_3'] == path_key)
        ]['G (kcal/mol)'].values[0] + butadiene['G (kcal/mol)']
        g_energies[path].append(cat_reactants - ref_G)
    
    # Transition State
    ts_g = df[
        (df['Species'] == 'Transition State') &
        (df['Folder_Level_2'] == f'{path_key}_ts')
    ]['G (kcal/mol)'].values[0]
    g_energies[path].append(ts_g - ref_G)
    
    # Product
    product_g = df[
        (df['Species'] == 'Product') &
        (df['Folder_Level_2'] == f'{path_key}_product')
    ]['G (kcal/mol)'].values[0]
    g_energies[path].append(product_g - ref_G)

# Plot each path
for path in paths:
    if path == 'no_cat':
        plt.plot([0, 2, 4], [g_energies[path][0], g_energies[path][1], g_energies[path][2]], 
                 marker='o', label=path)
    else:
        plt.plot([1, 2, 3], [g_energies[path][0], g_energies[path][1], g_energies[path][2]], 
                 marker='o', label=path)

# plt.xticks(range(5), species_order)
plt.ylabel('Relative Free Energy (kcal/mol)')
plt.title('Reaction Free Energy Profile')
plt.legend(title='Paths')
plt.grid(True)
plt.tight_layout()
# plt.savefig(os.path.join(work_dir, 'free_energy_profile.png'))
