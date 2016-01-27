import sys
import tty
import termios


def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def file_to_string(filename, must_exist=True):
    try:
        # Well things are crappy. For decades, encoding has been a real problem
        # Git commits in the linux kernel are messy and sometimes have non-valid encoding
        # Anyway, opening a file as binary and decoding it to iso8859 solves the problem :-)
        with open(filename, 'rb') as f:
            retval = str(f.read().decode('iso8859'))
            f.close()
    except FileNotFoundError:
        print('Warning, file ' + filename + ' not found!')
        if must_exist:
            raise
        return None

    return retval


def parse_file_to_dictionary(filename, must_exist=True):
    retval = {}

    try:
        with open(filename, 'r') as f:
            for line in f:
                (key, val) = line.split()
                retval[key] = val
            f.close()
    except FileNotFoundError:
        print('Warning, file ' + filename + ' not found!')
        if must_exist:
            raise

    return retval


def write_dictionary_to_file(filename, dict):
    with open(filename, 'w') as f:
        f.write('\n'.join(map(lambda x: str(x[0]) + ' ' + str(x[1]), dict.items())) + '\n')
        f.close()
