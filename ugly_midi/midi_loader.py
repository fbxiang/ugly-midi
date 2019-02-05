from .instrument import Instrument
from .containers import Note, TimeSignature, KeySignature, TempoChange
from mido import MidiFile
import numpy as np
import warnings
import collections

MAX_TICK = 1e7


class UglyMidiFile(object):
    """Class for reading midi files"""

    def __init__(self, midi_file):
        midi_data = MidiFile(midi_file)
        assert midi_data.type == 1
        assert len(midi_data.tracks) > 1

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
                self.tempo_changes.append(TempoChange(msg.tempo, msg.time))
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

        def __get_instrument(program, channel, track, create_new):
            """Gets the Instrument corresponding to the given program number,
            drum/non-drum type, channel, and track index.  If no such
            instrument exists, one is created.
            """
            # If we have already created an instrument for this program
            # number/track/channel, return it
            if (program, channel, track) in instrument_map:
                return instrument_map[(program, channel, track)]
            # If there's a straggler instrument for this instrument and we
            # aren't being requested to create a new instrument
            if not create_new and (channel, track) in stragglers:
                return stragglers[(channel, track)]
            # If we are told to, create a new instrument and store it
            if create_new:
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
            # Otherwise, create a "straggler" instrument which holds events
            # which appear before we actually want to create a proper new
            # instrument
            else:
                # Create a "straggler" instrument
                instrument = Instrument(program, track_name_map[track_idx])
                # Note that stragglers ignores program number, because we want
                # to store all events on a track which appear before the first
                # note-on, regardless of program
                stragglers[(channel, track)] = instrument
            return instrument

        # NOTICE: it is actually possible to use program_change to affect other
        # channels.

        # all_events contain [track_idx, event]
        all_events = []
        for track_idx, track in enumerate(midi_data.tracks):
            for event in track:
                if event.type == 'track_name':
                    track_name_map[track_idx] = event.name
                elif event.type == 'program_change':
                    all_events.append([track_idx, event])
                elif event.type == 'note_on' and event.velocity > 0:
                    all_events.append([track_idx, event])
                elif event.type == 'note_off' or (event.type == 'note_on'
                                                  and event.velocity == 0):
                    event.type = 'note_off'
                    all_events.append([track_idx, event])

        all_events = sorted(all_events, lambda e: e[1].time)

        current_instrument = np.zeros(16, dtype=np.int)
        # note on in one track and note off in another track is too ridiculous
        last_note_on = {}
        for track_id, event in all_events:
            if event.type == 'program_change':
                current_instrument[event.channel] = event.program
            elif event.type == 'note_on':
                # put the note into the note-on list, record its instrument
                last_note_on[(track_id, event.channel, event.note)] = [
                    current_instrument[event.channel], event.velocity,
                    event.time
                ]
            elif event.type == 'note_off':
                # ignore spurious note-offs
                key = (track_id, event.channel, event.note)
                if key in last_note_on:
                    prog, vel, t = last_note_on[key]
                    instr = __get_instrument(prog, event.channel, track_id,
                                             True)
                    if event.time == t:
                        continue
                    instr.add_note(Note(vel, event.note, t, event.time))
                    del last_note_on[(track_id, event.channel, event.note)]

        # for track_idx, track in enumerate(midi_data.tracks):
        #     # Keep track of last note on location:
        #     # key = (instrument, note),
        #     # value = (note-on tick, velocity)
        #     last_note_on = collections.defaultdict(list)
        #     # Keep track of which instrument is playing in each channel
        #     # initialize to program 0 for all channels
        #     current_instrument = np.zeros(16, dtype=np.int)
        #     for event in track:
        #         # Look for track name events
        #         if event.type == 'track_name':
        #             # Set the track name for the current track
        #             track_name_map[track_idx] = event.name
        #         # Look for program change events
        #         if event.type == 'program_change':
        #             # Update the instrument for this channel
        #             current_instrument[event.channel] = event.program
        #         # Note ons are note on events with velocity > 0
        #         elif event.type == 'note_on' and event.velocity > 0:
        #             # Store this as the last note-on location
        #             note_on_index = (event.channel, event.note)
        #             last_note_on[note_on_index].append((event.time,
        #                                                 event.velocity))
        #         # Note offs can also be note on events with 0 velocity
        #         elif event.type == 'note_off' or (event.type == 'note_on'
        #                                           and event.velocity == 0):
        #             # Check that a note-on exists (ignore spurious note-offs)
        #             key = (event.channel, event.note)
        #             if key in last_note_on:
        #                 # Get the start/stop times and velocity of every note
        #                 # which was turned on with this instrument/drum/pitch.
        #                 # One note-off may close multiple note-on events from
        #                 # previous ticks. In case there's a note-off and then
        #                 # note-on at the same tick we keep the open note from
        #                 # this tick.
        #                 end_tick = event.time
        #                 open_notes = last_note_on[key]

        #                 notes_to_close = [
        #                     (start_tick, velocity)
        #                     for start_tick, velocity in open_notes
        #                     if start_tick != end_tick
        #                 ]
        #                 notes_to_keep = [(start_tick, velocity)
        #                                  for start_tick, velocity in open_notes
        #                                  if start_tick == end_tick]

        #                 for start_tick, velocity in notes_to_close:
        #                     start_time = self.__tick_to_time[start_tick]
        #                     end_time = self.__tick_to_time[end_tick]
        #                     # Create the note event
        #                     note = Note(velocity, event.note, start_time,
        #                                 end_time)
        #                     # Get the program and drum type for the current
        #                     # instrument
        #                     program = current_instrument[event.channel]
        #                     # Retrieve the Instrument instance for the current
        #                     # instrument
        #                     # Create a new instrument if none exists
        #                     instrument = __get_instrument(
        #                         program, event.channel, track_idx, 1)
        #                     # Add the note event
        #                     instrument.notes.append(note)

        #                 if len(notes_to_close) > 0 and len(notes_to_keep) > 0:
        #                     # Note-on on the same tick but we already closed
        #                     # some previous notes -> it will continue, keep it.
        #                     last_note_on[key] = notes_to_keep
        #                 else:
        #                     # Remove the last note on for this instrument
        #                     del last_note_on[key]

        # TODO: add support for pitch bend and control changes

        # Initialize list of instruments from instrument_map
        self.instruments = [i for i in instrument_map.values()]
