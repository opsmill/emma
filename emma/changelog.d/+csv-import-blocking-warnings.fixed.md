A column that matches nothing in the schema no longer blocks a CSV import. It is
reported as a warning, left out of the data sent to Infrahub, and the rest of the file
is imported. Validation messages are now shown inline instead of only as toasts, which
faded after a few seconds and left the page blank with no indication of the problem.
