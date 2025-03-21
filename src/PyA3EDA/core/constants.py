"""
Constants Module

Defines conversion factors and a mapping for sanitizing filenames.
"""
class Constants:
    HARTREE_TO_KJMOL = 2625.5002 # Hartree to kJ/mol
    KJMOL_TO_KCALMOL = 1.0/4.184 # kJ/mol to kcal/mol
    HARTREE_TO_KCALMOL = HARTREE_TO_KJMOL * KJMOL_TO_KCALMOL # Hartree to kcal/mol 627.5096080305926
    TO_KILO = 1e-3
    ESCAPE_MAP = {
        ' ': '-space-', '(': '-lparen-', ')': '-rparen-',
        '[': '-lbracket-', ']': '-rbracket-', '{': '-lbrace-', '}': '-rbrace-',
        ',': '-comma-', ';': '-semicolon-', '*': '-asterisk-', '?': '-qmark-',
        '&': '-and-', '|': '-pipe-', '<': '-lt-', '>': '-gt-',
        '"': '-dq-', "'": '-sq-', '\\': '-backslash-', ':': '-colon-',
        '$': '-dollar-', '~': '-tilde-', '!': '-exclamation-', '=': '-equal-',
        '\t': '-tab-', '\n': '-newline-',
    }
