from ugly_midi.instrument import Instrument, get_instrument_from_piano_roll
from ugly_midi.containers import Note, TimeSignature, KeySignature, TempoChange
from mido import MidiFile, MetaMessage, Message, bpm2tempo, tempo2bpm
import numpy as np
import warnings
import collections

MAX_TICK = 1e7


class MidiLoader(object):
    """Class for reading midi files"""

    def __init__(self, midi_file, resolution=None):
        midi_data = MidiFile(midi_file)
        if midi_data.type != 1:
            raise ValueError('Midi type {} ({}) is not supported.'.format(
                midi_data.type, midi_file))
        if len(midi_data.tracks) <= 1:
            raise ValueError(
                'File {} appears to have too few midi tracks. It is invalid.'.
                format(midi_file))
        if resolution is not None:
            if (not isinstance(resolution, int)) or (resolution <= 0):
                raise ValueError(
                    'Invalid resolution {} specified. Expecting a positive integer.'
                    .format(resolution))

        # convert tick to absolute
        for track in midi_data.tracks:
            tick = 0
            for event in track:
                event.time += tick
                tick = event.time

        self.resolution = midi_data.ticks_per_beat
        self._load_track0(midi_data)

        max_tick = max([max([e.time for e in t])
                        for t in midi_data.tracks]) + 1

        if max_tick > MAX_TICK:
            raise ValueError(('MIDI file has a largest tick of {},'
                              ' it is likely corrupt'.format(max_tick)))

        # Check that there are tempo, key and time change events
        # only on track 0
        if any(
                e.type in ('set_tempo', 'key_signature', 'time_signature')
                for track in midi_data.tracks[1:] for e in track):
            warnings.warn(
                "Tempo, Key or Time signature change events found on "
                "non-zero tracks.  This is not a valid type 0 or type 1 "
                "MIDI file.  Tempo, Key or Time Signature may be wrong.",
                RuntimeWarning)

        # Populate the list of instruments
        self._load_instruments(midi_data)

        if resolution:
            self._change_resolution(resolution)

    def _load_track0(self, midi_data):
        self.key_signatures = []
        self.time_signatures = []
        self.tempo_changes = []

        for msg in midi_data.tracks[0]:
            if msg.type == 'key_signature':
                self.key_signatures.append(KeySignature(msg.key, msg.time))
            elif msg.type == 'time_signature':
                self.time_signatures.append(
                    TimeSignature(msg.numerator, msg.denominator, msg.time))
            elif msg.type == 'set_tempo':
                self.tempo_changes.append(
                    TempoChange(tempo2bpm(msg.tempo), msg.time))
            elif msg.type in ['note_on', 'note_off']:
                warnings.warn(
                    'Track 0 contains note information; This file may be invalid.',
                    RuntimeWarning)

    def _load_instruments(self, midi_data):
        """Populates ``self.instruments`` using ``midi_data``.
        Parameters
        ----------
        midi_data : midi.FileReader
            MIDI object from which data will be read.
        """
        # MIDI files can contain a collection of tracks; each track can have
        # events occuring on one of sixteen channels, and events can correspond
        # to different instruments according to the most recently occurring
        # program number.  So, we need a way to keep track of which instrument
        # is playing on each track on each channel.  This dict will map from
        # program number, drum/not drum, channel, and track index to instrument
        # indices, which we will retrieve/populate using the __get_instrument
        # function below.
        instrument_map = collections.OrderedDict()
        # Store a similar mapping to instruments storing "straggler events",
        # e.g. events which appear before we want to initialize an Instrument
        stragglers = {}
        # This dict will map track indices to any track names encountered
        track_name_map = collections.defaultdict(str)

        def __get_instrument(program, channel, track):

            if (program, channel, track) in instrument_map:
                return instrument_map[(program, channel, track)]

            is_drum = (channel == 9)
            instrument = Instrument(program, is_drum,
                                    track_name_map[track_idx])

            # If any events appeared for this instrument before now,
            # include them in the new instrument
            if (channel, track) in stragglers:
                straggler = stragglers[(channel, track)]
                instrument.control_changes = straggler.control_changes
                instrument.pitch_bends = straggler.pitch_bends
            # Add the instrument to the instrument map
            instrument_map[(program, channel, track)] = instrument

            return instrument

        # NOTICE: it is actually possible to use program_change to affect other
        # channels.

        # all_events contain [track_idx, event]
        all_events = []
        for track_idx, track in enumerate(midi_data.tracks):
            for event in track:
                if event.type == 'track_name':
                    track_name_map[track_idx] = event.name
                elif event.type in ['program_change', 'note_on', 'note_off']:
                    all_events.append([track_idx, event])

        all_events = sorted(all_events, key=lambda e: e[1].time)

        current_instrument = np.zeros(16, dtype=np.int)
        # note on in one track and note off in another track is too ridiculous
        last_note_on = {}
        for track_id, event in all_events:
            if event.type == 'program_change':
                current_instrument[event.channel] = event.program
            elif event.type == 'note_on' and event.velocity > 0:
                # put the note into the note-on list, record its instrument
                last_note_on[(track_id, event.channel, event.note)] = [
                    current_instrument[event.channel], event.velocity,
                    event.time
                ]
            elif event.type == 'note_off' or (event.type == 'note_on'
                                              and event.velocity == 0):
                # ignore spurious note-offs
                key = (track_id, event.channel, event.note)
                if key in last_note_on:
                    prog, vel, t = last_note_on[key]
                    instr = __get_instrument(prog, event.channel, track_id)
                    if event.time == t:
                        continue
                    instr.add_note(Note(vel, event.note, t, event.time))
                    del last_note_on[(track_id, event.channel, event.note)]

        # TODO: add support for pitch bend and control changes

        # Initialize list of instruments from instrument_map
        self.instruments = [i for i in instrument_map.values()]

    def _change_resolution(self, res):
        if self.resolution == res:
            return

        scale = res / self.resolution
        for ins in self.instruments:
            ins.change_resolution(scale)
        self.resolution = res

    def write(self, midi_file):
        mid = MidiFile(ticks_per_beat=self.resolution)

        track = mid.add_track()

        events = []
        for ks in self.key_signatures:
            events.append(
                MetaMessage('key_signature', key=ks.key, time=ks.time))
        for ts in self.time_signatures:
            events.append(
                MetaMessage(
                    'time_signature',
                    numerator=ts.numerator,
                    denominator=ts.denominator,
                    time=ts.time))
        for tc in self.tempo_changes:
            events.append(
                MetaMessage(
                    'set_tempo', tempo=bpm2tempo(tc.bpm), time=tc.time))
        events = sorted(events, key=lambda msg: msg.time)
        now = 0
        for msg in events:
            msg.time -= now
            track.append(msg)
            now += msg.time

        if len([instr
                for instr in self.instruments if not instr.is_drum]) > 15:
            warnings.warn(
                "Synthesizing with more than 15 instruments is not supported",
                RuntimeWarning)

        current_channel = 0
        for instr in self.instruments:
            track = mid.add_track()
            channel = 9 if instr.is_drum else current_channel

            track.append(
                Message(
                    'program_change',
                    channel=channel,
                    program=instr.program,
                    time=0))

            note_msgs = []
            for n in instr.notes:
                note_msgs.append(
                    Message(
                        'note_on',
                        channel=channel,
                        note=n.pitch,
                        velocity=n.velocity,
                        time=n.start))
                note_msgs.append(
                    Message(
                        'note_off',
                        channel=channel,
                        note=n.pitch,
                        velocity=0,
                        time=n.end))

            note_msgs = sorted(note_msgs, key=lambda msg: msg.time)
            now = 0
            for msg in note_msgs:
                track.append(msg.copy(time=msg.time - now))
                now = msg.time

            if not instr.is_drum:
                current_channel += 1
                if current_channel > 15:
                    break

        mid.save(midi_file)


