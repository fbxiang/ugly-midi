"""
containers copied from the Pretty Midi Project
https://github.com/craffel/pretty-midi
"""


class Note(object):
    """A note event.
    Parameters
    ----------
    velocity : int
        Note velocity.
    pitch : int
        Note pitch, as a MIDI note number.
    start : float
        Note on time, absolute, in seconds.
    end : float
        Note off time, absolute, in seconds.
    """

    def __init__(self, velocity, pitch, start, end):
        self.velocity = int(velocity)
        self.pitch = int(pitch)
        self.start = int(start)
        self.end = int(end)

    def get_duration(self):
        """Get the duration of the note in seconds."""
        return self.end - self.start

    @property
    def duration(self):
        return self.get_duration()

    def __repr__(self):
        return 'Note(start={:f}, end={:f}, pitch={}, velocity={})'.format(
            self.start, self.end, self.pitch, self.velocity)


class TimeSignature(object):
    """Container for a Time Signature event, which contains the time signature
    numerator, denominator and the event time in seconds.
    Attributes
    ----------
    numerator : int
        Numerator of time signature.
    denominator : int
        Denominator of time signature.
    time : float
        Time of event in seconds.
    Examples
    --------
    Instantiate a TimeSignature object with 6/8 time signature at 3.14 seconds:
    >>> ts = TimeSignature(6, 8, 3.14)
    >>> print(ts)
    6/8 at 3.14 seconds
    """

    def __init__(self, numerator, denominator, time):
        if not (isinstance(numerator, int) and numerator > 0):
            raise ValueError('{} is not a valid `numerator` type or value'.
                             format(numerator))
        if not (isinstance(denominator, int) and denominator > 0):
            raise ValueError('{} is not a valid `denominator` type or value'.
                             format(denominator))
        if not (isinstance(time, (int, float)) and time >= 0):
            raise ValueError(
                '{} is not a valid `time` type or value'.format(time))

        self.numerator = numerator
        self.denominator = denominator
        self.time = time

    def __repr__(self):
        return "TimeSignature(numerator={}, denominator={}, time={})".format(
            self.numerator, self.denominator, self.time)

    def __str__(self):
        return '{}/{} at {:.2f} seconds'.format(self.numerator,
                                                self.denominator, self.time)


class KeySignature(object):
    """Contains the key signature and the event time in seconds.
    Attributes
    """

    def __init__(self, key, time):
        # if not isinstance(key_number, int) or key_number < 0 or key_number >= 24:
        #     raise ValueError('{} is not a valid `key_number` type or value'.
                             # format(key_number))
        if not (isinstance(time, (int, float)) and time >= 0):
            raise ValueError(
                '{} is not a valid `time` type or value'.format(time))

        self.key = key
        self.time = time

    def __repr__(self):
        return "KeySignature(key={}, time={})".format(
            self.key, self.time)

    def __str__(self):
        return '{} at {:.2f} seconds'.format(self.key, self.time)


class TempoChange(object):
    def __init__(self, bpm, time):
        if not (isinstance(bpm, (int, float)) and bpm >= 0):
            raise ValueError(
                '{} is not a valid `tepmo` type or value'.format(bpm))

        if not (isinstance(time, (int, float)) and time >= 0):
            raise ValueError(
                '{} is not a valid `time` type or value'.format(time))

        self.bpm = bpm
        self.time = time

    def __repr__(self):
        return "TempoChange(bpm={}, time={})".format(self.bpm, self.time)

    def __str__(self):
        return "Tempo changes to {} at {}".format(self.bpm, self.time)
