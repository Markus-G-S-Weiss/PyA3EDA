"""
Clean Profile Extractor - DRY Metadata-Driven Approach

Extract energy profiles using calculation-specific components from metadata.
No name parsing - metadata is the single source of truth.
"""
from typing import Dict, List, Any, Optional


class ProfileExtractor:
    """Clean, DRY profile extraction using metadata-driven approach."""
    
    def __init__(self, raw_data_list: List[Dict[str, Any]]):
        """Initialize with raw calculation data."""
        self.raw_data = raw_data_list
        self.components = self._get_components()
        self.energy_lookup = self._build_energy_lookup()
    
    def _get_components(self) -> Dict[str, List[str]]:
        """Extract complete reaction components from metadata."""
        if not self.raw_data:
            return {"all_reactants": [], "all_products": [], "all_catalysts": []}
        
        first_entry = self.raw_data[0]
        return {
            "all_reactants": first_entry.get("all_reactants", []),
            "all_products": first_entry.get("all_products", []),
            "all_catalysts": first_entry.get("all_catalysts", [])
        }
    
    def _build_energy_lookup(self) -> Dict[str, Dict[str, float]]:
        """Build energy lookup table with calc_type-specific keys."""
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
        """Get energy for species, trying calc_type-specific key first."""
        if calc_type:
            calc_type_key = f"{species}_{calc_type}"
            if calc_type_key in self.energy_lookup:
                return self.energy_lookup[calc_type_key]
        
        return self.energy_lookup.get(species)
    
    def _find_entries(self, branch: str = None, category: str = None, catalyst: str = None) -> List[Dict[str, Any]]:
        """Find entries matching metadata criteria."""
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
    
    def _create_additive_stage(self, stage_name: str, species_list: List[str], calc_type: str = None) -> Optional[Dict[str, Any]]:
        """Create stage by adding energies of multiple species."""
        total_e = total_g = 0.0
        
        for species in species_list:
            energy = self._get_energy(species, calc_type)
            if not energy:
                return None
            total_e += energy["E"]
            total_g += energy["G"]
        
        return {
            "Stage": stage_name,
            "Species": " + ".join(species_list),
            "E (kcal/mol)": total_e,
            "G (kcal/mol)": total_g,
            "Source": f"Energy addition: {' + '.join(species_list)}"
        }
    
    def _create_direct_stage(self, stage_name: str, species: str, calc_type: str = None) -> Optional[Dict[str, Any]]:
        """Create stage from direct calculation."""
        energy = self._get_energy(species, calc_type)
        if not energy:
            return None
        
        calc_type_str = f" ({calc_type})" if calc_type else ""
        return {
            "Stage": stage_name,
            "Species": species,
            "E (kcal/mol)": energy["E"],
            "G (kcal/mol)": energy["G"],
            "Source": f"Direct calculation: {species}{calc_type_str}"
        }
    
    def _create_combined_stage(self, stage_name: str, base_entry: Dict[str, Any], missing_components: List[str]) -> Optional[Dict[str, Any]]:
        """Create stage by combining base calculation with missing components."""
        calc_type = base_entry.get("Calc_Type", "")
        base_species = base_entry["Species"]
        
        # Get base energy with calc_type
        base_energy = self._get_energy(base_species, calc_type)
        if not base_energy:
            return None
        
        total_e = base_energy["E"]
        total_g = base_energy["G"]
        
        # Add missing components
        for component in missing_components:
            component_energy = self._get_energy(component)
            if not component_energy:
                return None
            total_e += component_energy["E"]
            total_g += component_energy["G"]
        
        species_list = [base_species] + missing_components
        return {
            "Stage": stage_name,
            "Species": " + ".join(species_list),
            "E (kcal/mol)": total_e,
            "G (kcal/mol)": total_g,
            "Source": f"Energy addition: {' + '.join(species_list)}"
        }
    
    def _generate_basic_stages(self, catalyst: str = None) -> List[Dict[str, Any]]:
        """Generate reactants and products stages."""
        stages = []
        
        # Reactants stage
        if catalyst:
            reactants_species = [catalyst] + self.components["all_reactants"]
        else:
            reactants_species = self.components["all_reactants"]
        
        reactants_stage = self._create_additive_stage("Reactants", reactants_species)
        if reactants_stage:
            stages.append(reactants_stage)
        
        # Products stage
        if catalyst:
            products_species = [catalyst] + self.components["all_products"]
        else:
            products_species = self.components["all_products"]
        
        products_stage = self._create_additive_stage("Products", products_species)
        if products_stage:
            stages.append(products_stage)
        
        return stages
    
    def _generate_ts_stages(self, catalyst: str = None) -> List[Dict[str, Any]]:
        """Generate TS stages for catalyst or no_cat."""
        stages = []
        
        if catalyst:
            ts_entries = self._find_entries(branch="ts", category="cat", catalyst=catalyst)
            for entry in ts_entries:
                calc_type = entry.get("Calc_Type", "unknown")
                stage = self._create_direct_stage(f"TS_{calc_type}", entry["Species"], calc_type)
                if stage:
                    stages.append(stage)
        else:
            ts_entries = self._find_entries(branch="ts", category="no_cat")
            for entry in ts_entries:
                stage = self._create_direct_stage("TS_no_cat", entry["Species"])
                if stage:
                    stages.append(stage)
        
        return stages
    
    def _generate_pretsm_stages(self, catalyst: str) -> List[Dict[str, Any]]:
        """Generate preTS stages for catalyst."""
        stages = []
        pretsm_entries = self._find_entries(branch="preTS", category="cat", catalyst=catalyst)
        
        for entry in pretsm_entries:
            calc_type = entry.get("Calc_Type", "unknown")
            present_reactants = entry.get("reactants", [])
            missing_reactants = [r for r in self.components["all_reactants"] if r not in present_reactants]
            
            if missing_reactants:
                stage = self._create_combined_stage(f"preTS_{calc_type}", entry, missing_reactants)
            else:
                stage = self._create_direct_stage(f"preTS_{calc_type}", entry["Species"], calc_type)
            
            if stage:
                stages.append(stage)
        
        return stages
    
    def _generate_postsm_stages(self, catalyst: str) -> List[Dict[str, Any]]:
        """Generate postTS stages for catalyst."""
        stages = []
        postsm_entries = self._find_entries(branch="postTS", category="cat", catalyst=catalyst)
        
        for entry in postsm_entries:
            calc_type = entry.get("Calc_Type", "unknown")
            present_products = entry.get("products", [])
            missing_products = [p for p in self.components["all_products"] if p not in present_products]
            
            if missing_products:
                stage = self._create_combined_stage(f"postTS_{calc_type}", entry, missing_products)
            else:
                stage = self._create_direct_stage(f"postTS_{calc_type}", entry["Species"], calc_type)
            
            if stage:
                stages.append(stage)
        
        return stages
    
    def extract_profiles(self) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all energy profiles."""
        if not self.raw_data:
            return {}
        
        profiles = {}
        
        # Generate no_cat profile
        no_cat_profile = []
        no_cat_profile.extend(self._generate_basic_stages())
        no_cat_profile.extend(self._generate_ts_stages())
        
        if no_cat_profile:
            profiles["no_cat"] = no_cat_profile
        
        # Generate catalyst profiles
        for catalyst in self.components["all_catalysts"]:
            catalyst_profile = []
            catalyst_profile.extend(self._generate_basic_stages(catalyst))
            catalyst_profile.extend(self._generate_ts_stages(catalyst))
            catalyst_profile.extend(self._generate_pretsm_stages(catalyst))
            catalyst_profile.extend(self._generate_postsm_stages(catalyst))
            
            if catalyst_profile:
                profiles[catalyst] = catalyst_profile
        
        return profiles


def extract_profile_data(raw_data_list: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Main function: Extract energy profiles from raw calculation data.
    
    Args:
        raw_data_list: Raw calculation data with metadata
        
    Returns:
        Dict mapping catalyst names to their energy profiles
    """
    extractor = ProfileExtractor(raw_data_list)
    return extractor.extract_profiles()
