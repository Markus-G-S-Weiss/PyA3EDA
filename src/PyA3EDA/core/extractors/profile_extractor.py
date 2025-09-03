"""
Energy Profile Extractor for Quantum Chemistry Calculations.

Processes quantum chemistry calculation data to construct reaction energy profiles
for both catalyzed and uncatalyzed pathways. Uses metadata-driven approach to 
identify reaction components and build comprehensive energy profiles.

Example:
     extractor = ProfileExtractor(calculation_data)
     profiles = extractor.extract_profiles()
     print(profiles['no_cat'])  # Uncatalyzed pathway
"""
from typing import Dict, List, Any, Optional


class ProfileExtractor:
    """
    Extracts energy profiles from quantum chemistry calculation data.
    
    This class processes raw quantum chemistry calculation results to generate
    comprehensive energy profiles for chemical reactions. It handles both 
    catalyzed and uncatalyzed reaction pathways, supporting various calculation
    types including EDA (Energy Decomposition Analysis) methods.
    
    Attributes:
        raw_data (List[Dict[str, Any]]): Raw calculation data containing energies and metadata.
        components (Dict[str, List[str]]): Identified reaction components (reactants, products, catalysts).
        energy_lookup (Dict[str, Dict[str, float]]): Optimized lookup table for species energies.
    """
    
    def __init__(self, raw_data_list: List[Dict[str, Any]]):
        """
        Initialize the ProfileExtractor with calculation data.
        
        Args:
            raw_data_list (List[Dict[str, Any]]): List of calculation data dictionaries.
                Each dictionary must contain:
                - 'Species': Species identifier string
                - 'Branch': Calculation branch ('reactants', 'products', 'ts', 'preTS', 'postTS', 'cat')
                - 'Category': Calculation category ('no_cat', 'cat')
                - 'E (kcal/mol)' or 'SP_E (kcal/mol)': Electronic energy in kcal/mol
                - 'G (kcal/mol)': Gibbs free energy in kcal/mol
                - 'all_reactants': List of reactant species names
                - 'all_products': List of product species names
                - 'all_catalysts': List of catalyst species names
                - 'Calc_Type' (optional): EDA calculation type ('frz_cat', 'pol_cat', 'full_cat')
        
        Raises:
            ValueError: If raw_data_list is empty or contains invalid data.
        """
        self.raw_data = raw_data_list
        self.components = self._get_components()
        self.energy_lookup = self._build_energy_lookup()
    
    def _get_components(self) -> Dict[str, List[str]]:
        """Extract reaction components from calculation metadata."""
        if not self.raw_data:
            return {"all_reactants": [], "all_products": [], "all_catalysts": []}
        
        # Get first entry's component data (all entries should have same reaction setup)
        first_entry = self.raw_data[0]
        return {
            "all_reactants": first_entry.get("all_reactants", []),
            "all_products": first_entry.get("all_products", []),  
            "all_catalysts": first_entry.get("all_catalysts", [])
        }
    
    def _build_energy_lookup(self) -> Dict[str, Dict[str, float]]:
        """Build energy lookup table with support for calculation-specific keys."""
        energy_lookup = {}
        
        for data in self.raw_data:
            species = data.get("Species", "")
            if not species:
                continue
            
            # Get energy values
            e_val = data.get("E (kcal/mol)") or data.get("SP_E (kcal/mol)")
            g_val = data.get("G (kcal/mol)")
            
            if e_val is not None and g_val is not None:
                calc_type = data.get("Calc_Type", "")
                
                # Create calc_type-specific key if calc_type exists
                if calc_type and calc_type != "unknown":
                    energy_lookup[f"{species}_{calc_type}"] = {"E": e_val, "G": g_val}
                
                # Always create base species key
                energy_lookup[species] = {"E": e_val, "G": g_val}
        
        return energy_lookup
    
    def _get_energy(self, species: str, calc_type: str = None) -> Optional[Dict[str, float]]:
        """Get energy for species, trying calc_type-specific key first if provided."""
        if calc_type:
            calc_type_key = f"{species}_{calc_type}"
            if calc_type_key in self.energy_lookup:
                return self.energy_lookup[calc_type_key]
        
        return self.energy_lookup.get(species)
    
    def _find_entries(self, branch: str = None, category: str = None, catalyst: str = None) -> List[Dict[str, Any]]:
        """Find calculation entries matching specified metadata criteria."""
        matches = []
        for entry in self.raw_data:
            if branch and entry.get("Branch") != branch:
                continue
            if category and entry.get("Category") != category:
                continue
            if catalyst and entry.get("Catalyst") != catalyst:
                continue
            matches.append(entry)
        return matches
    
    def _create_stage(self, stage_name: str, species_list: List[str], calc_types: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Create an energy profile stage by combining species energies.
        
        Constructs a single stage in the energy profile by summing the energies
        of the specified species list.
        
        Args:
            stage_name (str): Name identifier for the profile stage.
            species_list (List[str]): List of species identifiers to combine.
            calc_types (List[str], optional): List of calculation types corresponding
                to each species. Must match length of species_list if provided.
                
        Returns:
            Optional[Dict[str, Any]]: Dictionary containing stage data with keys:
                - 'Stage': Stage name identifier
                - 'Species': Combined species string (space + separated)
                - 'E (kcal/mol)': Total electronic energy
                - 'G (kcal/mol)': Total Gibbs free energy
                - 'Source': Energy source description
                Returns None if any required energies are unavailable.
        """
        """Create stage by summing energies of species list."""
        if not species_list:
            return None
        
        total_e = total_g = 0.0
        calc_types = calc_types or [None] * len(species_list)
        
        # Sum energies for all species
        for species, calc_type in zip(species_list, calc_types):
            energy = self._get_energy(species, calc_type)
            if not energy:
                return None
            total_e += energy["E"]
            total_g += energy["G"]
        
        # Simple source description
        if len(species_list) == 1 and calc_types[0]:
            source = f"Direct ({calc_types[0]})"
        elif len(species_list) == 1:
            source = "Direct"
        else:
            source = "Addition"
        
        return {
            "Stage": stage_name,
            "Species": " + ".join(species_list),
            "E (kcal/mol)": total_e,
            "G (kcal/mol)": total_g,
            "Source": source
        }
    
    def _process_entries(self, entries: List[Dict[str, Any]], stage_prefix: str, 
                        missing_logic: callable = None, category: str = "no_cat") -> List[Dict[str, Any]]:
        """Process calculation entries to generate energy profile stages with customizable logic."""
        stages = []
        seen_combinations = set() if category == "no_cat" else None
        
        for entry in entries:
            # Get basic entry info
            species = entry["Species"]
            calc_type = entry.get("Calc_Type") if entry.get("Category") == "cat" else None
            stage_name = f"{stage_prefix}_{calc_type}" if calc_type else stage_prefix
            
            # Determine species list and calc_types
            if missing_logic:
                species_list, calc_types = missing_logic(entry)
            else:
                species_list, calc_types = [species], [calc_type] if calc_type else None
            
            # Create stage
            stage = self._create_stage(stage_name, species_list, calc_types)
            if not stage:
                continue
                
            # Handle duplicates for no_cat
            if seen_combinations is not None:
                species_set = frozenset(stage["Species"].split(" + "))
                if species_set in seen_combinations:
                    continue
                seen_combinations.add(species_set)
            
            stages.append(stage)
        
        return stages
    
    def _generate_component_stages(self, stage_name: str, branch: str, components: List[str], catalyst: str = None, category: str = "no_cat") -> List[Dict[str, Any]]:
        """Generate stages for reactants or products using entries from raw data."""
        entries = self._find_entries(branch=branch, category=category, catalyst=catalyst if category == "cat" else None)
        
        def missing_logic(entry):
            present_components = entry.get(branch, [])
            missing_components = [c for c in components if c not in present_components]
            return self._get_component_species_list(entry, missing_components, catalyst, category)
        
        return self._process_entries(entries, stage_name, missing_logic, category)
    
    def _get_component_species_list(self, entry: Dict[str, Any], missing_components: List[str], 
                                   catalyst: str, category: str) -> tuple:
        """Get species list and calc_types for component-based stages."""
        species = entry["Species"]
        calc_type = entry.get("Calc_Type", "")
        
        if category == "no_cat" and catalyst:
            if missing_components:
                # Add missing components + catalyst
                species_list = [catalyst] + [species] + missing_components
                calc_types = [calc_type] + [None] * (len(missing_components) + 1)
            else:
                # Just add catalyst
                species_list = [catalyst, species]
                calc_types = [None, calc_type] if calc_type else None
        else:
            # For "no_cat" without catalyst, or "cat" entries
            if missing_components:
                # Add missing components
                species_list = [species] + missing_components
                calc_types = [calc_type] + [None] * len(missing_components)
            else:
                # Use directly
                species_list = [species]
                calc_types = [calc_type] if calc_type else None
        
        return species_list, calc_types

    def _generate_basic_component_stages(self, component_type: str, catalyst: str = None) -> List[Dict[str, Any]]:
        """Generate energy profile stages for reactants or products."""
        # Map component types to their data
        component_mapping = {
            "reactants": ("Reactants", "reactants", "all_reactants"),
            "products": ("Products", "products", "all_products")
        }
        
        if component_type not in component_mapping:
            raise ValueError(f"Unknown component_type: {component_type}. Must be 'reactants' or 'products'")
        
        stage_name, branch, components_key = component_mapping[component_type]
        components = self.components[components_key]
        
        return self._generate_component_stages(stage_name, branch, components, catalyst)
    
    def _generate_prepost_stages(self, branch: str, stage_prefix: str, catalyst: str, component_type: str) -> List[Dict[str, Any]]:
        """Generate catalyst-specific stages (preTS/postTS) with missing component logic."""
        entries = self._find_entries(branch=branch, category="cat", catalyst=catalyst)
        
        def missing_logic(entry):
            present_components = entry.get(component_type.replace("all_", ""), [])
            missing_components = [c for c in self.components[component_type] if c not in present_components]
            calc_type = entry.get("Calc_Type", "")
            
            if missing_components:
                # Combined: base species + missing components
                species_list = [entry["Species"]] + missing_components
                calc_types = [calc_type] + [None] * len(missing_components)
            else:
                # Direct: just the base species
                species_list = [entry["Species"]]
                calc_types = [calc_type]
            
            return species_list, calc_types
        
        return self._process_entries(entries, stage_prefix, missing_logic, "cat")
    
    def _generate_ts_stages(self, catalyst: str = None) -> List[Dict[str, Any]]:
        """Generate TS stages for catalyst or no_cat."""
        if catalyst:
            entries = self._find_entries(branch="ts", category="cat", catalyst=catalyst)
            return self._process_entries(entries, "TS", category="cat")
        else:
            entries = self._find_entries(branch="ts", category="no_cat")
            return self._process_entries(entries, "TS_no_cat", category="no_cat")
    
    def extract_profiles(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract energy profiles for all reaction pathways.
        
        Generates comprehensive energy profiles for both uncatalyzed and catalyzed
        reaction pathways from the provided calculation data.
        
        Returns:
            Dict[str, List[Dict[str, Any]]]: Dictionary mapping pathway names to their
                energy profiles. Keys include:
                - 'no_cat': Uncatalyzed reaction pathway
                - '{catalyst_name}': Catalyzed pathways for each catalyst
                
                Each profile is a list of stage dictionaries containing:
                - 'Stage': Stage identifier
                - 'Species': Species combination string
                - 'E (kcal/mol)': Electronic energy
                - 'G (kcal/mol)': Gibbs free energy
                - 'Source': Energy source description
                
        Note:
            Returns empty dictionary if no calculation data is available.
            
        Example:
            >>> profiles = extractor.extract_profiles()
            >>> print(profiles['no_cat'][0])
            {'Stage': 'Reactants', 'Species': 'A + B', 'E (kcal/mol)': -100.5, 
             'G (kcal/mol)': -98.2, 'Source': 'Addition'}
        """
        if not self.raw_data:
            return {}
        
        profiles = {}
        
        # Generate no_cat profile
        no_cat_profile = []
        no_cat_profile.extend(self._generate_basic_component_stages("reactants"))
        no_cat_profile.extend(self._generate_ts_stages())
        no_cat_profile.extend(self._generate_basic_component_stages("products"))
        
        if no_cat_profile:
            profiles["no_cat"] = no_cat_profile
        
        # Generate catalyst profiles
        for catalyst in self.components["all_catalysts"]:
            catalyst_profile = []
            catalyst_profile.extend(self._generate_basic_component_stages("reactants", catalyst))
            catalyst_profile.extend(self._generate_prepost_stages("preTS", "preTS", catalyst, "all_reactants"))
            catalyst_profile.extend(self._generate_ts_stages(catalyst))
            catalyst_profile.extend(self._generate_prepost_stages("postTS", "postTS", catalyst, "all_products"))
            catalyst_profile.extend(self._generate_basic_component_stages("products", catalyst))


            if catalyst_profile:
                profiles[catalyst] = catalyst_profile
        
        return profiles
