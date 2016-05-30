import re


class Diff:
    DIFF_SELECTOR_REGEX = re.compile(r'^[-\+@]')

    # The two-line unified diff headers
    FILE_SEPARATOR_MINUS_REGEX = re.compile(r'^--- (.+)$')
    FILE_SEPARATOR_PLUS_REGEX = re.compile(r'^\+\+\+ (.+)$')

    # Exclude '--cc' diffs
    EXCLUDE_CC_REGEX = re.compile(r'^diff --cc (.+)$')

    # Hunks inside a file
    HUNK_REGEX = re.compile(r'^@@ -([0-9]+),?([0-9]+)? \+([0-9]+),?([0-9]+)? @@ ?(.*)$')
    DIFF_REGEX = re.compile(r'^[\+-](.*)$')

    def __init__(self, patches, lines):
        self._patches = patches
        self._lines = lines

        self._affected = set()
        for i, j in self.patches.keys():
            # The [2:] will strip a/ and b/
            if '/dev/null' not in i:
                self._affected.add(i[2:])
            if '/dev/null' not in j:
                self._affected.add(j[2:])

    @property
    def lines(self):
        return self._lines

    @property
    def patches(self):
        return self._patches

    @property
    def affected(self):
        return self._affected

    @staticmethod
    def parse_diff(diff):
        # Split by linebreaks and filter empty lines
        # Only split at \n and not at \r
        diff = list(filter(None, diff.split('\n')))

        # diff length ratio
        # Filter parts of interest
        lines_of_interest = list(filter(lambda x: Diff.DIFF_SELECTOR_REGEX.match(x), diff))
        diff_lines = sum(map(len, lines_of_interest))

        # Check if we understand the diff format
        if diff and Diff.EXCLUDE_CC_REGEX.match(diff[0]):
            return 0, {}

        retval = {}

        while len(diff):
            # Consume till the first occurence of '--- '
            while len(diff):
                minus = diff.pop(0)
                if Diff.FILE_SEPARATOR_MINUS_REGEX.match(minus):
                    break
            if len(diff) == 0:
                break
            minus = Diff.FILE_SEPARATOR_MINUS_REGEX.match(minus).group(1)
            plus = Diff.FILE_SEPARATOR_PLUS_REGEX.match(diff.pop(0)).group(1)

            diff_index = minus, plus
            if diff_index not in retval:
                retval[diff_index] = {}

            while len(diff) and Diff.HUNK_REGEX.match(diff[0]):
                hunk = Diff.HUNK_REGEX.match(diff.pop(0))

                # l_start = int(hunk.group(1))
                l_lines = 1
                if hunk.group(2):
                    l_lines = int(hunk.group(2))

                # r_start = int(hunk.group(3))
                r_lines = 1
                if hunk.group(4):
                    r_lines = int(hunk.group(4))

                hunktitle = hunk.group(5)

                del_cntr = 0
                add_cntr = 0
                hunk_changes = [], []  # [removed], [inserted]
                while not (del_cntr == l_lines and add_cntr == r_lines):
                    line = diff.pop(0)
                    if line[0] == '+':
                        hunk_changes[1].append(line[1:])
                        add_cntr += 1
                    elif line[0] == '-':
                        hunk_changes[0].append(line[1:])
                        del_cntr += 1
                    elif line[0] != '\\':  # '\\ No new line... statements
                        add_cntr += 1
                        del_cntr += 1

                hunk_changes = (list(filter(None, hunk_changes[0])),
                                list(filter(None, hunk_changes[1])))

                if hunktitle not in retval[diff_index]:
                    retval[diff_index][hunktitle] = [], []
                retval[diff_index][hunktitle] = (retval[diff_index][hunktitle][0] + hunk_changes[0],
                                                 retval[diff_index][hunktitle][1] + hunk_changes[1])

        return Diff(retval, diff_lines)