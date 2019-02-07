from ugly_midi.midi_file import MidiObject
from ugly_midi.instrument import Instrument
from ugly_midi.containers import Note, TempoChange
import numpy as np


def program2family(prog):
    if prog < 8:
        return 'Piano'
    if prog < 16:
        return 'Chromatic Percussion'
    if prog < 24:
        return 'Organ'
    if prog < 32:
        return 'Guitar'
    if prog < 40:
        return 'Bass'
    if prog < 48:
        return 'Strings'
    if prog < 56:
        return 'Ensemble'
    if prog < 64:
        return 'Brass'
    if prog < 72:
        return 'Reed'
    if prog < 80:
        return 'Pipe'
    if prog < 88:
        return 'Synth Lead'
    if prog < 96:
        return 'Synth Pad'
    if prog < 104:
        return 'Synth Effects'
    if prog < 112:
        return 'Ethnic'
    if prog < 120:
        return 'Percussive'
    if prog < 128:
        return 'Sound Effects'


def program2family5(prog):
    family = program2family(prog)
    if family in ['Piano', 'Chromatic Percussion']:
        return 'Piano'
    if family in ['Guitar']:
        return 'Guitar'
    if family in ['Bass']:
        return 'Bass'
    if family in [
            'Organ', 'Strings', 'Ensemble', 'Synth Lead', 'Synth Pad', 'Brass',
            'Reed', 'Pipe', 'Ethnic'
    ]:
        return 'Ensemble'
    return -1


def family2program(name):
    """
    classify instruments into 5 categories
    """
    if name in ['Piano', 'Chromatic Percussion']:
        return 0
    if name in ['Guitar']:
        return 24
    if name in ['Bass']:
        return 32
    if name in [
            'Organ', 'Strings', 'Ensemble', 'Synth Lead', 'Synth Pad', 'Brass',
            'Reed', 'Pipe', 'Ethnic'
    ]:
        return 40
    return -1


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


def merge_instruments(instr1, instr2):
    assert isinstance(instr1, Instrument)
    assert isinstance(instr2, Instrument)
    assert instr1.is_drum == instr2.is_drum

    instr = Instrument(
        instr1.program, is_drum=instr1.is_drum, name=instr1.name)
    instr.notes = instr1.notes + instr2.notes
    return instr


def midi_write_pianoroll(midi_file,
                         roll,
                         resolution,
                         program=0,
                         is_drum=False,
                         bpm=120):
    mid = MidiObject(resolution=resolution)
    mid.add_instrument(get_instrument_from_piano_roll(roll, program, is_drum))
    mid.tempo_changes = [TempoChange(bpm, 0)]
    mid.write(midi_file)
