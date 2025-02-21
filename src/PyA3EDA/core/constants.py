"""
Constants Module

Defines conversion factors and a mapping for sanitizing filenames.
"""
class Constants:
    HARTREE_TO_KCALMOL = 627.5096080305927
    CAL_TO_KCAL = 1e-3
    ESCAPE_MAP = {
        ' ': '-space-', '(': '-paren-', ')': '-paren-',
        '[': '-bracket-', ']': '-bracket-', '{': '-brace-', '}': '-brace-',
        ',': '-comma-', ';': '-semicolon-', '*': '-asterisk-', '?': '-qmark-',
        '&': '-and-', '|': '-pipe-', '<': '-lt-', '>': '-gt-',
        '"': '-dq-', "'": '-sq-', '\\': '-backslash-', ':': '-colon-',
        '$': '-dollar-', '~': '-tilde-', '!': '-exclamation-', '=': '-equal-',
        '\t': '-tab-', '\n': '-newline-',
    }
