from mido import MidiFile, MetaMessage
from ugly_midi.containers import Note
import os
import numpy as np


class Instrument(object):
    """Object representing a midi instrument"""

    def __init__(self, program, is_drum=False, name=''):
        self.program = program
        self.is_drum = is_drum
        self.name = name
        self.notes = []

    def add_note(self, note):
        self.notes.append(note)

    def get_piano_roll(self, end_time=None):
        """Gets a piano roll aligned by beats"""
        if not self.notes:
            return np.array([[] * 128])

        end_time = self.get_end_time() if end_time is None else end_time
        piano_roll = np.zeros((end_time, 128))

        # fill piano roll with notes
        for n in self.notes:
            start = n.start
            if start >= end_time:
                continue
            end = min(n.end, end_time)
            piano_roll[start:end, n.pitch] += n.velocity

        # TODO: pitch bends and pedals
        return piano_roll

    def get_end_time(self):
        if not self.notes:
            return 0
        return max([n.end for n in self.notes])

    def remove_invalid_notes(self):
        self.notes = [n for n in self.notes if n.start < n.end]

    def change_resolution(self, scale, discard_short_notes=False):
        for n in self.notes:
            start = round(n.start * scale)
            end = round(n.end * scale)
            if start == end:
                if discard_short_notes:
                    return
                end += 1
            n.start, n.end = start, end

    def __repr__(self):
        return 'Instrument(program={}, is_drum={}, name="{}")'.format(
            self.program, self.is_drum, self.name.replace('"', r'\"'))


def get_instrument_from_piano_roll(roll, program=0, is_drum=False, name=''):
    if not isinstance(roll, np.ndarray):
        raise TypeError('Piano roll should be an np.ndarray')
    if len(roll.shape) != 2 or roll.shape[1] != 128:
        raise ValueError('Piano roll must have shape [frames x 128]')

    instr = Instrument(program, is_drum, name)

    for pitch in range(roll.shape[1]):
        prev_val = 0
        start_t = -1
        for t in range(roll.shape[0]):
            curr_val = roll[t, pitch]
            if prev_val == 0 and curr_val != 0:
                start_t = t
            if prev_val != 0 and curr_val == 0:
                instr.add_note(Note(prev_val, pitch, start_t, t))
                start_t = -1
            prev_val = curr_val
        # add the note that last to the end
        if prev_val != 0:
            instr.add_note(Note(prev_val, pitch, start_t, roll.shape[0]))
    return instr
