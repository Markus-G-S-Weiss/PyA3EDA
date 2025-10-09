"""
Constants Module

Defines conversion factors and a mapping for sanitizing filenames.
"""
class Constants:
    HARTREE_TO_J=4.3597447222060e-18 # Hartree to J
    TO_KILO = 1.0e-3
    HARTREE_TO_KJ = HARTREE_TO_J * TO_KILO # Hartree to kJ
    AVOGADRO = 6.02214076e23 # Avogadro's number in mol^-1
    HARTREE_TO_KJMOL = HARTREE_TO_KJ * AVOGADRO # Hartree to kJ/mol
    KJMOL_TO_KCALMOL = 1.0/4.184 # kJ/mol to kcal/mol
    HARTREE_TO_KCALMOL = HARTREE_TO_KJMOL * KJMOL_TO_KCALMOL # Hartree to kcal/mol
    KJMOL_TO_HARTREE = 1.0 / 2625.5311584660003 # value for bsse conversion
    ESCAPE_MAP = {
        ' ': '-space-', '(': '-lparen-', ')': '-rparen-',
        '[': '-lbracket-', ']': '-rbracket-', '{': '-lbrace-', '}': '-rbrace-',
        ',': '-comma-', ';': '-semicolon-', '*': '-asterisk-', '?': '-qmark-',
        '&': '-and-', '|': '-pipe-', '<': '-lt-', '>': '-gt-',
        '"': '-dq-', "'": '-sq-', '\\': '-backslash-', ':': '-colon-',
        '$': '-dollar-', '~': '-tilde-', '!': '-exclamation-', '=': '-equal-',
        '\t': '-tab-', '\n': '-newline-',
    }
