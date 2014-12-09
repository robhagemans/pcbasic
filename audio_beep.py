"""
PC-BASIC 3.23 - sound_beep.py
Sound implementation through the linux beep utility

(c) 2013, 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

import plat
import state
import backend

music_queue = [ [], [], [], [] ]

if plat.system == 'Windows':
    def init_sound():
        """ This module is not supported under Windows. """
        return False
else:    
    import subprocess
    
    def init_sound():
        """ Initialise sound module. """
        return subprocess.call("command -v beep >/dev/null 2>&1", 
                                shell=True) == 0
    
    def beep(frequency, duration, fill):
        """ Emit a sound. """
        return subprocess.Popen(('beep -f %f -l %d -D %d' % 
            (frequency, duration*fill*1000, duration*(1-fill)*1000)).split())
    
    def hush():
        """ Turn off any sound. """
        subprocess.call('beep -f 1 -l 0'.split())


now_playing = [None, None, None, None]
now_loop = [None, None, None, None]

    
def stop_all_sound():
    """ Clear all sound queues and turn off all sounds. """
    global now_loop, now_playing
    for voice in now_playing:
        if voice and voice.poll() == None:
            voice.terminate()   
    now_playing = [None, None, None, None]
    now_loop = [None, None, None, None]
    hush()
    
def play_sound(frequency, duration, fill, loop, voice=0, volume=15):
    """ Queue a sound for playing. """
    music_queue[voice].append((frequency, duration, fill, loop, volume))
        
def check_sound():
    """ Update the sound queue and play sounds. """
    global now_loop
    for voice in range(4):
        if now_loop[voice]:
            if (music_queue[voice] and now_playing[voice] 
                    and now_playing[voice].poll() == None):
                now_playing[voice].terminate()
                now_loop[voice] = None
                hush()
            elif not now_playing[voice] or now_playing[voice].poll() != None:
                play_now(*now_loop[voice], voice=voice)
        if (music_queue[voice] and 
                (not now_playing[voice] or now_playing[voice].poll() != None)):
            play_now(*music_queue[voice].pop(0), voice=voice)
        # remove the notes that have been played
        backend.sound_done(voice, len(music_queue[voice]))
    
def busy():
    """ Is the mixer busy? """
    is_busy = False
    for voice in range(4):
        is_busy = is_busy or ((not now_loop[voice]) and 
                    now_playing[voice] and now_playing[voice].poll() == None)
    return is_busy

def set_noise(is_white):
    """ Set the character of the noise channel. """
    pass      
      
def quit_sound():
    """ Shut down the mixer. """
    pass

# implementation
      
def play_now(frequency, duration, fill, loop, volume, voice):
    """ Play a sound immediately. """
    frequency = max(1, min(19999, frequency))
    if loop:
        duration = 5
        fill = 1
        now_loop[voice] = (frequency, duration, fill, loop, volume)
    if voice == 3:
        # ignore noise channel
        pass
    else:    
        now_playing[voice] = beep(frequency, duration, fill)
    