class MidiWriter(object):
    def __init__(self, resolution):
        self.instruments = []
        self.tempo_changes = []
        self.key_signatures = []
        self.time_signatures = []
        self.resolution = resolution

    def add_instrument(self, instr):
        if not isinstance(instr, Instrument):
            raise TypeError('Expecting an Instrument')

        self.instruments.append(instr)

    # TODO: add functions for tempo and signatures

    def write(self, midi_file):
        mid = MidiFile(ticks_per_beat=self.resolution)

        if not self.time_signatures:
            self.time_signatures = [TimeSignature(4, 4, 0)]

        if not self.tempo_changes:
            self.tempo_changes = [TempoChange(120, 0)]

        track = mid.add_track()

        events = []
        for ks in self.key_signatures:
            events.append(
                MetaMessage('key_signature', key=ks.key, time=ks.time))
        for ts in self.time_signatures:
            events.append(
                MetaMessage(
                    'time_signature',
                    numerator=ts.numerator,
                    denominator=ts.denominator,
                    time=ts.time))
        for tc in self.tempo_changes:
            events.append(
                MetaMessage(
                    'set_tempo', tempo=bpm2tempo(tc.bpm), time=tc.time))
        events = sorted(events, key=lambda msg: msg.time)
        now = 0
        for msg in events:
            msg.time -= now
            track.append(msg)
            now += msg.time

        if len([instr
                for instr in self.instruments if not instr.is_drum]) > 15:
            warnings.warn(
                "Synthesizing with more than 15 instruments is not supported",
                RuntimeWarning)

        current_channel = 0
        for instr in self.instruments:
            track = mid.add_track()
            channel = 9 if instr.is_drum else current_channel

            track.append(
                Message(
                    'program_change',
                    channel=channel,
                    program=instr.program,
                    time=0))

            note_msgs = []
            for n in instr.notes:
                note_msgs.append(
                    Message(
                        'note_on',
                        channel=channel,
                        note=n.pitch,
                        velocity=n.velocity,
                        time=n.start))
                note_msgs.append(
                    Message(
                        'note_off',
                        channel=channel,
                        note=n.pitch,
                        velocity=0,
                        time=n.end))

            note_msgs = sorted(note_msgs, key=lambda msg: msg.time)
            now = 0
            for msg in note_msgs:
                track.append(msg.copy(time=msg.time - now))
                now = msg.time

            if not instr.is_drum:
                current_channel += 1
                if current_channel > 15:
                    break

        mid.save(midi_file)





# import matplotlib.pyplot as plt
# from ugly_midi.instrument import get_instrument_from_piano_roll
# mid = MidiLoader('/home/fx/bach/data/bach/aof/can1.mid', resolution=24)
# roll = mid.instruments[0].get_piano_roll()

# instr = get_instrument_from_piano_roll(roll)
# roll = instr.get_piano_roll()

# midi_write_pianoroll('/tmp/test.mid', roll, 24)

# plt.imshow(roll.T, aspect='auto')
# plt.gca().invert_yaxis()
# plt.show()
