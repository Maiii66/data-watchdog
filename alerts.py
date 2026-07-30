# Print alert messages in a clearly visible format.
def warn(message: str):
    border = '*' * (len(message) + 10)
    print(f"\n  {border}\n  *** ALERT: {message} ***\n  {border}\n")
